# Day Three validation evidence

**Reviewed:** August 9, 2026

This dossier is the substitute used when practitioner access is not available during a hackathon.
It is not a clinical validation study and does not claim user endorsement. It combines current
public research, executable standards boundaries, adversarial tests, measured model fixtures, live
acceptance checks, and explicit limitations.

## What each evidence layer can establish

| Evidence | What it can establish | What it cannot establish |
|---|---|---|
| CDC guidance and peer-reviewed literature | The workflow problem and relevant implementation patterns exist | That Day Three improves clinical outcomes |
| CLSI-oriented executable boundaries | Specific cumulative-antibiogram rules behave as tested | Certification or complete CLSI conformance |
| Recorded model calls with adjacent truth | Accuracy on the committed synthetic fixtures | Accuracy on every laboratory format |
| Unit and integration tests | Defined invariants hold under the tested conditions | Real-world adoption or usability |
| Public acceptance and exit tests | The deployed workflow and failure recovery are executable | Hospital production readiness |
| Accessibility checks | Token contrast and coded interface contracts pass | A human usability study |

## Research to implementation trace

| Source | Product decision | Executable or visible evidence |
|---|---|---|
| [CDC small and critical-access implementation guide](https://www.cdc.gov/antibiotic-use/media/pdfs/core-elements-small-critical-508.pdf) | Keep a pharmacist as the decision owner and support local cumulative evidence | Pharmacist-review boundary in the console; tests/test_reconcile.py |
| [CDC hospital Core Elements](https://www.cdc.gov/antibiotic-use/hcp/core-elements/hospital.html) | Schedule review, track work, and preserve an audit trail | tests/test_course.py; tests/test_wake.py |
| [CDC critical-access case example](https://www.cdc.gov/nhsn/au-case-examples/reducing-carbapenem-use.html) | Connect local susceptibility context to prospective pharmacist review | Guided antibiogram-to-review flow |
| [Selected 21-program evaluation](https://pmc.ncbi.nlm.nih.gov/articles/PMC10594270/) | Design for constrained time, personnel, expertise, and electronic-record support | Durable wakes and resumable state |
| [19-CAH process evaluation](https://pmc.ncbi.nlm.nih.gov/articles/PMC11574594/) | Register long-lived work up front instead of relying on memory | Five inpatient wakes through day 14, with a separately armed 30-day post-discharge check |
| [Low-isolate reliability analysis](https://pmc.ncbi.nlm.nih.gov/articles/PMC9927543/) | Suppress percentages below the selected threshold | test_a_cell_below_thirty_isolates_is_suppressed |
| [De-escalation timing review](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11776815/) | Put the first review near 48 hours and re-arm if evidence is incomplete | test_the_agent_wakes_itself_at_hour_forty_eight |

The full source hierarchy and rejected claims are in
[docs/research-traceability.md](docs/research-traceability.md).

## Product measurements

| Measurement | Current result | Reproduce |
|---|---:|---|
| Recorded Gemini extraction | 29 of 29 fields across 4 fixtures | python scripts/record_intake.py --rescore |
| Standalone test suite | 308 passed | python -m pytest -q |
| Public acceptance flow | 18 of 18 | python scripts/demo_flow.py with the public URL |
| Shared-substrate exit test | 10 of 10 | POST /exit-test with an empty JSON body |
| Accessibility gate | Pass in light and dark themes | python scripts/check_a11y.py |

These measurements describe committed synthetic fixtures and specified behavior. They are not
clinical-effectiveness measurements.

## Adversarial safety matrix

| Attack or failure | Required behavior | Regression evidence |
|---|---|---|
| Empty source quote | Reject as no source | test_rejects_a_source_reference_with_an_empty_quote |
| Whitespace-only quote | Reject as no source | test_rejects_a_whitespace_only_quote |
| Valid quote beside empty quote | Reject the claim | test_an_empty_quote_cannot_be_hidden_behind_a_valid_one |
| Fabricated source text | Reject | test_rejects_a_fabricated_quote |
| Fabricated percentage | Reject | test_rejects_a_fabricated_percentage |
| Instruction hidden in a report | Quarantine as data | test_instruction_shaped_text_in_a_report_is_quarantined |
| Hyphenated or apostrophe-bearing name | Redact | test_ordinary_real_world_spellings_are_not_missed |
| Lowercase applicant label or PO box | Redact | test_ordinary_real_world_spellings_are_not_missed |
| Organism or susceptibility row | Preserve | test_the_gate_does_not_over_redact |
| Redaction reviewer failure | Fail the gate closed | test_a_failing_reviewer_fails_the_gate_closed |
| Registry access without scope | Refuse and audit | test_consuming_without_the_scope_is_refused; test_every_access_attempt_is_logged |

## Resilience matrix

| Condition | Required behavior | Regression evidence |
|---|---|---|
| Crash after completed work | Resume without repeating completed work | test_resume_after_crash_does_not_repeat_completed_work |
| Two workers claim one wake | Exactly one claim succeeds | test_a_wake_is_claimed_by_exactly_one_worker |
| Transient dispatch failure | Release for bounded retry | test_direct_dispatch_failure_releases_the_wake_for_bounded_retry |
| Repeated failure | Dead-letter instead of infinite loop | test_repeated_failure_dead_letters_rather_than_looping |
| Completed wake scanned again | Do not fire again | test_completed_wakes_do_not_fire_again |
| Discharge or discontinuation | Cancel remaining work without deleting audit state | tests/test_course.py |
| Concurrent project demos | Keep clocks and simulated wake claims isolated | Public acceptance flows run concurrently |
| Managed-memory outage | Keep Firestore authoritative and report a bounded memory failure | test_course_creation_survives_a_managed_memory_failure |
| Cross-course memory lookup | Use an exact hash-derived scope with no patient identifier | test_course_scope_is_stable_and_does_not_expose_the_course_id; test_due_wake_recalls_managed_context |

## Standards boundary and known deviation

The implementation tests low-count suppression, analysis-period edges, rounding, diagnostic-only
isolates, and one isolate per patient and species.

Known deviation: CLSI selects the earliest isolate by collection date. The current curator keeps the
first isolate ingested. When reports arrive in collection order, these agree. With a delayed earlier
report, the patient still contributes exactly one isolate, so counts stay correct, but the selected
susceptibility profile can differ.

This is published in /conformance. Day Three does not claim certification or complete standards
conformance.

## Usability evidence without pretending it is user research

The project uses a first-time cognitive walkthrough rather than a claimed user study:

- Light mode is the default.
- Controls are numbered in causal order.
- Disabled states prevent actions before prerequisites exist.
- Every action explains what will happen and what happened.
- Synthetic data and simulated time are visible.
- Safety limits appear before the judge reaches the console.
- The guided flow requires no credentials or terminal.
- Accessibility checks cover both themes.

A practitioner usability study remains future work.

## What remains unproven

- Clinical effectiveness
- External validity across laboratory formats
- Production use with protected health information
- Practitioner usability or adoption
- Hospital integration and governance approval
- Complete CLSI conformance
- Cost savings, length-of-stay reduction, or mortality benefit
