# Day Three social copy

Replace the video placeholder before publishing.

## LinkedIn version

On day three of a hospital stay, someone should check whether the antibiotic is still right. The
problem is not another unanswered dashboard. It is keeping the evidence, clock, and responsible
human connected until the review is due.

Day Three is a deployed antimicrobial-stewardship agent workflow for small and critical-access
hospital teams. It reads synthetic scanned microbiology reports with measured Gemini 3.5 Flash
output, builds a cumulative local antibiogram, registers a five-week wake ladder, and returns at the
48-hour review point. It prepares a quote-grounded draft for pharmacist review and stops. It cannot
prescribe, dose, change an order, or contact a clinician.

The most useful engineering result came from trying to break our own evidence boundary. We found
that an empty quote could pass a string-containment check. The Verifier now rejects empty and
whitespace-only references, and one valid source cannot launder an empty companion. We also publish
one CLSI deviation: out-of-order reports keep the first ingested isolate rather than the earliest
collected. Counts remain correct, but the selected susceptibility profile can differ.

Current proof:

- 230 standalone tests
- 18 of 18 public acceptance checks
- 29 of 29 recorded extraction fields
- 10 of 10 shared-substrate exit-test clauses
- Accessibility passing in light and dark themes

Built with Cloud Run, Firestore, Cloud Scheduler, Cloud Trace, Gemini 3.5 Flash, Gemma 4 MaaS,
Gemini 3.1 Flash Image, and Veo 3.1 Fast.

Live: https://day-three-109051079423.us-central1.run.app

Video: ADD PUBLIC VIDEO URL

Code: https://github.com/usv240/day-three

I created this post for the purposes of entering the All Things Agentic Hackathon.

#AllThingsAgenticHackathon

## Compact version

Day Three is a deployed stewardship agent that reads synthetic lab reports, builds a local
antibiogram, waits for the 48-hour review, and stops for pharmacist approval. Its Verifier rejects
unsupported and empty quotes. Proven by 240 tests and an 18 of 18 public flow.

Live: https://day-three-109051079423.us-central1.run.app

I created this post for the purposes of entering the All Things Agentic Hackathon.
#AllThingsAgenticHackathon
