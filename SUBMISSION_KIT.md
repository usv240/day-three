# Day Three: Submission Kit

The execution kit for the final submission artifacts. Product statements in this file must match
the deployed system and the current claim audit; aspirational beats are labelled conditional.

Scorecard context: the 17-step deployed flow, README and diagram are complete. The final video,
public-repository verification and Imagen asset remain. Bonus is specified in
`shared/BONUS_PLAN.md`.

---

## 1. Complete: the console's headline path runs on recorded real model output

Implemented and protected by the deployed acceptance flow:

- `btn-report`: fetch `/day-three/fixtures/{next in rotation}`, ingest with its recorded
  `extraction` and its `ground_truth` as the document; prepend to the stream a thumbnail of
  `/day-three/fixtures/{name}/image` (max-height 120px, click opens full size in a new tab) with
  the caption: "Read by Gemini 3.5 Flash. Recorded output, graded 29/29 against ground truth."
- `btn-hostile`: fetch `ecoli_urine_with_note` the same way.
- No hand-written `EXTRACTION` constant remains in the ingest path.
- Acceptance asserts the intake response came from a fixture recording and that the grid reflects
  the output. Current deployed result: 17/17.

## 2. The 4-minute video: shot list and exact narration

**Pre-flight checklist (do all, in order, before recording):**
1. `POST /sim/reset` then `POST /day-three/reset` (via console button "Start from a clean slate")
2. Fresh browser profile, 1440x900 window, no bookmarks bar, no extensions, DevTools closed
3. Theme: light (better projector legibility); one rehearsal pass of the full flow first
4. Second tab open: Cloud Run service page for `day-three`. Open Cloud Trace only if a fresh trace
   for the exact demo request is visible and its contents have been checked.
5. OBS or equivalent capturing the window plus microphone; one continuous take, no cuts inside
   beats 2 to 8 (Rules line 504 scores unedited execution)
6. `demo_flow.py --url` run minutes before, screenshot the 17/17 output for the repo

**Shot list.** Narration is verbatim; timings are targets with 15 seconds of slack total.

| Time | On screen | Say exactly |
|---|---|---|
| 0:00 | Landing page hero | "If you're admitted with a serious infection, treatment may start before the culture result is ready. About two days later, the lab can support a narrower choice. Small and critical access hospitals often have limited stewardship time and infectious-disease support, so that review can be delayed or missed. This is Day Three, running live on Google Cloud." |
| 0:20 | Scroll to console, click clean slate | "Everything you'll see is the real deployed system. The clock is simulated, and labelled; the same scheduler runs on wall-clock time in production." |
| 0:30 | Click "Drop a scanned lab report" twice; hover a grid cell | "A scanned culture report. Gemini 3.5 reads the page, transcribes it, and can only keep values it can quote from its own transcription. We measured it: twenty-nine of twenty-nine correct, zero invented. Watch the antibiogram build; this hospital has never had one. Cells with too few samples show no number at all; that's the CLSI standard, and it matters in a minute." |
| 1:05 | Click "Drop a report with hidden instructions" | "This report has an instruction hidden in it. Quarantined before any model reads it, and shown, not silently dropped. The lab data still went through." |
| 1:20 | Click "Admit a patient" | "A patient starts broad antibiotics. One agent now owns this whole five-week course: it registers every wake it will ever need, then goes to sleep. Sleeping costs nothing." |
| 1:35 | "Advance 47 hours"; then "Advance 5 more" | "Forty-seven hours pass. Nothing wakes; nothing is due. Five more, and the agent wakes itself. Nobody clicked it awake; the scheduler found it was due." |
| 1:55 | Click "Ask the day three question" | "The question nobody was there to ask: is the drug still right? It recommends narrowing, and every sentence is pinned to a quoted line of the lab report. It pages the pharmacist and stops. It cannot change an order." |
| 2:20 | Click "Make the agent invent a number" | "Now the part I care about most. We ask an agent to state a resistance rate for a cell with too few samples. There is no such number, and it invents one, and the Verifier rejects it, with the reason. A sentence cannot reach a human here unless its evidence is real. The same mechanism blocks instructions hidden in documents." |
| 2:45 | `/day-three/registry?department=infection_prevention` in URL bar; then the consume denial via console | "These agents are catalogued for the whole hospital. Infection Prevention discovers the antibiogram, and when it asks without the right scopes, it's refused, and the refusal is audited." |
| 3:05 | Cloud Run dashboard; optionally a verified fresh trace | "This is the Cloud Run service in us-central1, configured to scale to zero." If and only if the fresh trace is verified, add: "And this is the trace for the request you just watched." |
| 3:25 | `/conformance` page | "We couldn't get a rural pharmacist in the build window, so we did something better than claiming a review: we built to the published CLSI standard, and every rule links its implementation and its passing test. You can check us." |
| 3:40 | `/judges` page, slow scroll | "Eight implemented agent roles, a hundred and seventy-seven Day Three tests, two hundred and fifty-one across the shared application, and an exit test a judge can run with one request. Day Three supports the antibiotic review that limited teams can miss." |

**Upload:** YouTube, public, English captions on (auto then corrected), title
"Day Three - All Things Agentic Hackathon".

## 3. Architecture diagram

One diagram, rendered from this Mermaid source (render at 2x, export PNG for README and a still
in the video's 3:05 beat; also commit the .mmd). Legibility rule from UI_STANDARD: readable at
video resolution, max ~12 boxes visible, groups do the organizing.

```mermaid
flowchart LR
  subgraph public["Judge / Pharmacist (browser)"]
    UI[Site + Live Console]
  end

  subgraph gcp["Google Cloud: us-central1 (region-pinned, enforced in code)"]
    subgraph run["Cloud Run: day-three (min 0, max 3)"]
      API[FastAPI routes]
      SPINE[Spine: clock | runs | wakes | Verifier | quarantine]
      FLEET[Eight roles: Intake · Curator · CourseWatch · Reconciler · Drafter · Verifier · Router · Registrar]
    end
    FS[(Firestore\nruns · wakes · claims · antibiogram · courses)]
    SCHED[Cloud Scheduler\nevery minute -> /internal/scan-due]
    TRACE[Cloud Trace\nreasoning chains]
  end

  subgraph global["Vertex AI: global endpoint (Gemini 3.x is not offered regionally)"]
    GEM[Gemini 3.5 Flash\ntranscription-first extraction]
    GEMMA[Gemma 4 MaaS\nname review, spans only]
  end

  UI --> API --> SPINE --> FS
  SCHED --> API
  SPINE --> TRACE
  FLEET -->|"redaction gate: identifiers stripped BEFORE this boundary"| GEM
  FLEET --> GEMMA
```

Caption under the diagram, verbatim: "Storage and compute are pinned to us-central1 and enforced
by code. Gemini 3.x is served only globally; the redaction gate is why crossing that boundary is
acceptable."

## 4. README skeleton (repo root)

Order fixed; each bullet is a section with listed content. Reuse `/judges` text; do not rewrite.

1. Title + one-line tagline + live URL + 30-second GIF of the wake beat
2. The problem (3 short paragraphs from the landing page) + the four cited stats
3. What it does: the 8 implemented agent roles from the site
4. **Run it in five minutes**: the exact command table from `/judges` (tests, indexes, deploy,
   exit-test, demo_flow) — Rules line 425 scores this as proof of reproducibility
5. Architecture: the diagram + caption + link to `spine/TECHNICAL_DESIGN.md`
6. Measured model accuracy: the 29/29 table + how to regenerate (`record_intake.py`)
7. What it does not do (safety box, from the site, verbatim)
8. Findings and learnings: lift the six `details` items from `/judges`
9. Conformance: link + one-paragraph explanation of standards-instead-of-testimonials
10. Disclosure: spine built during submission period; AI coding assistants used; synthetic data
    only; no endorsements

## 5. Devpost submission text (paste-ready fields)

- **Category:** The Fortified Enterprise Fleet
- **Tagline:** The antibiotic review limited teams can miss.
- **Description:** landing page problem text + who it's for + the three how-it-works cards
- **Features/functionality:** 8-agent table + the three track mandates with how each is met
- **Tech:** Gemini 3.5 Flash (Vertex AI, measured 29/29), Gemma 4 MaaS, GenAI SDK,
  Cloud Run, Firestore, Cloud Scheduler, Cloud Trace/Logging, Artifact Registry, Cloud Build,
  OpenTelemetry. Pub/Sub and Secret Manager are not used.
- **Data sources:** synthetic Synthea-style patients; synthetic degraded scans with ground truth;
  CLSI M39 rules; public stewardship literature (cited)
- **Findings and learnings:** the six `/judges` findings, trimmed to ~200 words
- **Hosted URL:** `https://day-three-109051079423.us-central1.run.app`
- **Video URL / Repo URL:** filled at submission; repo private until then, then
  shared with testing@devpost.com and cloudhackathons@google.com if kept private
