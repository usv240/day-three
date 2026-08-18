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

fetch("/static/glossary.json").then((r) => r.json()).then((g) => { glossary = g; });

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

function log(agent, message, why = "", tone = "") {
  const event = document.createElement("div");
  event.className = `event ${tone}`;
  event.innerHTML = `<span class="agent">${agent}</span><div>${message}${
    why ? `<div class="why">${why}</div>` : ""}</div>`;
  stream.prepend(event);
  while (stream.children.length > 40) stream.lastChild.remove();
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
  const { data } = await api("/day-three/antibiogram");
  const table = $("#grid");
  const meta = $("#grid-meta");

  if (!data.cells || data.cells.length === 0) {
    table.innerHTML = "";
    meta.textContent = "No reports ingested yet.";
    return;
  }

  meta.textContent = `Revision ${data.revision}. ${data.organisms.length} organisms. ${data.cells.length} drug pairs.`;
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
       <div style="margin-top:6px">Read by Gemini 3.5 Flash. Recorded output, graded 29 of 29
       correct against ground truth.</div>`);

  log("intake", `${data.isolate.organism}, ${data.isolate.susceptibilities.length} results extracted.`,
      "Every result kept the exact text from the page. A value the model could not quote is dropped, never guessed.");

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
  if (FIXTURE_ROTATION.includes(name)) {
    const loaded = Math.min(fixtureIndex, FIXTURE_ROTATION.length);
    $("#btn-report").textContent = loaded < FIXTURE_ROTATION.length
      ? `Load report ${loaded + 1} of ${FIXTURE_ROTATION.length}`
      : "Three reports loaded";
    if (loaded >= FIXTURE_ROTATION.length) {
      $("#btn-report").disabled = true;
      $("#btn-admit").disabled = false;
      $("#btn-fabricate").disabled = false;
    }
  }
}

$("#btn-reset").addEventListener("click", async () => {
  await api("/sim/reset", {});
  await api("/day-three/reset", {});
  patientCounter = 0; courseRunId = null; latestPatientId = null; fixtureIndex = 0;
  $("#btn-report").disabled = false;
  $("#btn-report").textContent = "Load report 1 of 3";
  $("#btn-hostile").disabled = false;
  $("#btn-admit").disabled = true;
  $("#btn-advance-47").disabled = true;
  $("#btn-advance-5").disabled = true;
  $("#btn-reconcile").disabled = true;
  $("#btn-fabricate").disabled = true;
  stream.innerHTML = "";
  log("system", "Clean slate. Clock reset to real time, antibiogram cleared.");
  await refreshClock(); await refreshGrid();
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
  log("course watch", `Patient admitted on broad therapy. ${data.ladder.length} wakes registered, horizon ${data.horizon_days} days.`,
      data.ladder.map((w) => `${w.kind} at +${w.in_hours}h`).join(" &middot; "), "accept");
  log("course watch", "Agent is now asleep. It costs nothing while sleeping.");
  await refreshClock();
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

  log("reconciler", `<b>${data.headline}</b>`,
      data.notes.join(" ") || "", data.kind === "deescalate" ? "accept" : "");

  data.claims.forEach((claim) => {
    log("verifier",
        `<span class="chip ${claim.accepted ? "ok" : "bad"}">${claim.accepted ? "grounded" : "rejected"}</span> ${claim.text}`,
        claim.quoted ? `<span class="quote">${claim.quoted}</span>` : "",
        claim.accepted ? "accept" : "reject");
  });

  log("router", "Pharmacist-review escalation prepared. Waiting for sign off.",
      "Nothing was sent. The agent stops here and cannot change an order.");
});

$("#btn-fabricate").addEventListener("click", async () => {
  const { ok, data } = await api("/day-three/demo/fabricate", {});
  if (!ok) { log("verifier", data.detail || "Ingest a few reports first.", "", "reject"); return; }
  log("drafter", `Claimed: "${data.claim}"`);
  log("verifier",
      `<span class="chip bad">rejected</span> ${data.reason}`,
      data.teaching_note, "reject");
});

/* --- Boot --------------------------------------------------------------- */

refreshClock();
refreshGrid();
setInterval(refreshClock, 15000);
