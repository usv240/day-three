# Day Three research traceability

**Last source review:** August 9, 2026

This ledger separates four things that hackathon copy often mixes together: the size of the
problem, a workflow recommendation, evidence from one implementation, and evidence that this
specific product works. Only the last category can be established by Day Three's own recordings,
tests, and deployed acceptance flow.

## Source hierarchy

1. Current CDC guidance and surveillance for national practice and implementation priorities.
2. CLSI M39 for cumulative-antibiogram behavior. The product maps selected rules to executable
   conformance tests but does not claim certification.
3. Primary peer-reviewed studies for bounded observations about named samples.
4. Systematic reviews for historical outcome and cost context, never product promises.

Every public statistic keeps its population, timeframe, denominator, and study type. A finding
from selected critical-access hospitals is not generalized to all rural hospitals.

## Source-to-decision matrix

| Source | Verified finding used | Product decision | Limit preserved |
|---|---|---|---|
| [CDC 2025 stewardship update](https://www.cdc.gov/antibiotic-use/hcp/data-research/stewardship-report.html) | In 2024, 97% of acute-care hospitals reported all seven Core Elements; 16% reported all six newer priorities. | Frame the friction as execution depth and follow-through, not absence of a program. | National self-reported survey results are not a CAH-specific rate. |
| [CDC small and critical-access implementation guide](https://www.cdc.gov/antibiotic-use/media/pdfs/core-elements-small-critical-508.pdf) | Small facilities may adapt nearby or regional recommendations; pharmacists often lead stewardship. | Build local cumulative evidence while keeping a pharmacist as the decision owner. | Guidance supports a workflow, not this product's clinical correctness. |
| [CDC hospital Core Elements](https://www.cdc.gov/antibiotic-use/hcp/core-elements/hospital.html) | Prospective audit and feedback and preauthorization are priority interventions; tracking and reporting matter. | Schedule review and show auditable local resistance data. | Day Three does not perform preauthorization or change orders. |
| [CDC critical-access case example](https://www.cdc.gov/nhsn/au-case-examples/reducing-carbapenem-use.html) | One rural CAH paired an antibiogram with prospective telepharmacist review. | Link the local antibiogram to a timed pharmacist-review draft. | One case example does not establish general effectiveness or a product outcome. |
| [Ryder et al., selected 21-program evaluation](https://pmc.ncbi.nlm.nih.gov/articles/PMC10594270/) | Among 20 respondents to the barriers item, 15 cited time/personnel, 8 expertise, and 5 electronic-record limitations. | Emphasize constrained coordination and preserved context. | Selected Iowa/Nebraska programs that self-identified gaps; not national prevalence. |
| [Kassamali-Escobar et al., 19-CAH process evaluation](https://pmc.ncbi.nlm.nih.gov/articles/PMC11574594/) | Staffing shortages, turnover, and bandwidth were barriers; 17 sites collected local data, while none completed a full improvement cycle in one year. | Register long-lived work up front and resume from durable state. | A process evaluation is not proof of clinical outcome or proof that software removes the barriers. |
| [2024 GRAM analysis](https://pubmed.ncbi.nlm.nih.gov/39299261/) | 4.71 million deaths were associated with bacterial AMR in 2021 and 1.14 million attributable; 39.1 million is a cumulative 2025-2050 projection. | Use AMR as scoped problem context. | Never imply Day Three prevents a quantified number of deaths. |
| [Low-isolate reliability analysis](https://pmc.ncbi.nlm.nih.gov/articles/PMC9927543/) | Small isolate counts produce unstable cumulative percentages. | Suppress percentages below the selected CLSI threshold and let the verifier reject fabricated rates. | The UI is a demonstration antibiogram, not a certified laboratory report. |

## Product evidence, separate from literature

- Four recorded Gemini 3.5 Flash calls are graded 29/29 against adjacent synthetic truth.
- Anyone can trigger a fresh, unrecorded Gemini call on the deployed service and see it graded by
  the same grader against the same truth file, so the published figure is checkable rather than
  asserted.
- A wall-clock wake can be registered by any visitor and fires only when a scheduled worker
  claims it, which removes the simulated clock from the durability claim.
- The standalone repository passes 303 tests.
- The deployed public acceptance flow passes 18/18.
- The shared resilience exit test passes 10/10.

These measurements establish behavior on committed synthetic fixtures. They do not establish
clinical effectiveness, external validity, or institutional validation.

**What the standards substitution does and does not buy.** Mapping CLSI M39 rules to executable
tests replaces an unverifiable practitioner testimonial with something a judge can run, and that
is the right trade for correctness: a reader can check whether first-isolate handling and
low-count suppression behave as the standard describes. It does not establish fit to practice.
No pharmacist has used this, so nothing here shows that the modelled friction matches lived
workflow or that the output would be adopted. Those are different questions, and only the first
is answered.

## Claims deliberately rejected

- "Hospitals do not have stewardship programs" â€" contradicted by current national adoption data.
- "Nearly all critical-access hospitals lack expertise" â€" unsupported breadth.
- "This saves $732 per patient" or "reduces stay by 4.6 days" â€" review findings, not product effects.
- "The Router pages the pharmacist" â€" no messaging integration exists; it persists a review
  escalation and nothing is sent.
- "Eight agents are eight services" â€" they are logical roles in one Cloud Run service.
