# Why a 48-hour review needs a sleeping agent, not another dashboard

I created this post for the purposes of entering the All Things Agentic Hackathon.

A hospital does not need one more screen that someone must remember to open. It needs a bounded
worker that can register responsibility, go quiet, wake when evidence should exist, and stop at the
human who holds authority. That distinction shaped Day Three.

## The friction

Empiric antibiotic treatment often begins before a final culture result is ready. Around the
48-to-72-hour review window, that report can support a narrower choice, but limited stewardship time,
expertise, and local data make consistent follow-through difficult.

This is not a claim that hospitals have no stewardship programs. The
[CDC 2025 national update](https://www.cdc.gov/antibiotic-use/hcp/data-research/stewardship-report.html)
reports high adoption of the seven Core Elements among acute-care hospitals, but much lower adoption
of all six newer implementation priorities. The figures are national and self-reported, not a
critical-access-hospital rate.

Selected critical-access studies describe the operational constraint more directly. A
[21-program Iowa and Nebraska evaluation](https://pmc.ncbi.nlm.nih.gov/articles/PMC10594270/)
reported bounded barriers including time, personnel, expertise, and electronic-record limitations.
A [19-hospital process evaluation](https://pmc.ncbi.nlm.nih.gov/articles/PMC11574594/) described
staffing, turnover, and bandwidth problems. Neither study proves this product works. They explain
why durable coordination is worth building.

Day Three builds a cumulative local antibiogram from synthetic scanned microbiology reports, then
stands watch over a synthetic antibiotic course. It is not a prescriber. It prepares a
source-grounded review for a pharmacist and stops.

## A multi-week schedule in four minutes, honestly

The production architecture uses durable Firestore wakes claimed by a Cloud Scheduler worker. For
judging, an injectable clock compresses weeks into minutes. The interface labels every simulated
advance, while the production wall-clock path remains separate and documented.

That clock exposed an integration failure. Day Three and Sixty Days originally shared one simulation
clock document. Running both acceptance flows concurrently let one rehearsal move the other's time
and consume a wake. Each project now owns its own clock document, and simulated dispatch checks the
owning project before claiming a candidate. The shared production worker still scans wall-clock due
work across both projects.

The lesson was simple: deterministic demos are part of system design. If two judges can interfere
with each other, the demo is not deterministic.

## Fluent output is not evidence

Gemini 3.5 Flash reads degraded synthetic scan images through a transcription-first contract. A value
may enter structured state only when its exact representation can be quoted from the transcription.
Four recorded live calls are graded against adjacent truth: 29 of 29 susceptibility fields correct,
with no invented field.

The same principle governs recommendations. The guided demo asks the agent to invent a resistance
percentage for a low-count cell. The number is not in the source, so the Verifier rejects the
sentence.

Boundary testing then found a more serious problem inside that verifier. A source reference with an
empty quote passed the containment check because an empty string is contained in every string. A
claim could therefore carry a hollow reference and still be accepted. The fix now rejects empty and
whitespace-only quotes, and a valid reference cannot launder an empty companion reference. Three
regression tests preserve that invariant.

Prompt-injection handling remains a separate boundary. Instruction-shaped text inside a lab
document is quarantined as untrusted data before any model can interpret it as authority.

## Privacy failed on ordinary names before it became robust

Redaction initially covered common clinical labels and street addresses. Adversarial fixture review
found ordinary formats it missed: all-caps applicant names, hyphenated names, straight and
typographic apostrophes, lowercase applicant labels, FEMA-style case references, and PO boxes.

The deterministic layer now covers those forms, while negative controls preserve organism names,
susceptibility rows, and phrases such as "Name of disaster." Gemma 4 reviews the already-redacted
text for remaining person-name spans and fails closed.

This is stronger evidence than claiming the first design was safe. The important result is that each
failure became a narrow regression test.

## Standards need disclosed limits

The cumulative antibiogram suppresses percentages below 30 isolates, applies inclusive analysis
period boundaries, rounds results, excludes surveillance isolates, and counts one isolate per
patient and species.

Boundary probing also found one known deviation. CLSI selects the earliest isolate by collection
date. The current curator keeps the first isolate ingested. These are the same when reports arrive
in collection order. If a delayed report was collected earlier, the patient still contributes one
isolate, so the count stays correct, but the selected susceptibility profile can differ.

That limitation is published in the live conformance response and the README. A disclosed deviation
is more useful to a reviewer than a broad claim of perfect conformance.

## Three additional Google models, three bounded jobs

Gemma 4 reviews already-pattern-redacted text for person-name spans. Gemini 3.1 Flash Image creates
an optional abstract first-use illustration. Veo 3.1 Fast creates a four-second motion briefing.

The image and video models never see patient data, clinical values, drug names, or recommendations.
They do not enter the clinical path and do not autoplay. Every output has a public provenance record
with its exact model ID, prompt, location, byte count, and SHA-256 hash.

The point is not to collect model names. Each model has a narrow job that improves privacy or
first-time comprehension without gaining authority over a clinical decision.

## Shared substrate, different product

Day Three and Sixty Days reuse the same small durable spine: runs, wakes, claims, redaction,
verification, tracing, and Firestore adapters. That reuse is disclosed in both repositories.

The submitted products are otherwise different. Day Three has microbiology ingestion, cumulative
susceptibility logic, five inpatient wakes through day 14, a pharmacist boundary, CLSI-oriented conformance,
clinical fixtures, and its own Cloud Run service, repository, interface, and acceptance flow.
Sixty Days has none of those domain modules.

The shared spine is infrastructure reuse, not a claim that the submissions are independent stacks.

## What the product refuses to do

Day Three cannot prescribe, dose, approve, change an order, or contact a clinician. The synthetic
demonstration is not hospital-wide validation. Recorded fixture accuracy is not clinical
effectiveness. No clinician testimonial was invented, and no institution endorses the project.

Those limits are visible on the landing and judge pages rather than hidden in a footer.

## Reproduce and inspect it

The public repository contains the as-built architecture SVG, Mermaid source, local and cloud
spin-up instructions, recordings, adjacent truth, 244 standalone tests, an 18-step live acceptance
flow, accessibility checks, and the 10-clause shared-substrate exit test.

Live product: https://day-three-109051079423.us-central1.run.app

Judge evidence: https://day-three-109051079423.us-central1.run.app/judges

Public repository: https://github.com/usv240/day-three

Demo video: ADD PUBLIC YOUTUBE OR VIMEO URL BEFORE PUBLISHING

This project was built during the contest period with AI coding assistants, synthetic data, and no
institutional endorsement.
