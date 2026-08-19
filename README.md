# Day Three: the review that should not get lost

**An agentic antimicrobial-stewardship console for small and critical-access hospital teams.**

Day Three turns synthetic microbiology reports into a privacy-protected local antibiogram, keeps a
multi-week antibiotic-course review ladder alive, and prepares a source-grounded reconciliation for
a pharmacist. Its background worker also filters official openFDA shortage data to the demo
formulary. The agent carries the context and the clock; the pharmacist keeps the decision.

> **New here?** Open the live app, press **Start from a clean slate**, and follow the numbered
> controls. Nothing in the demo uses real patient data.

- [Open the live application](https://day-three-109051079423.us-central1.run.app)
- [Read the judge evidence](https://day-three-109051079423.us-central1.run.app/judges)
- [Inspect machine-checkable conformance](https://day-three-109051079423.us-central1.run.app/conformance)

## Judge it in 90 seconds

1. Press **Start from a clean slate**.
2. Press **Load report** three times: watch a local cumulative antibiogram appear.
3. Run **Test a report with hidden instructions**: the prompt-injection text is quarantined.
4. Admit the synthetic course, advance **47 hours**, then **5 more hours**: the durable wake fires.
5. Press **Ask the day three question**: inspect the cited, pharmacist-reviewable draft.
6. Press **Test an unsupported number**: the verifier rejects the fabricated claim.

The interface explains each action before and after it runs. A first-time judge never needs a
terminal, credentials, or prior clinical knowledge.

## Verified evidence

| Gate | Reproducible result |
|---|---:|
| Live Gemini call you can trigger yourself | **graded against committed truth, on demand** |
| Wall-clock wake you can trigger yourself | **fires unattended, verified afterwards** |
| Deployed public acceptance flow | **18/18** |
| Standalone automated tests | **283 passed** |
| Recorded extraction fields | **29/29** |
| Shared-substrate exit test | **10/10** |
| Accessibility gate | **Pass: light and dark themes** |

The recordings, adjacent truth files, grading reports, tests, and acceptance script are committed.
These numbers describe the shipped synthetic fixtures. They are not estimates or clinical-outcome
claims.

## The problem

Small and critical-access hospitals may have less specialist time, fewer local isolates, and less
capacity to keep every review moving. A broad antibiotic may be started before a culture is final;
when the result arrives around the 48-to-72-hour review window, the evidence and the responsible
human still need to meet.

Day Three focuses on that coordination gap. It keeps the original report, uncertainty, local
cumulative context, wake status, and human-approval boundary together from intake to review.

## What happens end to end

| Stage | What the system does | What remains human-controlled |
|---|---|---|
| **1. Read** | Transcribes a synthetic microbiology report and removes direct identifiers before model review. | No real patient report enters this project. |
| **2. Curate** | Normalizes organism and susceptibility fields, preserves provenance, and rejects unsupported values. | Ambiguous or unsupported facts are not silently filled in. |
| **3. Aggregate** | Builds a deliberately small cumulative antibiogram with first-isolate handling and low-count suppression. | It is a demonstration view, not a certified laboratory report. |
| **4. Wait** | Registers five inpatient wakes through day 14 in durable state, then sleeps until work is due. At hour 48, a claimed wake invokes reconciliation against the latest persisted isolate. | A discharge transition cancels remaining inpatient wakes and arms a separate 30-day readmission check. The console clock is simulated and labelled; the separate wall-clock scanner and its public proof route are described under **Prove it yourself**. Missing culture data triggers one bounded recheck, never a guess or infinite loop. |
| **5. Reconcile** | Compares the final result with the synthetic course, local grid, and latest source-dated national shortage signal, then verifies and stores a cited draft automatically. | A pharmacist verifies local inventory and decides whether any clinical action is appropriate. |
| **6. Verify** | Rejects fabricated percentages, missing support, and claims outside the narrow task. | The service cannot prescribe, dose, order, page, or edit a chart. |

The public 18-step flow exercises stages 1 through 6, the first hour-48 wake, managed discovery,
and live capability invocation. Later inpatient wakes and the discharge/readmission transition are
implemented and tested, but intentionally omitted from the four-minute browser walkthrough.

## Prove it yourself

Two claims in the guided demo rest on something you cannot check from outside: the console
replays recorded model output, and the clock is simulated. Both are stated on screen, and both
now have a control that removes the caveat.

| Claim | Control | What it does |
|---|---|---|
| "Gemini really reads the scan" | **Read a lab report now** | Calls Gemini 3.5 Flash on Vertex AI when you press it, with the image and no source text, then grades the fresh answer against the same ground-truth file behind the published 29/29. |
| "The agent wakes itself" | **Start a real timer** | Registers a wake on wall-clock time in the `day-three-realtime` namespace. Only `day-three-realtime-wake-scan`, running every minute, can claim it. |

```bash
BASE=https://day-three-109051079423.us-central1.run.app

# A live model call, graded against committed truth.
curl -X POST -H "Content-Type: application/json"   -d '{"fixture":"ecoli_urine"}' "$BASE/day-three/live-intake"

# Register a wall-clock wake, then come back once it is due.
curl -X POST -H "Content-Type: application/json"   -d '{"delay_seconds":120}' "$BASE/day-three/realtime-proof"
curl "$BASE/day-three/realtime-proof/<proof_id>"
```

The live route accepts only a committed fixture name, never free text, so a credential-free paid
route cannot become a general model proxy. It runs under a durable daily budget shared across all
visitors, and it never writes to the antibiogram, so pressing it cannot alter the demo. Remaining
budget is public at `GET /day-three/live-intake` and on `/health`.

The wall-clock proof cannot be advanced by the simulated clock. Its record stores only observable
facts: registration time, due time, claim time, and the worker that claimed it.

## Architecture

The solid path below is the live stewardship workflow. The dotted path is optional onboarding
media generated at build time. It never sees reports and never participates in a clinical output.

```mermaid
%% Day Three, as built. One service, one database, one scheduler.
%% Kept deliberately small: this is the submission diagram, not an inventory.
flowchart TB
    B["Browser or API client<br/>no login needed"]
    V["Vertex AI<br/>Gemini 3.5 Flash reads the report<br/>Gemma 4 checks it for identifiers"]
    CR["Cloud Run: day-three<br/>us-central1, scales to zero<br/>Read, Curate, Schedule, Reconcile, Verify"]
    PH["Pharmacist<br/>reviews and decides.<br/>Nothing acts alone."]
    AR["Agent Registry<br/>8 entries. Other teams<br/>need the right scope."]
    FS[("Firestore<br/>the antibiogram, and<br/>work due days from now")]
    SCH["Cloud Scheduler<br/>checks for work<br/>that has come due"]

    B --> CR
    CR -->|"identifiers removed first"| V
    CR -->|"cited draft"| PH
    CR <-->|"scope checks"| AR
    CR <-->|"reads and writes"| FS
    SCH -->|"wakes it up"| CR
```

The nine logical roles are Python modules and route stages inside one `day-three` Cloud Run
service. They are not nine services. Four cross-department capabilities are also registered as
standard REST agents in Google Cloud Agent Registry and can be queried through the public
[`/day-three/registry/managed`](https://day-three-109051079423.us-central1.run.app/day-three/registry/managed) proof route. Together with four Runtime-projected agents, the live registry contains eight managed entries. There is no Pub/Sub hop. The deployed service runs as `sa-reason`,
while the separately provisioned identities document intended privilege boundaries rather than
pretending there is per-agent runtime isolation.

A real Agent Platform Memory Bank carries a deliberately small, deidentified course handoff
between sessions. Every lookup uses an exact hash-derived course scope, and neither patient
identifiers nor raw reports are stored there. Firestore remains the authoritative operational
ledger. The live [`/day-three/platform`](https://day-three-109051079423.us-central1.run.app/day-three/platform)
route reads Runtime, Identity, Gateway, Model Armor, and Memory Bank evidence from managed APIs.

Simulation clocks are namespaced per public evaluation, and simulated wake claims are filtered by
the owning project.

The shared spine worker also runs with simulation enabled, so it is not by itself proof that
anything fires on real time. Rather than describe it as one, Day Three ships a dedicated
wall-clock path: `day-three-realtime-wake-scan` runs every minute against
`/internal/scan-due-realtime`, bound to the separate `day-three-realtime` namespace and to
`RealClock`. Any visitor can register a wake there and watch real time, not a button press, fire
it.

- [Diffable Mermaid source](docs/architecture.mmd): the same architecture as text
- [Rendered SVG](docs/architecture.svg) and [PNG](docs/architecture.png) for submission pages
- [Recorded media provenance: prompts, model IDs, sizes, and SHA-256 hashes](app/web/media/bonus-media-provenance.json)
- [Bonus evidence map](BONUS_EVIDENCE.md)

### Why the Agent Runtimes are fail-closed

The four Agent Runtimes are real, each with its own Agent Identity, each bound to the gateway,
all verifiable at `/day-three/platform`. Direct invocation of them is refused, and that refusal
is deliberate.

Google protects Agent Runtime with a default agent-token policy. Invoking a Runtime directly from
this service requires a token-sharing exception that must pass an explicit security review. That
review has not been granted here, and the honest options were to disable a Google security default
so a demo looked better, or to leave it enforced and say so. This project leaves it enforced.

What that costs: the four Runtime resources are provisioned and governed, not exercised in the
request path. What it buys: nothing here depends on having weakened a default that exists to stop
exactly the kind of confused-deputy call an agent platform makes easy. The four cross-department
capabilities that *are* exercised live run as standard REST agents through Agent Registry, which
needs no such exception, and the console demonstrates a real scope denial and a real invocation
against them.

### Known conformance deviation

CLSI selects the earliest isolate by collection date. The current curator keeps the first isolate
ingested. These agree when reports arrive in collection order, but a delayed earlier report will
not replace the profile already counted. The patient still contributes exactly one isolate, so the
count remains correct; the selected susceptibility profile can differ. The public conformance route
discloses this limitation explicitly.

## Why each model is here

| Model | Narrow job | Boundary |
|---|---|---|
| **Gemini 3.5 Flash** | Structured transcription of synthetic reports. | Output is schema-validated and graded against adjacent truth. |
| **Gemma 4 MaaS** (`gemma-4-26b-a4b-it-maas`) | Second-pass privacy review after deterministic redaction. | It does not make clinical recommendations. |
| **Gemini 3.1 Flash Image** | Creates the optional abstract first-use briefing. | Build-time media only; no patient data or clinical values. |
| **Veo 3.1 Fast** | Creates the optional four-second motion briefing. | Muted, user-controlled, and outside the clinical path. |

The extra models are useful, visible, and auditable. They are not decorative claims attached to
the core workflow.

## Safety and data boundaries

- Synthetic composite reports only; no protected health information or real patient records.
- Deterministic patterns run before model-bound text; Gemma provides a second privacy review.
- Every shipped fixture identifier has regression coverage, including names, addresses, and case references.
- Recommendations must cite observable source fields; the verifier can abstain or reject.
- Every source reference must contain a nonempty quote; one valid reference cannot launder an empty one.
- Percentages are suppressed below the selected low-isolate threshold.
- openFDA is a national availability signal, refreshed at most once per 24 hours and never treated as local inventory or medical advice.
- No autonomous prescribing, dosing, messaging, paging, ordering, or chart mutation.
- The router persists a review escalation; it does not contact a clinician.

## Research and citations

Research changed the product, not just the pitch. National adoption data changed the framing from
"hospitals lack programs" to **teams need help executing consistently**. Critical-access studies
motivated durable handoffs. Low-isolate evidence led to suppression rather than false precision.

### Complete source list

1. [CDC: Core Elements for Small and Critical Access Hospitals](https://www.cdc.gov/antibiotic-use/media/pdfs/core-elements-small-critical-508.pdf) supports adaptable local practice and pharmacist leadership; it does not validate this product.
2. [CDC: Core Elements of Hospital Antibiotic Stewardship Programs](https://www.cdc.gov/antibiotic-use/hcp/core-elements/hospital.html) supports prospective audit, feedback, tracking, and reporting; Day Three does not perform preauthorization.
3. [CDC: Antibiotic Use and Stewardship in the United States, 2025 Update](https://www.cdc.gov/antibiotic-use/hcp/data-research/stewardship-report.html) reports 97% adoption of all seven Core Elements and 16% adoption of all six newer priorities among acute-care hospitals reporting in 2024; national self-reported context, not a CAH rate.
4. [CDC NHSN: Reducing Carbapenem Use in a Critical Access Hospital](https://www.cdc.gov/nhsn/au-case-examples/reducing-carbapenem-use.html) describes one CAH pairing an antibiogram with prospective telepharmacist review; this is a case example, not an outcome forecast.
5. [Ryder et al.: evaluation of 21 selected Iowa/Nebraska programs](https://pmc.ncbi.nlm.nih.gov/articles/PMC10594270/) reports bounded barriers including time/personnel, expertise, and electronic-record limitations; this is not national prevalence.
6. [Kassamali-Escobar et al.: process evaluation in 19 CAHs](https://pmc.ncbi.nlm.nih.gov/articles/PMC11574594/) reports staffing, turnover, and bandwidth barriers; this is not proof that software removes them.
7. [GRAM Project: global burden of bacterial antimicrobial resistance](https://pubmed.ncbi.nlm.nih.gov/39299261/) provides global problem context; Day Three never claims to prevent a quantified number of deaths.
8. [Low-isolate reliability analysis](https://pmc.ncbi.nlm.nih.gov/articles/PMC9927543/) shows instability in small cumulative samples and motivates low-count suppression.
9. [Review of antimicrobial de-escalation timing](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11776815/) supports review around 48 to 72 hours; the product still waits for final, supported evidence.
10. [Systematic review of stewardship cost evidence](https://aricjournal.biomedcentral.com/articles/10.1186/s13756-019-0471-0) provides historical context from included studies; its savings are not claimed as Day Three results.
11. [Systematic review and meta-analysis of de-escalation](https://www.mdpi.com/2813-0618/2/4/25) provides outcome context from included studies; its length-of-stay finding is not a product promise.
12. [Google Cloud Agent Registry overview](https://docs.cloud.google.com/agent-registry/overview) defines the managed discovery plane. Day Three has four registered capabilities plus four Agent Runtime resources with distinct Agent Identities. The live resource proof is at `/day-three/platform`.
13. [Agent Runtime](https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/runtime) documents the managed execution layer used by the four published roles.
14. [Agent Gateway overview](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/agent-gateway-overview) documents the Client-to-Agent gateway bound to every Runtime here.
15. [Model Armor prompt and response sanitization](https://docs.cloud.google.com/model-armor/sanitize-prompts-responses) documents the two live regional templates. Direct Runtime invocation currently remains fail-closed under Google's default agent-token protection while the required token-sharing exception receives explicit security approval.
16. [Agent Platform Memory Bank](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale) documents long-term memory attached to Agent Runtime. Day Three uses exact-scope, deidentified course handoffs only; Firestore remains authoritative.
17. [Google Cloud manual agent registration](https://docs.cloud.google.com/agent-registry/register-agents) documents standard REST registration through a Service resource and discovery through the projected Agent resource.
18. [openFDA Drug Shortages](https://open.fda.gov/apis/drug/drugshortages/) documents the daily public feed and warns against medical-care decisions; the watcher preserves that warning and requires pharmacist review.

For the source hierarchy, exact source-to-decision mapping, and rejected claims, read the
[research traceability ledger](docs/research-traceability.md).

## Use it through the API

The public web console remains a synthetic, credential-free judge experience. A separate `/v1`
surface lets an approved integration use the useful low-risk slice with an `X-API-Key`.

Day Three accepts only de-identified microbiology report text and a pseudonymous `SUBJECT-*`
reference. Production requests call Gemini 3.5 Flash through the same transcription, quote,
quarantine, and redaction path as the measured fixtures. Each key receives a separate calendar-year
antibiogram. Raw report text is not persisted, low-count cells remain suppressed, and no endpoint
can prescribe, dose, page, order, or change a chart.

Full provisioning, expiry, and rotation instructions are in [the beta API guide](docs/api-beta.md).

Invited developers can open [the live Developer page](https://day-three-109051079423.us-central1.run.app/developer), enter the invitation
code supplied by the project owner, and generate a tenant-scoped key that expires after seven days.
The plaintext key is shown once and remains only in page memory. The page includes a connection
test, a copyable project request, immediate revocation, and a link to the interactive OpenAPI schema.

Operators can also create a non-expiring key through Secret Manager:

```bash
cd app
python scripts/create_beta_key.py --tenant clinic_one --label "Clinic one"
```

The command prints the key once and a hash-only JSON value. Store the JSON as the
`BETA_API_KEY_HASHES` Secret Manager value, grant the Cloud Run service account Secret Accessor,
and expose it to the service as that environment variable. Never commit or place the plaintext key
in browser JavaScript.

```bash
curl -H "X-API-Key: $DAY_THREE_API_KEY" \
  https://day-three-109051079423.us-central1.run.app/v1

curl -X POST \
  -H "X-API-Key: $DAY_THREE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"document":"DE-IDENTIFIED CULTURE REPORT ...","subject_ref":"SUBJECT-001","acknowledge_deidentified":true}' \
  https://day-three-109051079423.us-central1.run.app/v1/intake

curl -H "X-API-Key: $DAY_THREE_API_KEY" \
  https://day-three-109051079423.us-central1.run.app/v1/antibiogram
```

Open `/docs`, select **Authorize**, and enter the same key to explore the schema. API keys are
revocable access credentials, not permission to send protected health information. This hackathon
beta remains a de-identified integration sandbox. A real clinical deployment still requires the
hospital's security, privacy, governance, and validation processes.

## Reproduce locally

Prerequisites: Python 3.12. New live model calls also require Application Default Credentials
for a Google Cloud project with Vertex AI enabled.

```bash
cd app
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
python -m pytest -q
python scripts/check_a11y.py
```

Run deterministically with the committed recordings:

```bash
export GOOGLE_CLOUD_PROJECT=agentic-fleet-2026
export SIM_MODE=true
export REPLAY_MODE=true
uvicorn service.main:app --reload
python scripts/demo_flow.py --url http://127.0.0.1:8000
curl -X POST -H "Content-Type: application/json" -d '{}' http://127.0.0.1:8000/exit-test
```

Deploying from `app/` with `bash deploy.sh` targets the independent Cloud Run service `day-three`.
The explicit empty JSON body in the exit-test request matters; a bodyless POST receives HTTP 411.
Managed discovery is reproducible with `python infra/register_agents.py`; the script creates or
updates the four standard REST entries. See `app/infra/README.md` for the editor and viewer IAM
commands and the public verification route.

## Repository map

- `app/day_three/`: project domain logic, including `grading.py` (one grader shared by the
  recorder and the live route), `live_budget.py` (durable cap on the paid public call), and
  `realtime_proof.py` (wall-clock due-work records)
- `app/spine/`: copied, reviewed runtime substrate required by this standalone project
- `app/service/`: public and operational routes
- `app/fixtures/`: synthetic inputs, adjacent truth, and recorded model outputs
- `app/tests/`: unit, integration, claim, safety, and UI-contract tests
- `app/scripts/`: recording, grading, accessibility, demo, and deployment verification
- `docs/research-traceability.md`: source-to-product decisions and rejected claims
- [Validation evidence](VALIDATION_EVIDENCE.md): research-to-test evidence, adversarial checks, and explicit limits
- [Project differentiation](PROJECT_DIFFERENTIATION.md): concrete separation from the other submission and shared-spine disclosure
- `SUBMISSION_KIT.md`: evidence-backed demo and Devpost copy
- `LICENSE`: MIT, with an explicit not-a-medical-device clause

## Disclosure

Built during the contest period with AI coding assistants. All public demonstration data is
synthetic. Model output is measured against committed truth and is never presented as clinical
advice. No government, healthcare organization, or standards body endorses this project.
