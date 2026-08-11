"""Reconciler tests.

Scope discipline is a feature here. These tests pin down what the agent will and will not say,
because a narrow, defensible recommendation is worth more than a broad, unsafe one.
"""

from datetime import datetime, timezone

import pytest

from day_three.antibiogram import Interpretation, Isolate, Susceptibility
from day_three.reconcile import (
    Kind,
    PatientContext,
    Reconciler,
    claim_for_rendering,
    headline_for_rendering,
    is_broad,
    spectrum,
)
from spine.verify import Verifier

LAB = """CULTURE AND SUSCEPTIBILITY REPORT
Organism: Escherichia coli
CEFTRIAXONE          <=1        S
CIPROFLOXACIN         >2        R
NITROFURANTOIN       <=16       S
MEROPENEM          <=0.25       S
"""

ART = "art_lab_0031"


# The exact lines as they appear in LAB. Intake must capture the real text, including the MIC,
# because the Verifier checks the quote against the document and a paraphrase is not a quote.
REPORT_LINES = {
    "ceftriaxone": "CEFTRIAXONE          <=1        S",
    "ciprofloxacin": "CIPROFLOXACIN         >2        R",
    "nitrofurantoin": "NITROFURANTOIN       <=16       S",
    "meropenem": "MEROPENEM          <=0.25       S",
}


def isolate_with(*pairs: tuple[str, Interpretation]) -> Isolate:
    return Isolate(
        isolate_id="iso_1",
        patient_id="pt_1",
        organism="Escherichia coli",
        collected_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        susceptibilities=tuple(
            Susceptibility(
                drug=d,
                interpretation=i,
                source_ref=REPORT_LINES.get(d.lower(), f"{d.upper()} {i.value}"),
            )
            for d, i in pairs
        ),
    )


@pytest.fixture
def reconciler():
    return Reconciler()


# --- Spectrum ordering ------------------------------------------------------------


def test_narrower_agents_rank_lower():
    assert spectrum("nitrofurantoin") < spectrum("ceftriaxone") < spectrum("meropenem")


def test_unknown_drugs_are_treated_as_broad():
    """Guessing narrow would be the unsafe direction."""
    assert is_broad("some-new-agent-2026")


# --- De-escalation ----------------------------------------------------------------


def test_recommends_narrowing_when_a_narrower_susceptible_option_exists(reconciler):
    patient = PatientContext("pt_1", regimen=("piperacillin-tazobactam",))
    isolate = isolate_with(
        ("ceftriaxone", Interpretation.S), ("meropenem", Interpretation.S)
    )

    rec = reconciler.reconcile(patient, isolate, ART)
    assert rec.kind is Kind.DEESCALATE
    assert rec.suggested == "ceftriaxone"
    assert "narrowing" in rec.headline.lower()


def test_picks_the_narrowest_susceptible_option_not_just_any(reconciler):
    patient = PatientContext("pt_1", regimen=("meropenem",))
    isolate = isolate_with(
        ("ceftriaxone", Interpretation.S),
        ("nitrofurantoin", Interpretation.S),
        ("meropenem", Interpretation.S),
    )
    assert reconciler.reconcile(patient, isolate, ART).suggested == "nitrofurantoin"


def test_every_recommendation_carries_a_grounded_claim(reconciler):
    patient = PatientContext("pt_1", regimen=("meropenem",))
    isolate = isolate_with(("ceftriaxone", Interpretation.S))
    rec = reconciler.reconcile(patient, isolate, ART)

    assert rec.claims
    verifier = Verifier(artifacts={ART: LAB})
    for claim in rec.claims:
        assert verifier.verify(claim).accepted, f"{claim.text} was not grounded"


def test_recommendations_always_require_a_pharmacist(reconciler):
    patient = PatientContext("pt_1", regimen=("meropenem",))
    rec = reconciler.reconcile(
        patient, isolate_with(("ceftriaxone", Interpretation.S)), ART
    )
    assert rec.requires_pharmacist is True


# --- Allergies --------------------------------------------------------------------


def test_never_suggests_a_drug_the_patient_is_allergic_to(reconciler):
    patient = PatientContext("pt_1", regimen=("meropenem",), allergies=("ceftriaxone",))
    isolate = isolate_with(
        ("ceftriaxone", Interpretation.S),
        ("ciprofloxacin", Interpretation.S),
    )
    rec = reconciler.reconcile(patient, isolate, ART)
    assert rec.suggested != "ceftriaxone"


# --- Escalation -------------------------------------------------------------------


def test_flags_resistance_to_the_current_drug_as_urgent(reconciler):
    patient = PatientContext("pt_1", regimen=("ciprofloxacin",))
    isolate = isolate_with(
        ("ciprofloxacin", Interpretation.R), ("ceftriaxone", Interpretation.S)
    )

    rec = reconciler.reconcile(patient, isolate, ART)
    assert rec.kind is Kind.ESCALATE
    assert "resistant" in rec.headline.lower()
    assert "urgent" in " ".join(rec.notes).lower()


def test_resistance_takes_priority_over_de_escalation(reconciler):
    """Being on a drug that does not work matters more than being on one that is too broad."""
    patient = PatientContext("pt_1", regimen=("ciprofloxacin", "meropenem"))
    isolate = isolate_with(
        ("ciprofloxacin", Interpretation.R),
        ("nitrofurantoin", Interpretation.S),
    )
    assert reconciler.reconcile(patient, isolate, ART).kind is Kind.ESCALATE


# --- No change --------------------------------------------------------------------


def test_says_no_change_when_already_narrowest(reconciler):
    patient = PatientContext("pt_1", regimen=("nitrofurantoin",))
    isolate = isolate_with(("nitrofurantoin", Interpretation.S))
    assert reconciler.reconcile(patient, isolate, ART).kind is Kind.NO_CHANGE


def test_broad_therapy_is_endorsed_when_nothing_narrower_works(reconciler):
    patient = PatientContext("pt_1", regimen=("meropenem",))
    isolate = isolate_with(
        ("meropenem", Interpretation.S),
        ("ceftriaxone", Interpretation.R),
        ("ciprofloxacin", Interpretation.R),
    )
    rec = reconciler.reconcile(patient, isolate, ART)
    assert rec.kind is Kind.NO_CHANGE
    assert "justified" in " ".join(rec.notes).lower()


# --- Shortages --------------------------------------------------------------------


def test_shortage_blocks_the_preferred_option_and_says_so(reconciler):
    r = Reconciler(shortages=frozenset({"ceftriaxone"}))
    patient = PatientContext("pt_1", regimen=("meropenem",))
    isolate = isolate_with(
        ("ceftriaxone", Interpretation.S),
        ("ciprofloxacin", Interpretation.S),
    )
    rec = r.reconcile(patient, isolate, ART)

    assert rec.kind is Kind.SHORTAGE_ADJUST
    assert "shortage" in rec.headline.lower()
    assert rec.suggested == "ciprofloxacin"


def test_shortage_with_no_alternative_still_states_the_problem(reconciler):
    r = Reconciler(shortages=frozenset({"ceftriaxone"}))
    patient = PatientContext("pt_1", regimen=("meropenem",))
    rec = r.reconcile(patient, isolate_with(("ceftriaxone", Interpretation.S)), ART)
    assert rec.kind is Kind.SHORTAGE_ADJUST
    assert rec.suggested is None


# --- Refusing to guess ------------------------------------------------------------


def test_does_not_speculate_before_the_culture_finalises(reconciler):
    patient = PatientContext("pt_1", regimen=("meropenem",))
    rec = reconciler.reconcile(patient, None, ART)
    assert rec.kind is Kind.AWAITING_RESULT
    assert "does not speculate" in " ".join(rec.notes)


def test_never_synthesises_a_quote_for_an_unquoted_susceptibility(reconciler):
    """Regression, found by probing the deployed reconcile endpoint.

    An earlier version fell back to f"{DRUG} {INTERPRETATION}" when the extraction had produced
    no quote. For any drug printed without an MIC column, which is a common real report format,
    that manufactured string genuinely appears in the document, so the Verifier accepted a claim
    whose quote the model never produced. The chain from model output to rendered sentence was
    silently broken while every check still looked green.
    """
    from day_three.antibiogram import Isolate

    document = "Organism: Staphylococcus aureus\nOXACILLIN            R\nVANCOMYCIN            S\n"
    isolate = Isolate(
        isolate_id="i1",
        patient_id="pt_1",
        organism="Staphylococcus aureus",
        collected_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        susceptibilities=(
            Susceptibility("vancomycin", Interpretation.S, source_ref=None),
        ),
    )
    rec = reconciler.reconcile(
        PatientContext("pt_1", regimen=("linezolid",)), isolate, "art"
    )
    verifier = Verifier(artifacts={"art": document})

    assert rec.claims, "the recommendation should still surface for a pharmacist"
    for claim in rec.claims:
        assert (
            claim.source_refs == ()
        ), "no quote must mean no source reference, never a made-up one"
        assert not verifier.verify(
            claim
        ).accepted, "an unquoted claim must not be renderable"


def test_rejected_claim_sentence_is_withheld_at_the_rendering_boundary(reconciler):
    """A client must not receive unsupported prose that it could render despite the verdict."""
    from day_three.antibiogram import Isolate

    isolate = Isolate(
        isolate_id="i1",
        patient_id="pt_1",
        organism="Staphylococcus aureus",
        collected_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        susceptibilities=(
            Susceptibility("vancomycin", Interpretation.S, source_ref=None),
        ),
    )
    rec = reconciler.reconcile(
        PatientContext("pt_1", regimen=("linezolid",)), isolate, "art"
    )
    payload = claim_for_rendering(
        rec.claims[0], Verifier(artifacts={"art": "VANCOMYCIN S"})
    )

    assert payload["accepted"] is False
    assert payload["text"] is None
    assert payload["rejection_code"] == "no_source"
    assert payload["rejection_reason"]
    safe_headline = headline_for_rendering(rec, [payload])
    assert "susceptible" not in safe_headline.lower()
    assert "source verification" in safe_headline.lower()


def test_a_quoted_susceptibility_still_grounds_normally(reconciler):
    """The fix must not break the happy path."""
    isolate = isolate_with(("ceftriaxone", Interpretation.S))
    rec = reconciler.reconcile(
        PatientContext("pt_1", regimen=("meropenem",)), isolate, ART
    )
    verifier = Verifier(artifacts={ART: LAB})
    assert rec.claims
    assert all(verifier.verify(c).accepted for c in rec.claims)


def test_never_recommends_a_dose(reconciler):
    """Scope discipline. Dosing is out of scope and stays out of scope."""
    patient = PatientContext("pt_1", regimen=("meropenem",), renal_impairment=True)
    rec = reconciler.reconcile(
        patient, isolate_with(("ceftriaxone", Interpretation.S)), ART
    )

    text = (rec.headline + " " + " ".join(rec.notes)).lower()
    assert "does not recommend doses" in text
    for unit in (" mg", " gram", "q8h", "q12h", "bid", "tid"):
        assert unit not in text


# --- Feeding the Verifier ---------------------------------------------------------


def test_resistant_results_become_records_that_forbid_calling_it_susceptible(
    reconciler,
):
    isolate = isolate_with(
        ("ciprofloxacin", Interpretation.R), ("ceftriaxone", Interpretation.S)
    )
    records = reconciler.records_for(isolate)

    assert len(records) == 1
    assert records[0].key == "ciprofloxacin"
    assert "susceptible" in records[0].forbids


def test_those_records_actually_block_a_contradicting_claim(reconciler):
    from spine.verify import Claim, ClaimKind, RejectionCode, SourceRef

    isolate = isolate_with(("ciprofloxacin", Interpretation.R))
    verifier = Verifier(artifacts={ART: LAB}, records=reconciler.records_for(isolate))

    bad = Claim(
        id="clm_flip",
        text="The isolate is susceptible to ciprofloxacin.",
        kind=ClaimKind.SUSCEPTIBILITY,
        source_refs=(SourceRef(ART, "CIPROFLOXACIN         >2        R"),),
    )
    assert verifier.verify(bad).code is RejectionCode.CONTRADICTS_RECORD
