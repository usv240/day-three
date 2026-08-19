# Day Three: Technical Design — As Built

**Track:** The Fortified Enterprise Fleet
**Product path:** `/` and `/judges`
**Shared substrate:** `spine/TECHNICAL_DESIGN.md`

This file describes the implementation, not the original concept. Executable tests and public
acceptance flows are the source of truth.

## 1. Product boundary

Day Three maintains a synthetic local antibiogram, holds a multi-week antibiotic-course wake
ladder, compares a supplied regimen with a final synthetic culture result and the local grid,
verifies every rendered recommendation against quoted sources, and routes a draft to a pharmacist
for approval.

It never diagnoses, prescribes, recommends a dose, changes an order, sends a clinical message
without review, or treats national availability as local inventory. The clinical fixtures are
synthetic; the shortage signal is current public openFDA data.

## 2. Actual architecture

```text
recorded synthetic lab scan
        -> Intake (transcription first + exact quote checks + redaction)
        -> Curator (CLSI-constrained first-isolate antibiogram delta)
        -> managed Agent Registry projection + local scoped invocation policy

synthetic course admission
        -> Course Watch (full wake ladder registered now)
        -> domain executor when Cloud Scheduler wakes it

persisted culture + regimen + allergy facts + local grid + official shortage snapshot
        -> Reconciler
        -> Drafter claims
        -> Verifier reject/retry/circuit break
        -> Router draft
        -> pharmacist approval boundary
```

Logical roles are modular Python components and route stages inside one Cloud Run service. They do
not communicate through Pub/Sub and do not run as separate Cloud Run services.

## 3. Implemented roles

| Role | Implementation and actual job |
|---|---|
| Intake | `app/day_three/intake.py`: Gemini extraction from synthetic scans; transcription-first quote guard |
| Curator | `app/day_three/antibiogram.py`: deterministic first-isolate aggregation and suppressed low counts |
| Course Watch | `app/day_three/course.py`: registers 48-hour through multi-week wakes |
| Shortage Watch | `app/day_three/shortages.py`: bounded daily openFDA refresh, formulary filter, provenance, and stale-data handling |
| Reconciler | `app/day_three/reconcile.py`: compares supplied facts; no dose or autonomous order action |
| Drafter | route-level construction of bounded recommendation claims |
| Verifier | `app/spine/verify.py`: source existence/support and contradiction checks |
| Router | persists a pharmacist-review escalation; never sends or executes it |
| Registrar | `app/day_three/managed_registry.py` reads four managed Google Cloud entries; `registry.py` adds local scopes and invocation policy |

"Nine roles" is a logical modularity claim. The process executes as one Cloud Run service under
`sa-reason`; five differentiated service accounts are provisioned boundaries, not per-role
runtime identities.

## 4. Recorded model boundary

- Gemini model: `gemini-3.5-flash` via the Google GenAI SDK on Vertex AI global.
- Four degraded synthetic culture-report calls are recorded once and replayed.
- Adjacent truth grades 29/29 fields, 0 wrong, 0 invented.
- Gemma `gemma-4-26b-a4b-it-maas` reviews possible person-name spans.
- Gemma evaluation measures 4/4 recall, 0 false positives, 0 leaks.

No demo rehearsal silently calls a model. The console replays, and recording scripts are explicit
paid paths.

One route deliberately breaks that pattern. `POST /day-three/live-intake` calls Gemini on demand,
credential-free, so a visitor can check that the recorded score is real instead of trusting it.
It is the same construction as `scripts/record_intake.py` -- `IntakeAgent(VertexClient(...))` with
no Gemma reviewer, image only, no source text -- so the fresh answer is graded by
`day_three/grading.py`, the same grader that produced the published figure. It accepts only a
committed fixture name, never free text, is bounded by a durable daily budget in
`day_three/live_budget.py`, and writes nothing to the antibiogram.

## 5. Wake behavior

Course Watch registers the complete ladder at admission. Cloud Scheduler calls
`/internal/scan-due`; the shared scheduler claims a due wake transactionally and passes it to a
domain executor. The result is written idempotently to `wake_actions/{wake_id}` before completion.

At hour 48 the executor loads the latest persisted structured isolate, combines it with the course
and latest openFDA snapshot, runs the Reconciler, verifies every claim, and stores a review draft.
If the culture is absent, it creates exactly one hour-72 recheck and refuses to guess; the second
miss stops. No path changes treatment, sends a message, or bypasses pharmacist approval.

The console clock is simulated, which leaves that behaviour resting on a clock the visitor moved.
`POST /day-three/realtime-proof` therefore books a due record on the wall clock in the separate
`day-three-realtime` namespace, and only `/internal/scan-due-realtime` -- driven every minute by
`day-three-realtime-wake-scan` -- can claim it. It does not use the shared wake table on purpose:
the spine worker scans that table unfiltered on its own simulated clock and completed the first
version of these with its own handler, leaving the proof silently unrecorded.

## 6. Data and verification

Firestore stores structured runs, steps, wakes, typed due-action results, isolates, antibiogram
cells, courses, claims, recommendations, access decisions, and source-dated shortage snapshots.
Raw synthetic scan transcriptions are not
persisted downstream.

Every recommendation sentence becomes a typed claim. A source-free or unsupported claim is
rejected; retry is bounded and circuit-breaks. Prompt-injection-shaped source text is quarantined
before any claim or tool route.

## 7. Clinical standard boundary

The implemented antibiogram behavior maps to CLSI M39 rules in the machine-checkable
`/conformance` report:

- first isolate per patient, organism, analysis period;
- first-isolate selection irrespective of body site;
- verified final results only;
- duplicate/replayed reports do not change counts;
- small denominators are suppressed; and
- source data and changes remain auditable.

The product does not claim formal CLSI certification or institutional validation.

## 8. Google Cloud topology

- Cloud Run: one standalone `day-three` service.
- Firestore: durable state.
- Cloud Scheduler: the existing `spine-scan-due` job invokes a shared spine worker that claims due
  wakes from the same Firestore substrate; it is not a second Day Three service.
- Cloud Scheduler: `day-three-shortage-refresh` calls an isolated wall-clock refresh route daily;
  it does not scan wakes or inherit the judge-controlled simulated clock.
- Cloud Scheduler: `day-three-realtime-wake-scan` calls `/internal/scan-due-realtime` every minute
  on wall-clock time, bounded to the `day-three-realtime` namespace, which is what makes the
  public wall-clock proof unattended rather than button-driven.
- Demo isolation: the service uses Firestore clock document `sim/clock-day-three`; simulated
  advances claim only wakes whose durable run belongs to `day-three`. The shared `spine-scan-due`
  worker is unfiltered, but it also runs with simulation enabled, so it is not evidence that
  anything fires on real time. That is why the wall-clock proof owns a separate scanner and its
  own due-work collection rather than riding the shared wake table.
- Cloud Trace/Logging: real configured telemetry.
- Vertex AI global: Gemini and Gemma MaaS.
- Google Cloud Agent Registry: four manually registered standard REST agents in `us-central1`,
  which the live registry exposes alongside four Runtime-projected entries, eight in total;
  the Cloud Run identity has viewer-only access for the public proof route.
- openFDA Drug Shortages: public operational input refreshed at most once per 24 hours.
- Artifact Registry and Cloud Build: container image build/deploy.

- Secret Manager: `day-three-beta-api-keys` and `day-three-beta-enrollment` are mounted as
  environment variables on the service; only hashes are stored, never a plaintext key.

Pub/Sub, GCS scan ingestion, Vector Search, and separate role services are absent. Four Agent
Runtime resources with distinct Agent Identities exist and are readable at `/day-three/platform`,
but they are not in the request path: direct invocation stays fail-closed under Google's default
agent-token protection, which this project chose not to disable.

## 9. Security and safety

- Synthetic clinical data only.
- Deterministic redaction plus Gemma span review before downstream model reasoning.
- Region-pinned storage/compute; global model boundary disclosed.
- Registry scopes are enforced and every access decision is durable. Supported Curator and
  Shortage Watch consumption invokes the capability; unsupported adapters say so explicitly.
- Router stops at pharmacist review.
- Claims and public counts are pinned by regression tests.

## 10. Verification

```powershell
cd app
python -m pytest tests -q
python scripts/check_a11y.py
python scripts/demo_flow.py --url https://SERVICE.run.app
curl.exe -X POST -H "Content-Type: application/json" -d "{}" https://SERVICE.run.app/exit-test
```

The last verified public Day Three flow before the current revision was 18/18 and the shared exit
test was 10/10. Rerun both after every deployment; do not carry those numbers forward by prose.
