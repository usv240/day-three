# Day Three: Submission Kit

The execution kit for the final submission artifacts. Product statements in this file must match
the deployed system and the current claim audit; aspirational beats are labelled conditional.

Scorecard context: the 18-step deployed flow, public README, standalone repository, submission-ready
architecture SVG, three additional Google model integrations, and the public build story are complete.
The final video and social publication remain external steps. Bonus evidence is specified in `BONUS_EVIDENCE.md`.

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
  the output. Current deployed result: 18/18.

## 2. The 4-minute video: shot list and exact narration

**Pre-flight checklist (do all, in order, before recording):**
1. `POST /sim/reset` then `POST /day-three/reset` (via console button "Start from a clean slate")
2. Fresh browser profile, 1440x900 window, no bookmarks bar, no extensions, DevTools closed
3. Theme: light (better projector legibility); one rehearsal pass of the full flow first
4. Second tab open: Cloud Run service page for `day-three`. Open Cloud Trace only if a fresh trace
   for the exact demo request is visible and its contents have been checked.
5. OBS or equivalent capturing the window plus microphone; one continuous take, no cuts inside
   beats 2 to 8 (Rules line 504 scores unedited execution)
6. `demo_flow.py --url` run minutes before, screenshot the 18/18 output for the repo

**Shot list.** Narration is verbatim; timings are targets with 15 seconds of slack total.

| Time | On screen | Say exactly |
|---|---|---|
| 0:00 | Landing page hero | "If you're admitted with a serious infection, treatment may start before the culture result is ready. About two days later, the lab can support a narrower choice. Small and critical access hospitals often have limited stewardship time and infectious-disease support, so that review can be delayed or missed. This is Day Three, running live on Google Cloud." |
| 0:20 | Scroll to console, click clean slate | "Everything you'll see is the real deployed system. The clock is simulated, and labelled; the same scheduler runs on wall-clock time in production." |
| 0:30 | Click **Load report** three times; hover a grid cell | "A scanned culture report. This is the output Gemini 3.5 produced for this page, recorded and graded: twenty-nine of twenty-nine correct, zero invented. It can only keep values it can quote from its own transcription. In a moment I will call the model live so you do not have to take the recording on trust. Watch the antibiogram build; this hospital has never had one. Cells with too few samples show no number at all; that's the CLSI standard, and it matters in a minute." |
| 1:05 | Click **Test a report with hidden instructions** | "This report has an instruction hidden in it. Quarantined before any model reads it, and shown, not silently dropped. The lab data still went through." |
| 1:20 | Click **Admit a patient on broad therapy** | "A patient starts broad antibiotics. One agent registers five inpatient wakes through day 14, then goes to sleep. A separate readmission check is armed only if discharge occurs. Sleeping costs nothing." |
| 1:35 | "Advance 47 hours"; then "Advance 5 more" | "Forty-seven hours pass. Nothing wakes; nothing is due. Five more, and the agent wakes itself. Nobody clicked it awake; the scheduler found it was due." |
| 1:55 | Click "Ask the day three question" | "The question nobody was there to ask: is the drug still right? It recommends narrowing, and every sentence is pinned to a quoted line of the lab report. It prepares a pharmacist-review escalation and stops. Nothing is sent, and it cannot change an order." |
| 2:20 | Click **Test an unsupported number** | "Now the part I care about most. We ask an agent to state a resistance rate for a cell with too few samples. There is no such number. It invents one, and the Verifier rejects it, with the reason. A sentence cannot reach a human here unless its evidence is real." |
| 2:40 | Scroll to **Two things you should not take on trust**; press **Read a scan live** | "Everything you have seen replayed a recorded model answer, and the page says so. That is a fair thing to be sceptical about, so here is the same scan going to Gemini on Vertex AI right now, with no source text, graded by the same file behind our published number. Live, on camera, at whatever it scores." |
| 3:05 | Press **Register a real-time wake**; read the due time aloud | "And the clock. That ladder ran on a simulated clock, labelled throughout. This registers a wake on the real clock that I cannot advance and cannot fake. A scheduled worker will claim it. I will come back to it." |
| 3:20 | `/day-three/registry/managed`, then the scope denial and the granted invocation | "Eight entries in Google Cloud Agent Registry, not a Python list. Our policy layer refuses Infection Prevention without the right scope and durably audits it; with the scope, it invokes the Curator. The background worker also filters official openFDA shortage data to this formulary." |
| 3:40 | `/day-three/platform`, then the fired wake, then `/judges` | "Four Runtime resources with distinct Agent Identities, one Gateway, two Model Armor templates. Direct Runtime invocation is refused, and we left it refused rather than disable a Google security default to make a demo look better. And there is the wake: fired on the real clock, by a worker, with nobody watching." |

**Upload:** YouTube, public, English captions on (auto then corrected), title
"Day Three - All Things Agentic Hackathon".

## 3. Architecture diagram

Use the committed submission-ready docs/architecture.svg for Devpost and the video still. It is
1600 by 900, accessible, and distinguishes the live clinical path from recorded onboarding
media. The canonical Mermaid source remains below. If Devpost requires PNG instead of SVG,
render it at 2x; keep the diagram readable at video resolution and under roughly twelve boxes.

```mermaid
flowchart LR
  subgraph public["Judge / Pharmacist (browser)"]
    UI[Site + Live Console]
  end

  subgraph gcp["Google Cloud: us-central1 (region-pinned, enforced in code)"]
    subgraph run["Cloud Run: day-three (min 0, max 3)"]
      API[FastAPI routes]
      SPINE[Spine: clock | runs | wakes | Verifier | quarantine]
      FLEET[Nine roles: Intake / Curator / CourseWatch / ShortageWatch / Reconciler / Drafter / Verifier / Router / Registrar]
    end
    FS[(Firestore\nruns / wakes / claims / antibiogram / courses)]
    SCHED[Shared Cloud Scheduler worker\nevery minute claims due Firestore wakes]
    TRACE[Cloud Trace\nreasoning chains]
    MEMORY[Agent Platform Memory Bank\ndeidentified handoff context]
  end
    REGISTRY[Google Cloud Agent Registry\n4 REST capabilities + 4 Runtime projections]
    RUNTIME[4 Agent Runtime resources\n4 distinct Agent Identities]
    GATEWAY[Client-to-Agent Gateway\n2 Model Armor templates]

  subgraph global["Vertex AI: global endpoint (Gemini 3.x is not offered regionally)"]
    GEM[Gemini 3.5 Flash\ntranscription-first extraction]
    GEMMA[Gemma 4 MaaS\nname review, spans only]
  end

  UI --> API --> SPINE --> FS
  SCHED --> FS
  SPINE --> TRACE
  API <--> REGISTRY
  SPINE --> MEMORY --> SPINE
  REGISTRY --- RUNTIME
  RUNTIME --- GATEWAY
  FDA[openFDA Drug Shortages] --> FLEET
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
3. What it does: the 9 implemented logical roles and 8 managed registry entries from the site
4. **Run it in five minutes**: the exact command table from `/judges` (tests, indexes, deploy,
   exit-test, demo_flow) because Rules line 425 scores this as proof of reproducibility
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
- **Features/functionality:** 9-role table + managed Agent Registry proof + the three track mandates
- **Tech:** Gemini 3.5 Flash (Vertex AI, measured 29/29), Gemma 4 MaaS, Gemini 3.1 Flash Image, Veo 3.1 Fast, GenAI SDK,
  Cloud Run, Firestore, Cloud Scheduler, Google Cloud Agent Registry, Agent Runtime, Agent Identity, Agent Gateway, Memory Bank, Model Armor, Cloud Trace/Logging, Artifact Registry, Cloud Build,
  OpenTelemetry. Pub/Sub is not used. Secret Manager stores the invitation code and expiring beta-key records.
- **Data sources:** synthetic composite patients; synthetic degraded scans with ground truth;
  official openFDA Drug Shortages; CLSI M39 rules; public stewardship literature (cited)
- **Findings and learnings:** the six `/judges` findings, trimmed to ~200 words
- **Hosted URL:** `https://day-three-109051079423.us-central1.run.app`
- **Video URL:** filled after the public upload
- **Repo URL:** `https://github.com/usv240/day-three` (public)

## 6. Final submission checklist

- [ ] Public YouTube or Vimeo video under four minutes with corrected English captions
- [ ] Live Cloud Run proof visible in the video
- [x] Public hosted project, no credentials required
- [x] Public standalone repository
- [x] Submission-ready architecture SVG plus canonical Mermaid source
- [x] Three additional Google model integrations with public prompts and hashes
- [x] 18/18 acceptance, 280 tests, accessibility, and 10/10 shared-substrate exit test
- [x] Credential-free live Gemini call on the public page, budget-capped and graded
- [x] Wall-clock wake proof a visitor can register and verify afterwards
- [x] LICENSE committed
- [x] Public build story published: https://dev.to/ujwal240/the-antibiotic-review-that-software-quietly-forgets-2ane
- [x] Public build story URL ready for the Day Three Devpost submission
- [ ] Publish docs/social-post.md with #AllThingsAgenticHackathon and add its public URL
- [ ] Final link and citation check immediately before Devpost submission
- [ ] Freeze the submitted revision and keep it available through judging
