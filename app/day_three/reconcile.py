"""The Reconciler: the question nobody at a small hospital is there to ask.

At hour 48 the lab knows which organism it is. Somebody should ask whether the antibiotic the
doctor guessed on admission is still the right one. At a large hospital an infectious disease
pharmacist does this. At a critical access hospital there is nobody, so it does not happen.

**Scope is deliberately narrow.** This decides organism-to-drug appropriateness, which is
unambiguous and checkable against a susceptibility result. It does **not** recommend doses, does
not adjust for renal function beyond flagging that a pharmacist must, and does not prescribe.
Every output is a draft requiring licensed pharmacist approval. Narrow scope is what makes the
recommendation defensible.

Every conclusion is emitted as a Claim, so nothing reaches a human that the Verifier has not
grounded in a real susceptibility result.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from day_three.antibiogram import Antibiogram, Interpretation, Isolate
from spine.verify import Claim, ClaimKind, Record, SourceRef

# Narrower is better. Lower rank means narrower spectrum, which means less collateral damage to
# the patient's own flora and less selective pressure driving resistance.
#
# This is a deliberately coarse ordering over common agents, used only to answer "is there a
# narrower option that this organism is susceptible to". It is not a substitute for a formulary
# or for clinical judgement, and the UI says so.
SPECTRUM_RANK: dict[str, int] = {
    "penicillin": 1,
    "amoxicillin": 2,
    "nitrofurantoin": 2,
    "trimethoprim-sulfamethoxazole": 3,
    "cefazolin": 3,
    "doxycycline": 3,
    "ceftriaxone": 4,
    "ciprofloxacin": 4,
    "levofloxacin": 4,
    "amoxicillin-clavulanate": 4,
    "piperacillin-tazobactam": 6,
    "cefepime": 6,
    "vancomycin": 6,
    "meropenem": 8,
    "ertapenem": 7,
    "linezolid": 8,
    "daptomycin": 8,
}

BROAD_THRESHOLD = 6


class Kind(StrEnum):
    DEESCALATE = "deescalate"
    ESCALATE = "escalate"
    NO_CHANGE = "no_change"
    SHORTAGE_ADJUST = "shortage_adjust"
    AWAITING_RESULT = "awaiting_result"


@dataclass(frozen=True)
class PatientContext:
    patient_id: str
    regimen: tuple[str, ...]
    allergies: tuple[str, ...] = ()
    renal_impairment: bool = False


@dataclass
class Recommendation:
    kind: Kind
    headline: str
    claims: list[Claim] = field(default_factory=list)
    suggested: str | None = None
    requires_pharmacist: bool = True
    notes: list[str] = field(default_factory=list)


def spectrum(drug: str) -> int:
    """Unknown drugs are treated as broad. Guessing narrow would be the unsafe direction."""
    return SPECTRUM_RANK.get(drug.lower(), BROAD_THRESHOLD)


def is_broad(drug: str) -> bool:
    return spectrum(drug) >= BROAD_THRESHOLD


class Reconciler:
    """Compares a regimen against what the lab now knows."""

    def __init__(
        self,
        antibiogram: Antibiogram | None = None,
        shortages: frozenset[str] = frozenset(),
    ) -> None:
        self._antibiogram = antibiogram
        self._shortages = frozenset(d.lower() for d in shortages)

    def reconcile(
        self,
        patient: PatientContext,
        isolate: Isolate | None,
        artifact_id: str,
    ) -> Recommendation:
        if isolate is None:
            return Recommendation(
                kind=Kind.AWAITING_RESULT,
                headline="Culture not finalised. Re-arming for hour 72 rather than guessing.",
                notes=["No organism identified yet. The agent does not speculate."],
            )

        susceptible = {
            s.drug.lower(): s
            for s in isolate.susceptibilities
            if s.interpretation is Interpretation.S
        }
        resistant = {
            s.drug.lower(): s
            for s in isolate.susceptibilities
            if s.interpretation in (Interpretation.R, Interpretation.NS)
        }

        claims: list[Claim] = []

        # 1. Is the patient on something the organism is resistant to? That is the urgent case.
        for drug in patient.regimen:
            hit = resistant.get(drug.lower())
            if hit is not None:
                claims.append(
                    self._claim(
                        f"clm_resist_{drug}",
                        f"The isolate is resistant to {drug}.",
                        ClaimKind.SUSCEPTIBILITY,
                        artifact_id,
                        hit.source_ref or f"{drug.upper()} {hit.interpretation.value}",
                    )
                )
                return Recommendation(
                    kind=Kind.ESCALATE,
                    headline=(
                        f"{isolate.organism} is resistant to {drug}, which this patient is "
                        f"currently receiving."
                    ),
                    claims=claims,
                    notes=["Urgent. The current therapy is unlikely to be working."],
                )

        # 2. Is there a narrower option the organism is susceptible to?
        current_broadest = max((spectrum(d) for d in patient.regimen), default=0)
        candidates = sorted(
            (
                drug
                for drug in susceptible
                if spectrum(drug) < current_broadest
                and not self._is_allergic(patient, drug)
            ),
            key=spectrum,
        )

        if not candidates:
            if any(is_broad(d) for d in patient.regimen) and susceptible:
                return Recommendation(
                    kind=Kind.NO_CHANGE,
                    headline="No narrower option this organism is susceptible to. Continue.",
                    claims=claims,
                    notes=["Broad therapy is justified here by the susceptibility result."],
                )
            return Recommendation(
                kind=Kind.NO_CHANGE,
                headline="Current therapy is already the narrowest appropriate option.",
                claims=claims,
            )

        narrowest = candidates[0]
        evidence = susceptible[narrowest]
        claims.append(
            self._claim(
                f"clm_susc_{narrowest}",
                f"The isolate is susceptible to {narrowest}.",
                ClaimKind.SUSCEPTIBILITY,
                artifact_id,
                evidence.source_ref or f"{narrowest.upper()} {evidence.interpretation.value}",
            )
        )

        # 3. Is that narrower option actually available?
        if narrowest in self._shortages:
            fallback = next((d for d in candidates[1:] if d not in self._shortages), None)
            return Recommendation(
                kind=Kind.SHORTAGE_ADJUST,
                headline=(
                    f"{narrowest} would be the right de-escalation, but it is in shortage."
                    + (f" Next best available option is {fallback}." if fallback else "")
                ),
                claims=claims,
                suggested=fallback,
                notes=[
                    f"{narrowest} is on the active shortage list.",
                    "Stated explicitly so the tradeoff is visible rather than silent.",
                ],
            )

        notes = []
        if patient.renal_impairment:
            notes.append(
                "Renal impairment is recorded. Dosing must be reviewed by the pharmacist; "
                "this agent does not recommend doses."
            )

        return Recommendation(
            kind=Kind.DEESCALATE,
            headline=(
                f"Consider narrowing from {', '.join(patient.regimen)} to {narrowest}. "
                f"{isolate.organism} is susceptible to it."
            ),
            claims=claims,
            suggested=narrowest,
            notes=notes,
        )

    def records_for(self, isolate: Isolate) -> list[Record]:
        """Structured facts the Verifier uses to catch a contradiction.

        A finalised resistant result forbids the word susceptible for that drug, even if the
        agent produces a quote that looks supportive.
        """
        records: list[Record] = []
        for susceptibility in isolate.susceptibilities:
            if susceptibility.interpretation in (Interpretation.R, Interpretation.NS):
                records.append(
                    Record(
                        key=susceptibility.drug.lower(),
                        value=susceptibility.interpretation.value,
                        forbids=("susceptible",),
                    )
                )
        return records

    @staticmethod
    def _is_allergic(patient: PatientContext, drug: str) -> bool:
        return any(allergy.lower() in drug.lower() for allergy in patient.allergies)

    @staticmethod
    def _claim(
        claim_id: str, text: str, kind: ClaimKind, artifact_id: str, quoted: str
    ) -> Claim:
        return Claim(
            id=claim_id,
            text=text,
            kind=kind,
            source_refs=(SourceRef(artifact_id=artifact_id, quoted_text=quoted),),
        )
