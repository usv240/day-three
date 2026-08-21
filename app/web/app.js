/* Day Three console.
   Drives the real deployed API. Nothing here is simulated except the clock, which is labelled. */

const $ = (sel) => document.querySelector(sel);
const api = async (path, body) => {
  const options = body === undefined
    ? { method: "GET" }
    : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
  const response = await fetch(path, options);
  const text = await response.text();
  try { return { ok: response.ok, data: JSON.parse(text) }; }
  catch { return { ok: false, data: { detail: text.slice(0, 200) } }; }
};

/* --- Theme -------------------------------------------------------------- */

const toggle = $("#theme-toggle");
const themes = ["light", "dark"];
let theme = localStorage.getItem("theme");
if (!themes.includes(theme)) theme = "light";

function applyTheme() {
  document.documentElement.setAttribute("data-theme", theme);
  toggle.textContent = theme === "light" ? "Use dark mode" : "Use light mode";
  toggle.setAttribute("aria-pressed", String(theme === "dark"));
  localStorage.setItem("theme", theme);
}
toggle.addEventListener("click", () => {
  theme = themes[(themes.indexOf(theme) + 1) % themes.length];
  applyTheme();
});
applyTheme();

/* --- Info popovers ------------------------------------------------------ */

let glossary = {};
const popover = $("#popover");
let openTrigger = null;

fetch("/static/glossary.json?v=20260819-shell").then((r) => r.json()).then((g) => { glossary = g; });

function closePopover() {
  popover.hidden = true;
  if (openTrigger) { openTrigger.setAttribute("aria-expanded", "false"); openTrigger = null; }
}

document.addEventListener("click", (event) => {
  const trigger = event.target.closest(".info");
  if (!trigger) { if (!event.target.closest("#popover")) closePopover(); return; }

  event.preventDefault();
  const entry = glossary[trigger.dataset.info];
  if (!entry) return;
  if (openTrigger === trigger) { closePopover(); return; }

  popover.innerHTML = `
    <h4>${entry.title}</h4>
    <p>${entry.plain}</p>
    <p class="why"><b>Why it matters here:</b> ${entry.why}</p>
    <a href="${entry.url}">Source: ${entry.source}</a>`;
  popover.hidden = false;

  const rect = trigger.getBoundingClientRect();
  const width = Math.min(340, window.innerWidth - 32);
  popover.style.width = `${width}px`;
  let left = rect.left + window.scrollX;
  left = Math.max(16, Math.min(left, window.innerWidth - width - 16));
  popover.style.left = `${left}px`;
  popover.style.top = `${rect.bottom + window.scrollY + 8}px`;

  trigger.setAttribute("aria-expanded", "true");
  openTrigger = trigger;
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !popover.hidden) { const t = openTrigger; closePopover(); t?.focus(); }
});

/* --- Activity stream ---------------------------------------------------- */

const stream = $("#stream");
const activityToggle = $("#activity-toggle");
const ACTIVITY_PREVIEW_COUNT = 6;

function updateActivityDisclosure() {
  const count = stream.children.length;
  activityToggle.hidden = count <= ACTIVITY_PREVIEW_COUNT;
  activityToggle.textContent = stream.classList.contains("is-expanded")
    ? "Show latest activity only"
    : `View full activity history (${count})`;
}

activityToggle.addEventListener("click", () => {
  const expanded = stream.classList.toggle("is-expanded");
  activityToggle.setAttribute("aria-expanded", String(expanded));
  updateActivityDisclosure();
});

function log(agent, message, why = "", tone = "") {
  const event = document.createElement("div");
  event.className = `event ${tone}`;
  event.innerHTML = `<span class="agent">${agent}</span><div>${message}${
    why ? `<div class="why">${why}</div>` : ""}</div>`;
  stream.prepend(event);
  while (stream.children.length > 40) stream.lastChild.remove();
  updateActivityDisclosure();
}

/* --- Fixtures -----------------------------------------------------------
   Nothing here is hand-written. Each fixture is a real scanned image plus the output Gemini 3.5
   Flash actually produced for it, recorded by scripts/record_intake.py and graded 29/29 against
   ground truth. The console fetches both from the deployed service, so what you see ingested is
   genuine model output. */

const FIXTURE_ROTATION = ["ecoli_urine", "kleb_blood", "staph_wound"];
const HOSTILE_FIXTURE = "ecoli_urine_with_note";
let fixtureIndex = 0;

let patientCounter = 0;
let courseRunId = null;
let latestPatientId = null;
let demoStarted = false;
let hostileTested = false;
let reviewCompleted = false;
let fabricationTested = false;
// Set while a real-clock job is pending, so Reset can say it survives.
let activeProofId = null;

const workflowSteps = [...document.querySelectorAll("[data-workflow-step]")];
const guidedActionIds = ["btn-reset", "btn-report", "btn-hostile", "btn-admit", "btn-advance-47", "btn-advance-5", "btn-reconcile", "btn-fabricate", "btn-no-evidence"];

function updateWorkflowGuide() {
  let currentStep = 1;
  if (demoStarted) {
    if (fabricationTested) currentStep = 5;
    else if (fixtureIndex < FIXTURE_ROTATION.length || !hostileTested) currentStep = 2;
    else if ($("#btn-reconcile").disabled && !reviewCompleted) currentStep = 3;
    else currentStep = 4;
  }

  workflowSteps.forEach((step) => {
    const number = Number(step.dataset.workflowStep);
    const state = number < currentStep ? "complete" : number === currentStep ? "current" : "upcoming";
    step.dataset.state = state;
    const label = step.querySelector(".step-state");
    label.textContent = state === "complete" ? "Complete" : state === "current" ? "Current" : "Upcoming";
    if (state === "current") step.setAttribute("aria-current", "step");
    else step.removeAttribute("aria-current");
  });

  guidedActionIds.forEach((id) => $("#" + id).classList.remove("btn-primary"));
  let nextId = null;
  if (!demoStarted) nextId = "btn-reset";
  else if (fixtureIndex < FIXTURE_ROTATION.length) nextId = "btn-report";
  else if (!hostileTested) nextId = "btn-hostile";
  else if (!courseRunId) nextId = "btn-admit";
  else if (!$("#btn-advance-47").disabled) nextId = "btn-advance-47";
  else if (!$("#btn-advance-5").disabled) nextId = "btn-advance-5";
  else if (!reviewCompleted) nextId = "btn-reconcile";
  else if (!fabricationTested) nextId = "btn-fabricate";
  if (nextId) $("#" + nextId).classList.add("btn-primary");
}

async function loadFixture(name) {
  const { ok, data } = await api(`/day-three/fixtures/${name}`);
  return ok ? data : null;
}

/* --- Clock -------------------------------------------------------------- */

async function refreshClock() {
  const { ok, data } = await api("/sim/state");
  $("#clock-now").textContent = ok
    ? new Date(data.simulated_now).toUTCString().replace(" GMT", "")
    : "unavailable";
}

/* --- Grid --------------------------------------------------------------- */

function classFor(cell) {
  if (cell.percent_susceptible === null) return "s-none";
  if (cell.percent_susceptible >= 80) return "s-high";
  if (cell.percent_susceptible >= 50) return "s-mid";
  return "s-low";
}

async function refreshGrid(changed = []) {
  const table = $("#grid");
  const meta = $("#grid-meta");

  // The demo state lives on the server and is shared by everyone, so a visitor who arrives after
  // someone else has run the walkthrough would otherwise land on a finished antibiogram before
  // pressing anything. That destroys the one thing this panel is meant to show -- a grid being
  // built from nothing -- and makes a live workflow look pre-baked. Until this visitor starts a
  // run, show the empty state and say why, rather than someone else's leftovers. Reset clears the
  // server state for real, so nothing is being hidden.
  if (!demoStarted) {
    table.innerHTML = "";
    $("#grid-summary").innerHTML = "";
    $("#grid-disclosure").hidden = true;
    meta.textContent = "Nothing loaded yet. Press Reset demo to start from a clean slate.";
    return;
  }

  const { data } = await api("/day-three/antibiogram");

  if (!data.cells || data.cells.length === 0) {
    table.innerHTML = "";
    $("#grid-summary").innerHTML = "";
    $("#grid-disclosure").hidden = true;
    meta.textContent = "No reports loaded yet. Press Load report to add the first one.";
    return;
  }

  const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;
  meta.textContent = `Revision ${data.revision}. ${plural(data.organisms.length, "organism")}, ${plural(data.cells.length, "drug result")}.`;
  const changedKeys = new Set(changed.map((c) => `${c.organism}|${c.drug}`));

  const shortOrganism = (organism) => {
    const parts = organism.split(" ");
    return parts.length > 1 ? `${parts[0][0]}. ${parts.slice(1).join(" ")}` : organism;
  };
  const head = `<thead><tr><th scope="col">Drug</th>${
    data.organisms.map((organism) => `<th scope="col" aria-label="${organism}">${shortOrganism(organism)}</th>`).join("")}</tr></thead>`;

  const body = data.drugs.map((drug) => {
    const cells = data.organisms.map((organism) => {
      const cell = data.cells.find((c) => c.organism === organism && c.drug === drug);
      if (!cell) return `<td class="s-none">not tested</td>`;
      const key = `${organism}|${drug}`;
      const label = cell.percent_susceptible === null
        ? `n=${cell.tested}, too few`
        : `${cell.percent_susceptible}% S`;
      return `<td class="${classFor(cell)} ${changedKeys.has(key) ? "changed" : ""}"
        title="${cell.tested} tested, ${cell.susceptible} susceptible">${label}</td>`;
    }).join("");
    return `<tr><th scope="row">${drug}</th>${cells}</tr>`;
  }).join("");

const summary = data.organisms.map((organism) => {
    const observed = data.cells.filter((cell) => cell.organism === organism);
    const items = observed.map((cell) => {
      const label = cell.percent_susceptible === null
        ? `n=${cell.tested}, too few`
        : `${cell.percent_susceptible}% susceptible`;
      return `<li><b>${cell.drug}</b><span>${label}</span></li>`;
    }).join("");
    return `<section class="organism-card"><h4>${shortOrganism(organism)} <span>${observed.length} tested</span></h4><ul>${items}</ul></section>`;
  }).join("");
  $("#grid-summary").innerHTML = summary;
  $("#grid-disclosure").hidden = false;
  $("#grid-disclosure-label").textContent = `Inspect full ${data.drugs.length}-drug matrix`;
  table.innerHTML = head + `<tbody>${body}</tbody>`;
}

/* --- Actions ------------------------------------------------------------ */

async function ingestFixture(name, label) {
  const fixture = await loadFixture(name);
  if (!fixture) {
    log("intake", `Fixture ${name} unavailable on this deployment.`, "", "reject");
    return;
  }

  patientCounter += 1;
  latestPatientId = `pt_${patientCounter}`;
  const { ok, data } = await api("/day-three/intake", {
    artifact_id: `art_${patientCounter}_${name}`,
    patient_id: latestPatientId,
    document: fixture.ground_truth,
    extraction: fixture.extraction,
  });
  if (!ok) { log("intake", `Report rejected: ${data.detail}`, "", "reject"); return; }

  // Show the actual page. The scan is the point: it is rotated, unevenly lit and compressed,
  // and Gemini read it anyway.
  log("scan", `${label}`,
      `<a href="${fixture.image_url}" target="_blank" rel="noopener">
         <img src="${fixture.image_url}" alt="Scanned culture and susceptibility report"
              style="max-height:120px;border:1px solid var(--border);border-radius:6px;margin-top:6px">
       </a>
       <div style="margin-top:6px">Read by Google's Gemini AI. This is a saved reading, scored 29 of
       29 against the correct answers. Use the live check further down to watch it read a page
       from scratch.</div>`);

  log("intake", `Found ${data.isolate.organism}, with ${data.isolate.susceptibilities.length} drug results.`,
      "Every result had to be quoted word for word from the page. Anything the AI could not point to on the page is thrown away, never guessed.");

  if (data.redacted) {
    log("redaction", `<span class="chip ok">gate</span> ${data.redacted} identifier(s) removed before the model boundary.`,
        "Storage stays in us-central1; Gemini 3.x is served globally, so identifiers are stripped before crossing.");
  }
  if (data.quarantined.length) {
    log("quarantine", `<span class="chip bad">removed</span> ${data.quarantined.length} instruction-shaped line(s) before any AI read the document.`,
        data.quarantined[0].why, "reject");
  }
  if (data.dropped.length) {
    log("intake", `${data.dropped.length} value(s) dropped rather than guessed.`, data.dropped.join("; "));
  }
  log("curator", `Antibiogram updated to revision ${data.revision}. ${data.cells_changed.length} cell(s) changed.`,
      "Applied as a delta, so only what moved is highlighted.", "accept");
  await refreshGrid(data.cells_changed);
  if (name === HOSTILE_FIXTURE && data.quarantined.length) {
    hostileTested = true;
    $("#btn-hostile").disabled = true;
    if (fixtureIndex >= FIXTURE_ROTATION.length) $("#btn-admit").disabled = false;
  }
  if (FIXTURE_ROTATION.includes(name)) {
    const loaded = Math.min(fixtureIndex, FIXTURE_ROTATION.length);
    $("#btn-report").textContent = loaded < FIXTURE_ROTATION.length
      ? `Load report ${loaded + 1} of ${FIXTURE_ROTATION.length}`
      : "Three reports loaded";
    if (loaded >= FIXTURE_ROTATION.length) {
      $("#btn-report").disabled = true;
      $("#btn-admit").disabled = !hostileTested;
    }
  }
  updateWorkflowGuide();
}

$("#btn-reset").addEventListener("click", async () => {
  await api("/sim/reset", {});
  await api("/day-three/reset", {});
  patientCounter = 0; courseRunId = null; latestPatientId = null; fixtureIndex = 0;
  demoStarted = true; hostileTested = false; reviewCompleted = false; fabricationTested = false;
  $("#btn-report").disabled = false;
  $("#btn-report").textContent = "Load report 1 of 3";
  $("#btn-hostile").disabled = false;
  $("#btn-admit").disabled = true;
  $("#btn-advance-47").disabled = true;
  $("#btn-advance-5").disabled = true;
  $("#btn-reconcile").disabled = true;
  $("#btn-fabricate").disabled = true;
  $("#btn-no-evidence").disabled = true;
  stream.innerHTML = "";
  log("system", "Clean slate. Clock reset to real time, antibiogram cleared.");
  if (activeProofId) {
    log("course-watch", "Your real-clock job is still booked.",
      "Reset only clears the demo. It cannot touch a job on the real clock.");
  }
  await refreshClock(); await refreshGrid();
  stream.classList.remove("is-expanded");
  activityToggle.setAttribute("aria-expanded", "false");
  updateWorkflowGuide();
});

$("#btn-report").addEventListener("click", () => {
  const name = FIXTURE_ROTATION[fixtureIndex % FIXTURE_ROTATION.length];
  fixtureIndex += 1;
  return ingestFixture(name, "Scanned lab report");
});

$("#btn-hostile").addEventListener("click", () =>
  ingestFixture(HOSTILE_FIXTURE, "Scanned report with an instruction hidden in it"));

$("#btn-admit").addEventListener("click", async () => {
  const { ok, data } = await api("/day-three/course", {
    patient_id: latestPatientId || "pt_admitted",
    regimen: ["piperacillin-tazobactam", "vancomycin"],
    indication: "suspected sepsis",
  });
  if (!ok) { log("course", `Failed: ${data.detail}`, "", "reject"); return; }
  courseRunId = data.run_id;
  $("#btn-admit").disabled = true;
  $("#btn-advance-47").disabled = false;
  log("course watch", `Patient started on a broad antibiotic. ${data.ladder.length} check-ins booked over the next ${data.horizon_days} days.`,
      data.ladder.map((w) => `${w.kind.replace(/_/g, " ")} in ${w.in_hours} hours`).join(" &middot; "), "accept");
  log("course watch", "Nothing more to do until the first check-in is due. Waiting costs nothing.");
  await refreshClock();
  updateWorkflowGuide();
});

async function advance(hours, label) {
  const { ok, data } = await api("/sim/advance", { hours });
  if (!ok) { log("clock", `Failed: ${data.detail}`, "", "reject"); return; }
  await refreshClock();
  const mine = (data.woke || []).filter((w) => !courseRunId || w.run_id === courseRunId);
  if (mine.length === 0) {
    log("clock", `${label}. <span class="chip wait">nothing woke</span>`,
        "Correct. Nothing is due yet, so no agent runs and nothing is spent.");
  } else {
    mine.forEach((w) => {
      const domain = w.domain || {};
      log("course watch", `<span class="chip ok">woke by itself</span> ${w.kind}`,
          domain.detail || "Nobody triggered this. The scheduler found it was due.", "accept");
      if (domain.action === "pharmacist_review_draft_created") {
        log("reconciler", `<span class="chip ok">automatic draft</span> ${domain.recommendation_kind}`,
            `Grounded: ${domain.all_claims_grounded}. Pharmacist approval required.`, "accept");
      }
    });
  }
  if (hours === 47) {
    $("#btn-advance-47").disabled = true;
    $("#btn-advance-5").disabled = false;
  }
  if (hours === 5) {
    $("#btn-advance-5").disabled = true;
    $("#btn-reconcile").disabled = false;
  }
  updateWorkflowGuide();
}

$("#btn-advance-47").addEventListener("click", () => advance(47, "Advanced 47 hours"));
$("#btn-advance-5").addEventListener("click", () => advance(5, "Advanced 5 more hours"));

$("#btn-reconcile").addEventListener("click", async () => {
  // The lab result the patient's decision rests on is the same real fixture the grid was built
  // from: Gemini's recorded reading of the scan, quotes and all. Nothing here is hand-written,
  // which is exactly why the Verifier can ground the recommendation against it.
  const fixture = await loadFixture(FIXTURE_ROTATION[0]);
  if (!fixture) { log("reconciler", "Fixture unavailable.", "", "reject"); return; }

  const susceptibilities = {};
  for (const s of fixture.extraction.susceptibilities) {
    susceptibilities[s.drug.toLowerCase()] = `${s.interpretation}|${s.quoted_text}`;
  }

  const { ok, data } = await api("/day-three/reconcile", {
    patient_id: latestPatientId || "pt_admitted",
    regimen: ["piperacillin-tazobactam", "vancomycin"],
    organism: fixture.extraction.organism,
    susceptibilities,
    artifact_id: "art_reconcile",
    document: fixture.extraction.transcription || fixture.ground_truth,
  });
  if (!ok) { log("reconciler", `Failed: ${data.detail}`, "", "reject"); return; }

  // The stream prepends, so the last thing logged is the first thing read. Log this batch
  // backwards: the recommendation is the answer to the question that was just asked, and it
  // belongs at the top, with its evidence under it and the handoff last. Logged in the obvious
  // order it landed underneath its own supporting detail, and one more click pushed it out of
  // the four-entry preview entirely.
  log("router", "Pharmacist-review escalation prepared. Waiting for sign off.",
      "Nothing was sent. The agent stops here and cannot change an order.");

  [...data.claims].reverse().forEach((claim) => {
    log("verifier",
        `<span class="chip ${claim.accepted ? "ok" : "bad"}">${claim.accepted ? "grounded" : "rejected"}</span> ${claim.text}`,
        claim.quoted ? `<span class="quote">${claim.quoted}</span>` : "",
        claim.accepted ? "accept" : "reject");
  });

  log("reconciler", `<b>${data.headline}</b>`,
      data.notes.join(" ") || "", data.kind === "deescalate" ? "accept" : "");
  reviewCompleted = true;
  $("#btn-reconcile").disabled = true;
  $("#btn-fabricate").disabled = false;
  updateWorkflowGuide();
});

$("#btn-fabricate").addEventListener("click", async () => {
  const { ok, data } = await api("/day-three/demo/fabricate", {});
  if (!ok) { log("verifier", data.detail || "Ingest a few reports first.", "", "reject"); return; }
  log("drafter", `Claimed: "${data.claim}"`);
  log("verifier",
      `<span class="chip bad">rejected</span> ${data.reason}`,
      data.teaching_note, "reject");
  fabricationTested = true;
  $("#btn-fabricate").disabled = true;
  $("#btn-no-evidence").disabled = false;
  updateWorkflowGuide();
});

// Governance, in the browser. This used to be two curl commands, which meant the recording had
// to leave the page, and a judge had to trust a terminal they could not inspect. The calls are
// identical; only the surface changed.
const scopeResult = $("#scope-result");

// Registry responses are server-generated, but they carry a department name that arrived from
// this page, so they are escaped like any other untrusted string before reaching innerHTML.
const escapeAttr = (value) => String(value ?? "").replace(/[&<>"]/g, (c) => (
  {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]
));

async function askRegistry(scopes, button) {
  const others = [$("#btn-scope-denied"), $("#btn-scope-granted")];
  others.forEach((b) => { b.disabled = true; });
  scopeResult.hidden = true;
  try {
    const { ok, data } = await api("/day-three/registry/consume", {
      department: "infection_prevention",
      agent: "curator",
      granted_scopes: scopes,
    });
    if (!ok) throw new Error(data.detail || "The registry call failed.");
    const audit = data.audit || {};
    if (data.allowed) {
      const cells = (data.result && data.result.cells) ? data.result.cells.length : 0;
      scopeResult.innerHTML = `
        <p class="prove-headline">Allowed, and invoked.</p>
        <p>With <code>read:antibiogram</code>, ${escapeAttr(data.agent)} ran and returned the real
        grid: ${cells} cells across ${(data.result.organisms || []).length} organisms.</p>
        <p class="small muted">Audit ${escapeAttr(audit.audit_id || "")}</p>`;
    } else {
      scopeResult.innerHTML = `
        <p class="prove-headline run-refused">Refused, and recorded.</p>
        <p>${escapeAttr(data.reason || "")}</p>
        <p class="small muted">The refusal is written down too. Audit
        ${escapeAttr(audit.audit_id || "")}</p>`;
    }
    scopeResult.hidden = false;
  } catch (error) {
    scopeResult.innerHTML = `<p>${escapeAttr(error.message)}</p>`;
    scopeResult.hidden = false;
  } finally {
    others.forEach((b) => { b.disabled = false; });
  }
}

if ($("#btn-scope-denied")) {
  $("#btn-scope-denied").addEventListener("click", (e) => askRegistry([], e.currentTarget));
  $("#btn-scope-granted").addEventListener("click",
    (e) => askRegistry(["read:antibiogram"], e.currentTarget));
}

// The other half of "autonomous": what it does when the evidence it needs is not there.
// Every other control shows the agent acting on what it has. This one shows it deciding to
// wait, and then declining to wait again, which is the behaviour that keeps a missing lab
// result from becoming an endless loop.
$("#btn-no-evidence").addEventListener("click", async () => {
  const { ok, data } = await api("/day-three/wake-without-evidence", {});
  if (!ok) { log("course-watch", data.detail || "Could not run that wake.", "", "reject"); return; }
  if (data.recheck_registered) {
    log("course-watch",
        `Attempt ${data.attempt}: no culture back yet, so it booked one more check.`,
        `${data.detail} It did not recommend anything, and nothing was sent to a model.`);
  } else {
    log("course-watch",
        `<span class="chip bad">no second recheck</span> Attempt ${data.attempt}: still no culture.`,
        "It already rechecked once. It will not book another, so a missing result cannot become an endless loop. This is where a person picks it up.",
        "reject");
    $("#btn-no-evidence").disabled = true;
  }
  updateWorkflowGuide();
});

/* --- Boot --------------------------------------------------------------- */

refreshClock();
refreshGrid();
updateWorkflowGuide();
updateActivityDisclosure();
setInterval(refreshClock, 15000);

/* --- Independent proof ---------------------------------------------------
   Two controls that exist because the guided demo, honestly labelled, still leaves two claims
   resting on things a visitor cannot check: the model output is replayed, and the clock is
   simulated. These remove both caveats. Neither touches demo state. */

const liveCallButton = $("#btn-live-call");
const liveCallBudget = $("#live-call-budget");
const liveCallResult = $("#live-call-result");

function renderBudget(data) {
  if (!data || data.available === false) {
    liveCallBudget.textContent = "Live AI readings are switched off on this deployment.";
    if (liveCallButton) liveCallButton.disabled = true;
    return;
  }
  const left = data.live_calls_allowed_today - data.live_calls_used_today;
  const yours = data.your_calls_allowed_today - data.your_calls_used_today;
  liveCallBudget.textContent =
    `${left} of ${data.live_calls_allowed_today} readings left today across all visitors, ${yours} left for you.`;
  if (liveCallButton) liveCallButton.disabled = left <= 0 || yours <= 0;
}

async function refreshLiveBudget() {
  if (!liveCallBudget) return;
  const { ok, data } = await api("/day-three/live-intake");
  if (ok) renderBudget(data);
}

if (liveCallButton) {
  liveCallButton.addEventListener("click", async () => {
    liveCallButton.disabled = true;
    liveCallBudget.textContent = "Reading the page with Google's AI now. This takes 20 to 30 seconds…";
    log("intake", "Reading a lab report with Google's AI now. This is not a recording.");
    const { ok, data } = await api("/day-three/live-intake", { fixture: "ecoli_urine" });
    liveCallResult.hidden = false;
    if (!ok) {
      liveCallResult.innerHTML = `<p class="prove-fail">${data.detail || "The reading did not complete."}</p>`;
      liveCallBudget.textContent = "";
      log("intake", "The live reading was refused or did not finish.", data.detail || "", "warn");
      await refreshLiveBudget();
      return;
    }
    const invented = Object.keys(data.invented || {}).length;
    liveCallResult.innerHTML = `
      <p class="prove-headline">Read ${data.correct} of ${data.of} results correctly, and made up ${invented}.</p>
      <dl class="prove-facts">
        <div><dt>AI model</dt><dd>${data.model}</dd></div>
        <div><dt>Bacteria found</dt><dd>${data.organism}</dd></div>
        <div><dt>Answered in</dt><dd>${data.latency_ms} ms</dd></div>
        <div><dt>Our published score</dt><dd>${data.recorded_run.correct} of ${data.recorded_run.of}</dd></div>
      </dl>
      <p class="small muted">Read at ${new Date(data.called_at).toLocaleTimeString()}, and scored against the same list of correct answers we published.</p>`;
    renderBudget(data.budget ? { available: true, ...data.budget } : null);
    log("intake", `Live AI reading scored ${data.correct} of ${data.of}.`,
      "Same page, same question, and same scoring as the recorded run.");
  });
  refreshLiveBudget();
}

const realtimeButton = $("#btn-realtime-proof");
const realtimeStatus = $("#realtime-proof-status");
const realtimeResult = $("#realtime-proof-result");
let realtimePoll = null;

function renderProof(data) {
  realtimeResult.hidden = false;
  if (data.fired) {
    realtimeResult.innerHTML = `
      <p class="prove-headline">It woke itself up after ${Math.round(data.real_seconds_waited)} seconds of real waiting.</p>
      <dl class="prove-facts">
        <div><dt>Booked at</dt><dd>${new Date(data.registered_at).toLocaleTimeString()}</dd></div>
        <div><dt>Due at</dt><dd>${new Date(data.due_at).toLocaleTimeString()}</dd></div>
        <div><dt>Ran at</dt><dd>${new Date(data.fired_at).toLocaleTimeString()}</dd></div>
        <div><dt>Run by</dt><dd>${data.fired_by_worker || "the background service"}</dd></div>
      </dl>
      <p class="small muted">Nobody pressed anything to make this happen.</p>`;
    return;
  }
  const left = Math.max(0, Math.round(data.seconds_until_due));
  realtimeResult.innerHTML = `
    <p class="prove-headline">${data.status === "due" ? "Due now. Waiting for the background service to pick it up." : `Waiting. Due in ${left} seconds.`}</p>
    <p class="small muted">Reference ${data.proof_id}. You can close this page and check
      <code>/day-three/realtime-proof/${data.proof_id}</code> later.</p>`;
}

// The card promises "you can close this page and come back", and the proof id lived only in
// this script's memory, so any navigation silently lost it and the card reset to "nothing
// booked". The job itself was never affected -- it is a server-side record claimed by a
// scheduler -- but the page could no longer show you the one thing it told you to come back
// for. The id is small, not a credential, and only useful for reading one public record.
const PROOF_STORAGE_KEY = "day-three-realtime-proof";
const PROOF_STORAGE_MAX_AGE_MS = 60 * 60 * 1000;

function rememberProof(proofId) {
  try {
    localStorage.setItem(PROOF_STORAGE_KEY, JSON.stringify({id: proofId, at: Date.now()}));
  } catch { /* private browsing; the timer still runs, it just will not survive a reload */ }
}

function forgetProof() {
  try { localStorage.removeItem(PROOF_STORAGE_KEY); } catch { /* nothing to clean up */ }
}

function recallProof() {
  try {
    const raw = localStorage.getItem(PROOF_STORAGE_KEY);
    if (!raw) return null;
    const saved = JSON.parse(raw);
    // A day-old id would render a stale result to someone who never booked it today.
    if (!saved.id || Date.now() - saved.at > PROOF_STORAGE_MAX_AGE_MS) {
      forgetProof();
      return null;
    }
    return saved.id;
  } catch {
    forgetProof();
    return null;
  }
}

function watchProof(proofId) {
  if (realtimePoll) clearInterval(realtimePoll);
  const poll = async () => {
    const { ok, data: view } = await api(`/day-three/realtime-proof/${proofId}`);
    if (!ok) {
      clearInterval(realtimePoll);
      realtimePoll = null;
      forgetProof();
      return;
    }
    renderProof(view);
    if (view.fired) {
      clearInterval(realtimePoll);
      realtimePoll = null;
      activeProofId = null;
      forgetProof();
      realtimeButton.disabled = false;
      realtimeStatus.textContent = "It woke up on its own.";
      log("course-watch", `Woke up on its own after ${Math.round(view.real_seconds_waited)} real seconds.`,
        `Run by ${view.fired_by_worker || "the background service"}.`);
    }
  };
  poll();
  realtimePoll = setInterval(poll, 10000);
}

if (realtimeButton) {
  // Resume a job booked before this page load, including from another page on the site.
  const remembered = recallProof();
  if (remembered) {
    activeProofId = remembered;
    realtimeButton.disabled = true;
    realtimeStatus.textContent = "Still watching the job you booked.";
    watchProof(remembered);
  }

  realtimeButton.addEventListener("click", async () => {
    realtimeButton.disabled = true;
    realtimeStatus.textContent = "Booking a job on the real clock…";
    // 60s is the floor the server allows. Long enough that only real time can satisfy it,
    // short enough that a visitor -- or a four-minute demo -- reliably sees it fire.
    const { ok, data } = await api("/day-three/realtime-proof", { delay_seconds: 60 });
    if (!ok) {
      realtimeStatus.textContent = data.detail || "Could not book the timer.";
      realtimeButton.disabled = false;
      return;
    }
    activeProofId = data.proof_id;
    rememberProof(data.proof_id);
    realtimeStatus.textContent = `Booked. Due at ${new Date(data.due_at).toLocaleTimeString()}.`;
    log("course-watch", "Booked a job on the real clock.",
      "The demo fast-forward button cannot move this one.");

    watchProof(data.proof_id);
  });
}
