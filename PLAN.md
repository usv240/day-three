# Day Three: Plan

> **As-built correction (August 8):** Shortage Watch entries below are design-only. No feed
> polling code was built, it is not demonstrated on the site, and it is deliberately absent from
> the public Registry. See `AS_BUILT.md`; executable code and tests are authoritative.

**Track:** The Fortified Enterprise Fleet
**Hosted project:** `https://day-three-109051079423.us-central1.run.app`
**Role in portfolio:** flagship. Gets the best week. Never cut.
**Original build window:** August 10 to 16. Product deployed; final submission video remains.

> **On day three, someone should ask whether the antibiotic is still right.
> Limited stewardship teams can miss it.**

---

## 1. The problem in plain words

You arrive at a small hospital with an infection. Nobody knows yet which bacteria you have,
because growing it in the lab takes about two days. So the doctor makes an educated guess and
starts a powerful, broad antibiotic that kills many things at once.

Two days later the lab result comes back. Now everyone knows exactly which bacteria it is, and
usually a narrower, cheaper, safer antibiotic would work better.

At a large hospital, a specialist stewardship team may review a patient around day three and say
"switch this one to something narrower." Small and critical access hospitals often have less
staff time and infectious-disease support, so that review can be delayed or missed.

---

## 2. Evidence

| Claim | Source |
|---|---|
| 4.71M deaths were associated with bacterial AMR in 2021 and 1.14M were attributable to it; an estimated 39.1M attributable deaths are cumulative across 2025 to 2050 | [Naghavi et al., The Lancet, 2024, GRAM](https://pubmed.ncbi.nlm.nih.gov/39299261/) |
| An evaluation covered 21 Iowa/Nebraska critical-access stewardship programs that self-identified possible gaps; among 20 answering the barriers item, 15 cited limited time/personnel, 8 limited infectious-disease or stewardship expertise, and 5 electronic-record limitations | [Ryder et al., primary paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC10594270/) |
| CDC says many critical access hospitals adapt treatment recommendations from nearby hospitals or regional collaboratives when local expertise or data are limited | [CDC Core Elements for Small and Critical Access Hospitals (PDF)](https://www.cdc.gov/antibiotic-use/media/pdfs/core-elements-small-critical-508.pdf) |
| CDC says that in most critical access hospitals a pharmacist, usually onsite, provides stewardship leadership | [CDC Core Elements for Small and Critical Access Hospitals (PDF)](https://www.cdc.gov/antibiotic-use/media/pdfs/core-elements-small-critical-508.pdf) |
| CDC identifies prospective audit and feedback and preauthorization as priority hospital stewardship interventions; local antibiograms separately support empiric-treatment decisions | [CDC Core Elements, hospital](https://www.cdc.gov/antibiotic-use/hcp/core-elements/hospital.html) |
| In 2024, 97% of acute-care hospitals reported all seven Core Elements, while 16% reported all six newer implementation priorities; these are national self-reported survey figures, not CAH-specific rates | [CDC, Antibiotic Use and Stewardship in the United States, 2025 Update](https://www.cdc.gov/antibiotic-use/hcp/data-research/stewardship-report.html) |
| A CDC CAH case example paired local resistance data with prospective telepharmacist review; it is an implementation example, not a promised product outcome | [CDC NHSN case example](https://www.cdc.gov/nhsn/au-case-examples/reducing-carbapenem-use.html) |
| A 2024 year-long process evaluation in 19 CAHs reported staffing shortages, turnover, and lack of bandwidth; 17 collected local data and none completed a full improvement cycle within the study year | [Kassamali-Escobar et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC11574594/) |
| De-escalation is recommended at 48 to 72 hours based on clinical status and microbiology | [PMC11776815](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11776815/) |
| Across the US studies in one systematic review, stewardship programs averaged 732 dollars in savings per patient | [Systematic review, Antimicrobial Resistance and Infection Control](https://aricjournal.biomedcentral.com/articles/10.1186/s13756-019-0471-0) |
| One systematic review reported a mean 4.6-day reduction in hospital stay after de-escalation, without increased mortality in the included studies | [Systematic review](https://www.mdpi.com/2813-0618/2/4/25) |
| A US analysis estimated an annual incremental cost of 1,383 dollars per infection with selected antibiotic-resistant organisms | [Peer-reviewed summary of Thorpe et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC6606543/) |
| Antibiotic resistant infection treatment costs doubled since 2002, now exceeding 2 billion dollars annually | [Health Affairs](https://www.healthaffairs.org/doi/10.1377/hlthaff.2017.1153) |

**Prior art status: very high confidence the space is open.** Six dedicated search passes.
The academic literature calls for AI stewardship ([systematic review](https://pmc.ncbi.nlm.nih.gov/articles/PMC11047419/),
[Lancet Infectious Diseases 2025](https://www.thelancet.com/journals/laninf/article/PIIS1473-3099(25)00313-5/abstract))
and our documented searches found no directly comparable end-to-end product. A healthcare-only
agent hackathon in 2026 produced 24 agent projects and none of the reviewed entries touched
antimicrobial resistance, stewardship or antibiograms. These are search findings, not proof of
market-wide absence.

---

## 3. The Unlikely Hero

**Marta is a synthetic composite persona:** a contract pharmacist serving a 25-bed critical
access hospital with limited infectious-disease support. She splits her time across facilities
and has never seen this hospital's own resistance patterns because nobody has compiled them.

Rules.md line 488 asks whether the project was built for an Unlikely Hero outside standard
corporate roles. Marta represents that answer and is explicitly labelled as a composite on the
landing page; she is not presented as an interviewed or validated real person.

---

## 4. The twist

Every other project reads data. **Day Three manufactures the knowledge that does not exist, then
stands watch with it.**

Layer one: it builds the local antibiogram this hospital has never had, from scanned lab reports,
and keeps mutating it as new results arrive.

Layer two: it sleeps, per patient, and wakes at hour 48 to ask the question nobody is there to ask.

---

## 5. Rubric mapping

| Rules.md criterion | What we do |
|---|---|
| Innovation and Operational Utility, 40 percent (line 480) | Supports timely review with local susceptibility evidence in settings with constrained stewardship resources. Published reviews report an average 732-dollar saving in their US studies and a mean 4.6-day stay reduction after de-escalation; neither figure is promised as this product's outcome. |
| **Track mandate: agents cataloged for cross-department use (line 378)** | Agent Registry with versions, owners, contracts and scopes. Four real cross department consumers. Filmed |
| **Track mandate: context across weeks of asynchronous operations (line 378)** | Course Watch spans roughly five weeks per patient across five wake points; the antibiogram accumulates over months |
| **Track mandate: production data, compliance, data sovereignty, security (line 378)** | Region-pinned resources with a build test, an enforced redaction boundary, scoped in-process components, break-glass audit and a denied cross-boundary read filmed |
| Multi-Agent Nexus: is the task complex enough (line 488) | Eight implemented agents with distinct jobs, multiple triggers and a data plane that must be built before reasoning can happen. Shortage-feed monitoring remains design-only and is not counted or catalogued. |
| Multi-Agent Nexus: Unlikely Hero (line 488) | Marta, a clearly labelled synthetic composite of a part-time contract pharmacist |
| Architecture: separation of concerns (line 498) | Each implemented agent has one job and declared inputs and outputs; the deployed system is one Cloud Run service, not separate service accounts per agent |
| Architecture: failure tolerance and hallucination recovery (line 498) | Verifier rejects unsourced claims on camera; circuit breaker after three rejections |
| Architecture: state management (line 494) | Firestore checkpointing, lease based claiming, idempotent tools, resumable mid run |
| Demo: proof of action (line 504) | Unedited live run: antibiogram mutating, agent waking at hour 52, Verifier overruling |
| Demo: documentation (line 506) | Architecture diagram, reproducible README, judge mode page, Cloud Run and Vertex AI proof |
| Bonus: additional Google models (line 518) | Gemma 4 redaction, Gemini 3.1 Flash Image onboarding, and Veo 3.1 Fast motion briefing are implemented, publicly served, hash-recorded, and tested. Media stays outside the clinical path. |

---

## 6. The fleet

| Agent | Job |
|---|---|
| **Intake** | Gemini 3.5 multimodal reads scanned culture and susceptibility reports into structured isolate records |
| **Curator** | Maintains the living antibiogram to CLSI M39 rules: first isolate per patient irrespective of body site, n under 30 suppressed, diagnostic isolates only |
| **Course Watch** | One agent per antibiotic course. Sleeps and wakes repeatedly across the whole course, not once. See section 6a |
| **Reconciler** | Compares current regimen against identified organism, susceptibilities, local antibiogram, allergies and renal function |
| **Shortage Watch (design only; not built or catalogued)** | Proposed monitor for FDA and ASHP shortage feeds. The implemented Reconciler can accept a supplied shortage list, but no code polls a feed. |
| **Drafter** | Writes the recommendation, every sentence cited to a susceptibility result or a guideline section |
| **Verifier** | Adversarial. Rejects any claim without a resolvable source reference |
| **Router** | Persists a pharmacist-review escalation, holds for sign off, never sends or executes |
| **Registrar** | Publishes, versions and scopes every agent in the Agent Registry so other departments can discover and consume them. See section 6b |

### 6a. Why the horizon is weeks, not 48 hours

Rules.md line 378 requires this track to demonstrate context maintained "across weeks of
asynchronous operations". An antibiotic course is genuinely weeks long, and stewardship has four
more decision points after hour 48. Course Watch wakes at every one of them.

| Wake | Clinical question | Why it matters |
|---|---|---|
| Hour 48 to 72 | Is the drug still right now the organism is known | De-escalation, the CDC named intervention |
| Day 5 to 7 | Can this patient move from IV to oral | High value, removes line days and shortens stay |
| Day 7, 10, 14 | Has the stop date passed | Prolonged therapy beyond 15 days is a documented stewardship target |
| Discharge | Does the outpatient prescription match the inpatient rationale | The most common place a narrow decision silently reverts to broad |
| Day 30 | Did this patient return with a resistant organism | Closes the loop back into the antibiogram, which mutates as a result |

A single patient's Course Watch therefore lives for roughly five weeks, sleeping between wakes,
resuming after crashes, and carrying context the whole way. The antibiogram itself accumulates over
months. That is what "weeks of asynchronous operations" means and we now demonstrate it literally.

### 6b. Cross department catalog

Rules.md line 378 requires demonstrating how agents are "cataloged for cross-department use", and
line 874 asks to show how an organization can discover them. The catalog is not decorative here,
because three agents produce output other departments genuinely need:

| Agent published | Consuming department | What they get |
|---|---|---|
| **Curator** | Infection Prevention | The living antibiogram, for outbreak and resistance trend detection |
| **Curator** | Pharmacy and Therapeutics | Local susceptibility evidence for formulary decisions |
| **Shortage Watch (future)** | Supply Chain | Proposed capability only; absent from the public registry until a real feed monitor is built and tested |
| **Intake** | Quality and Reporting | Structured isolates for NHSN antimicrobial resistance reporting |

Each entry carries a version, an owner, a declared input and output contract, its required scopes,
and a changelog. **On camera we show a second department discovering the Curator in the registry
and consuming it**, which turns a compliance checkbox into a demo beat.

### 6c. Production data posture (as built)

Rules.md line 378 asks about interacting with production data without violating compliance, data
sovereignty or security. We use synthetic data, deliberately and stated openly, and we run it
through production grade controls. What we demonstrate is the controls, not the data:

- **Location posture:** Cloud Run, Firestore and build resources use `us-central1`; the Vertex model
  endpoints used by this build are available at `global`. No Cloud Storage bucket is part of the
  build, so the product does not claim that every byte or model endpoint is in one region.
- **Redaction boundary:** the Gemma gate is enforced by an assertion that hard fails any step
  attempting to reach Gemini with unredacted text
- **Identity boundary:** five differentiated service accounts are provisioned, while the single
  deployed Cloud Run service currently executes as `sa-reason`. This is a provisioned boundary,
  not per-agent runtime isolation; `sa-reidentify` remains the distinct re-identification boundary.
- **Demonstrable denial:** the Registry refuses and audits cross-department consumption without the
  required scope. We do not substitute that application-level check for an IAM-denial claim.

The line we say out loud: **synthetic data, production controls.** That is honest under Rules.md
line 1111 and it answers the mandate directly.

---

## 7. Safety position, stated on camera and on the site

- Every output is a **draft recommendation requiring licensed pharmacist approval**
- The agent never prescribes, never modifies an order, never acts without a human
- Every recommendation cites the specific susceptibility result that justifies it
- All data is synthetic: Synthea generated patients, public resistance data, no real patient
  information at any point
- The antibiogram is a screening aid, not a substitute for a CLSI compliant laboratory report

This section appears verbatim in the "What it does not do" block required by
`shared/UI_STANDARD.md` section 5.

---

## 8. Demo script, four minutes

| Time | Beat |
|---|---|
| 0:00 to 0:20 | Zero jargon, second person. "Treatment may start before the culture is ready. About two days later the lab can support a narrower choice. Limited stewardship teams can miss that later review." |
| 0:20 to 0:55 | Load three deployed scan fixtures and their genuine recorded Gemini output. The antibiogram reaches revision three; every small cell suppresses the percentage under the CLSI rule. |
| 0:55 to 1:15 | Load the hostile-note fixture. Instruction-shaped text is quarantined while the clinical table remains usable. |
| 1:15 to 1:50 | Admit a patient on broad empiric therapy. Course Watch registers the five-wake ladder. Advance to hour 47 (nothing fires), then hour 52 (the de-escalation review is executed and recorded). |
| 1:50 to 2:25 | Reconciler proposes a narrower drug from the recorded report, grounds every claim, and labels the result as requiring pharmacist approval. No approval is fabricated. |
| 2:25 to 2:50 | **The Verifier rejects a claim on camera:** a fabricated percentage for a cell suppressed under the n-under-30 rule. |
| 2:50 to 3:20 | Infection Prevention discovers Curator. Consumption without `read:antibiogram` is refused and audited; the same request with the scope succeeds. |
| 3:20 to 3:40 | Open `/conformance`: four CLSI-derived rules, each mapped to code and a passing test. |
| 3:40 to 4:00 | Show the live URL, Cloud Run revision and a confirmed trace identifier, then the as-built architecture. |

Shortage Watch is not built or demonstrated. The Reconciler can accept a supplied shortage list,
but no code polls a feed and the public registry intentionally excludes the proposed agent.

Narrated in a real voice. Rules.md line 1097 says narration beats a silent screencast.

---

## 9. Original build schedule (historical, not current build status)

| Day | Work |
|---|---|
| Aug 10 | Data model, Firestore schema, Synthea fixture generation, synthetic lab report rendering and scanning |
| Aug 11 | Intake agent: multimodal parse to structured isolates, with source spans preserved |
| Aug 12 | Curator: CLSI M39 antibiogram construction and mutation, live grid UI |
| Aug 13 | Watch and Reconciler: the 48 hour mechanism on the spine clock; idempotency tests |
| Aug 14 | Drafter, Verifier wiring, Router and pharmacist approval flow. Shortage Watch was proposed but not built. |
| Aug 15 | Landing page, judge mode, glossary, light and dark, mobile pass, accessibility pass |
| Aug 16 | Deploy, capture Google Cloud proof, record video, write README and architecture diagram |

---

## 10. Risks

| Risk | Mitigation |
|---|---|
| Clinical logic is wrong and a judge with medical background notices | Get one pharmacist to review before Aug 16. Restrict scope to organism-drug mismatch, which is unambiguous. Never make dosing recommendations |
| Synthetic data looks fake | Render lab reports to PDF, print, photograph at an angle under poor light. Real scan artifacts |
| Non clinical judge cannot follow | The 20 second jargon free cold open, tested on someone with no medical background before recording |
| GEAP products unavailable or too heavy for 150 dollars | Verify on Aug 10. Fallback is plain ADK plus Cloud Run plus Firestore, which already satisfies every mandatory requirement in Rules.md line 370 |
| Multimodal parse accuracy on scanned tables | Evals with deliberately degraded fixtures; Verifier catches what the parser gets wrong; UI shows confidence and the source region |

---

## 11. Submission checklist

- [ ] Category selected: The Fortified Enterprise Fleet
- [ ] Hosted URL live and left running through October 1
- [ ] Public repo, or private with access to testing@devpost.com and cloudhackathons@google.com
- [ ] README with reproducible spin up instructions
- [ ] Architecture diagram, legible at video resolution
- [ ] Demo video under 4 minutes, public on YouTube, English, Google Cloud proof visible
- [ ] Text description including features, technologies, data sources, findings and learnings
- [ ] Judge mode page live at /judges
- [ ] Blog post published, stating it was created for this hackathon
- [ ] Social post with the hashtag
- [x] Additional Google models disclosed: Gemma 4, Gemini 3.1 Flash Image, Veo 3.1 Fast
