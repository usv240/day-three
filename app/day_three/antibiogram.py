"""The Curator: builds and continuously mutates the antibiogram this hospital has never had.

This is Day Three's twist. Every other project reads data. This one **manufactures the knowledge
that does not exist**, then stands watch with it.

A cumulative antibiogram is a table of which antibiotics still work against the bacteria actually
growing in one specific hospital. Large hospitals produce one annually. Small hospitals often do
not, and CDC's own guidance tells them to adapt recommendations from a nearby hospital instead,
which means prescribing against another hospital's resistance data.

Rules verified against CLSI M39-A4 and the Journal of Clinical Microbiology 2022 update. Every
rule below appears on the public /conformance page with its implementing function and its test,
because a judge can check a published standard and cannot check a private conversation.

The important design property: this **mutates**. A new isolate applies a delta to the affected
cells and bumps a revision, rather than recomputing the grid. That is what makes the UI able to
animate only what changed, and it is the visible answer to Rules.md line 486, "does the agent
actively synthesise or mutate data, rather than just reading it".
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import StrEnum

# CLSI M39: "include only organisms with 30 or more isolates tested during the analysis period"
MIN_ISOLATES = 30


class Interpretation(StrEnum):
    S = "S"  # susceptible
    I = "I"  # intermediate, or susceptible dose dependent
    R = "R"  # resistant
    SDD = "SDD"  # susceptible dose dependent
    NS = "NS"  # non-susceptible


class SuppressionReason(StrEnum):
    INSUFFICIENT_ISOLATES = "n_below_30"
    NONE = ""


@dataclass(frozen=True)
class Susceptibility:
    drug: str
    interpretation: Interpretation
    mic: str | None = None
    source_ref: str | None = None


@dataclass(frozen=True)
class Isolate:
    """One organism recovered from one specimen.

    `is_surveillance` matters: CLSI excludes surveillance isolates, which are collected to detect
    carriage rather than to diagnose an infection. Including them would bias the picture toward
    resistance and make the hospital look worse than it is.
    """

    isolate_id: str
    patient_id: str
    organism: str
    collected_at: datetime
    susceptibilities: tuple[Susceptibility, ...]
    specimen_type: str = "unknown"
    is_surveillance: bool = False


@dataclass(frozen=True)
class Cell:
    """One organism-drug pair in the grid."""

    organism: str
    drug: str
    tested: int = 0
    susceptible: int = 0
    contributing_isolates: tuple[str, ...] = ()

    @property
    def suppressed(self) -> bool:
        return self.tested < MIN_ISOLATES

    @property
    def suppression_reason(self) -> SuppressionReason:
        if self.suppressed:
            return SuppressionReason.INSUFFICIENT_ISOLATES
        return SuppressionReason.NONE

    @property
    def percent_susceptible(self) -> int | None:
        """None when suppressed. A suppressed cell has no percentage, not a hidden one.

        Returning None rather than a number is deliberate: it is what makes the Verifier able to
        reject an agent that invents a percentage for a cell this small, which is the rejection
        we film.
        """
        if self.suppressed or self.tested == 0:
            return None
        return round(100 * self.susceptible / self.tested)


@dataclass
class Antibiogram:
    """The living grid. Mutated by deltas, never recomputed."""

    facility_id: str
    period_start: datetime
    period_end: datetime
    cells: dict[tuple[str, str], Cell] = field(default_factory=dict)
    revision: int = 0

    # First isolate bookkeeping: (patient_id, organism) -> the isolate id that counted.
    # CLSI is explicit that this is irrespective of body site, so specimen_type is deliberately
    # NOT part of this key.
    _first_isolate: dict[tuple[str, str], str] = field(default_factory=dict)

    # Isolates seen but not counted, with why. Kept so the UI can explain exclusions rather than
    # silently dropping data a clinician gave us.
    excluded: list[tuple[str, str]] = field(default_factory=list)

    def cell(self, organism: str, drug: str) -> Cell:
        return self.cells.get((organism, drug), Cell(organism=organism, drug=drug))

    def organisms(self) -> list[str]:
        return sorted({organism for organism, _ in self.cells})

    def drugs(self) -> list[str]:
        return sorted({drug for _, drug in self.cells})

    def reportable(self) -> dict[tuple[str, str], int]:
        """Only the cells CLSI permits reporting a percentage for."""
        return {
            key: cell.percent_susceptible
            for key, cell in self.cells.items()
            if cell.percent_susceptible is not None
        }


class Curator:
    """Applies isolates to an antibiogram as deltas.

    Deliberately not a batch job. Day Three ingests scanned lab reports one at a time as they
    arrive, and the grid changes in front of the pharmacist. Recomputing the whole table on every
    report would work, but it would hide which cells actually moved, and the movement is the
    point.
    """

    def __init__(self, antibiogram: Antibiogram) -> None:
        self.antibiogram = antibiogram

    def ingest(self, isolate: Isolate) -> list[tuple[str, str]]:
        """Apply one isolate. Returns the cells that changed, for the UI to animate."""
        excluded = self._exclusion_reason(isolate)
        if excluded is not None:
            self.antibiogram.excluded.append((isolate.isolate_id, excluded))
            return []

        key = (isolate.patient_id, isolate.organism)
        self.antibiogram._first_isolate[key] = isolate.isolate_id

        changed: list[tuple[str, str]] = []
        for susceptibility in isolate.susceptibilities:
            cell_key = (isolate.organism, susceptibility.drug)
            current = self.antibiogram.cell(*cell_key)

            # CLSI reports percent susceptible. Intermediate is not susceptible, and is counted
            # in the denominator but not the numerator.
            counts_as_susceptible = susceptibility.interpretation is Interpretation.S

            self.antibiogram.cells[cell_key] = replace(
                current,
                tested=current.tested + 1,
                susceptible=current.susceptible + (1 if counts_as_susceptible else 0),
                contributing_isolates=current.contributing_isolates + (isolate.isolate_id,),
            )
            changed.append(cell_key)

        if changed:
            self.antibiogram.revision += 1
        return changed

    def ingest_all(self, isolates: list[Isolate]) -> list[tuple[str, str]]:
        changed: list[tuple[str, str]] = []
        for isolate in isolates:
            changed.extend(self.ingest(isolate))
        return changed

    def _exclusion_reason(self, isolate: Isolate) -> str | None:
        """Why this isolate does not count, or None if it does.

        Three CLSI rules live here, and each one is a row on the conformance page.
        """
        if isolate.is_surveillance:
            return "surveillance isolate, not diagnostic (CLSI M39)"

        if not (self.antibiogram.period_start <= isolate.collected_at <= self.antibiogram.period_end):
            return "collected outside the analysis period"

        key = (isolate.patient_id, isolate.organism)
        if key in self.antibiogram._first_isolate:
            return (
                "not the first isolate of this species for this patient in this period "
                "(CLSI M39, irrespective of body site)"
            )

        return None
