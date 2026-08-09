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
- The standalone repository passes 186 tests.
- The deployed public acceptance flow passes 17/17.
- The shared resilience exit test passes 10/10.

These measurements establish behavior on committed synthetic fixtures. They do not establish
clinical effectiveness, external validity, or institutional validation.

## Claims deliberately rejected

- “Hospitals do not have stewardship programs” — contradicted by current national adoption data.
- “Nearly all critical-access hospitals lack expertise” — unsupported breadth.
- “This saves $732 per patient” or “reduces stay by 4.6 days” — review findings, not product effects.
- “The Router pages the pharmacist” — no messaging integration exists; it persists a review
  escalation and nothing is sent.
- “Eight agents are eight services” — they are logical roles in one Cloud Run service.
