# Why a 48-hour review needs a sleeping agent, not another dashboard

I created this post for the purposes of entering the All Things Agentic Hackathon.

A hospital does not need one more screen that someone must remember to open. It needs a bounded
worker that can register responsibility, go quiet, wake when new evidence should exist, and stop at
the human who holds authority. That distinction shaped Day Three.

## The friction

Empiric antibiotic treatment often begins before a final culture result is ready. Around the
48-hour mark, that report can support a narrower choice, but limited stewardship time and
infectious-disease support make consistent review difficult. Day Three does not claim that every
hospital misses that review. It addresses the operational gap documented in public stewardship
research: constrained time, personnel, expertise, and local data.

The first part of the product builds a cumulative local antibiogram from synthetic scanned
microbiology reports. The second stands watch over a synthetic antibiotic course. The agent is not
a prescriber. It prepares a source-linked review for a pharmacist and stops.

## Five weeks in four minutes, honestly

The production architecture uses durable Firestore wakes claimed by a Cloud Scheduler worker. For
judging, an injectable clock compresses weeks into minutes. The interface labels every simulated
advance, and the production wall-clock path remains documented separately.

That clock exposed an unexpected integration failure. Day Three and a second submission originally
shared one simulation-clock document. Running both acceptance flows concurrently let one rehearsal
move the other's time and consume a wake. The fix was not another test delay. Each project now owns
its own clock document, and simulated wake dispatch checks the owning project before claiming a
candidate. Both live flows now pass in parallel.

## Fluency is not evidence

Gemini 3.5 Flash reads degraded synthetic scan images using a transcription-first contract. A value
may enter structured state only when its exact representation can be quoted from the transcription.
Four recorded live calls are graded against adjacent truth: 29 of 29 susceptibility fields correct,
with no invented field.

The same evidence principle governs the recommendation path. A deliberately fabricated resistance
percentage reaches the Verifier during the guided demo. The number does not exist in its cited
source, so the sentence is rejected. After repeated rejection, the run pauses for human review
rather than looping forever.

Prompt-injection defense uses the same idea. Instruction-shaped text inside a lab document is
quarantined as data before a model can treat it as authority.

## Three additional Google models, three bounded jobs

Gemma 4 reviews already-pattern-redacted text for person-name spans. It returns spans only and fails
closed. Gemini 3.1 Flash Image creates a non-data-bearing first-use illustration. Veo 3.1 Fast
creates a four-second motion briefing. The last two never see patient data, never enter the clinical
path, never autoplay, and never generate a clinical fact.

Every media output is checked in beside a public provenance manifest containing the exact model ID,
prompt, location, byte count, and SHA-256 hash. The point is not to collect model names. It is to
make a first-time workflow easier to understand without weakening the boundary around clinical
content.

## What the product refuses to do

Day Three cannot prescribe, dose, approve, change an order, or contact a clinician. The antibiogram
suppresses percentages when sample counts are too small. The synthetic demonstration is not
hospital-wide validation, and no clinician testimonial is invented. Those limitations are visible
on the landing and judge pages instead of hidden in a disclaimer footer.

## Reproduce it

The public repository contains the as-built architecture SVG, Mermaid source, local and cloud
spin-up instructions, recording scripts, ground truth, 17-step live acceptance flow, accessibility
gate, and shared-substrate exit test. The public judge page maps claims to exact files and tests.

Live product: https://day-three-109051079423.us-central1.run.app

Public repository: https://github.com/usv240/day-three

Demo video: ADD PUBLIC YOUTUBE OR VIMEO URL BEFORE PUBLISHING

This project was built during the contest period with AI coding assistants, synthetic data, and no
institutional endorsement.
