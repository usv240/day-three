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
without review, or polls a shortage feed. All fixture data is synthetic.

## 2. Actual architecture

```text
recorded synthetic lab scan
        -> Intake (transcription first + exact quote checks + redaction)
        -> Curator (CLSI-constrained first-isolate antibiogram delta)
        -> Registry (scoped catalogue record)

synthetic course admission
        -> Course Watch (full wake ladder registered now)
        -> direct due-action record when Cloud Scheduler wakes it

final recorded culture + regimen + allergy facts + local grid
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
| Reconciler | `app/day_three/reconcile.py`: compares supplied facts; no dose or autonomous order action |
| Drafter | route-level construction of bounded recommendation claims |
| Verifier | `app/spine/verify.py`: source existence/support and contradiction checks |
| Router | persists a pharmacist-review escalation; never sends or executes it |
| Registrar | `app/day_three/registry.py`: publishes scoped catalogue metadata |

“Eight roles” is a logical modularity claim. The process executes as one Cloud Run service under
`sa-reason`; five differentiated service accounts are provisioned boundaries, not per-role
runtime identities.

## 4. Recorded model boundary

- Gemini model: `gemini-3.5-flash` via the Google GenAI SDK on Vertex AI global.
- Four degraded synthetic culture-report calls are recorded once and replayed.
- Adjacent truth grades 29/29 fields, 0 wrong, 0 invented.
- Gemma `gemma-4-26b-a4b-it-maas` reviews possible person-name spans.
- Gemma evaluation measures 4/4 recall, 0 false positives, 0 leaks.

No demo rehearsal silently calls a model. Recording scripts are explicit paid paths.

## 5. Wake behavior

Course Watch registers the complete ladder at admission. Cloud Scheduler calls
`/internal/scan-due`; the shared scheduler claims a due wake transactionally, writes an
idempotent `wake_actions/{wake_id}` due-action record, and completes the wake.

That action says a review is due. It does not invent missing clinical facts or automatically
change treatment. The demo supplies the final recorded lab result and invokes reconciliation
after the unattended wake. This is the honest boundary between autonomous scheduling and a
human-reviewed clinical recommendation.

## 6. Data and verification

Firestore stores structured runs, steps, wakes, due-action records, isolates, antibiogram cells,
courses, claims, recommendations, and registry records. Raw synthetic scan transcriptions are not
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
- Cloud Trace/Logging: real configured telemetry.
- Vertex AI global: Gemini and Gemma MaaS.
- Artifact Registry and Cloud Build: container image build/deploy.

Pub/Sub, Secret Manager integration, GCS scan ingestion, Vector Search, a shortage-feed poller,
separate role services, and per-agent runtime identities are absent.

## 9. Security and safety

- Synthetic clinical data only.
- Deterministic redaction plus Gemma span review before downstream model reasoning.
- Region-pinned storage/compute; global model boundary disclosed.
- Registry scopes are enforced, but they are governance metadata rather than dynamic dispatch.
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

The last verified public Day Three flow before the current revision was 17/17 and the shared exit
test was 10/10. Rerun both after every deployment; do not carry those numbers forward by prose.
