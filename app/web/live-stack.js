(() => {
  const header = document.querySelector("header.site .bar");
  if (!header || header.querySelector("[data-live-stack]")) return;

  // Tiers carry meaning: what runs in every request, what is provisioned and
  // independently verifiable, and what is auxiliary. The panel styles them
  // differently so visual weight matches evidentiary weight.
  const groups = [
    {
      tier: "live",
      title: "Live request path",
      note: "Deployed and serving this build. Console model output is replayed from recorded Gemini calls; /v1 calls Gemini live.",
      items: ["Gemini 3.5 Flash on Vertex AI", "Cloud Run", "Firestore", "Cloud Scheduler", "Cloud Trace and Logging", "Secret Manager"],
    },
    {
      tier: "managed",
      title: "Managed agent platform",
      note: "Read live at /day-three/platform",
      items: ["Agent Registry", "Agent Runtime and Agent Identity", "Agent Gateway", "Model Armor", "Memory Bank"],
    },
    {
      tier: "extra",
      title: "Additional Google AI",
      note: "Privacy review and recorded onboarding media",
      items: ["Gemma 4 MaaS", "Gemini 3.1 Flash Image", "Veo 3.1 Fast"],
    },
  ];

  const widget = document.createElement("div");
  widget.className = "live-stack";
  widget.dataset.liveStack = "";
  widget.innerHTML = `
    <button class="live-stack-trigger" type="button" aria-expanded="false" aria-controls="live-stack-panel">
      <span class="live-stack-dot" aria-hidden="true"></span><span>Live stack</span>
    </button>
    <div class="live-stack-panel" id="live-stack-panel" role="group" aria-label="Technology used by Day Three">
      <div class="live-stack-heading">
        <span class="live-stack-dot" aria-hidden="true"></span>
        <div><strong>Running on Google Cloud</strong><small>Verified services in this build</small></div>
      </div>
      ${groups.map((group) => `
      <div class="live-stack-group" data-tier="${group.tier}">
        <b>${group.title}</b>
        <span class="live-stack-groupnote">${group.note}</span>
        <ul>${group.items.map((item) => `<li>${item}</li>`).join("")}</ul>
      </div>`).join("")}
      <p class="live-stack-note">Technology used; no endorsement implied.</p>
    </div>`;

  const theme = header.querySelector(".theme-toggle");
  const actions = document.createElement("div");
  actions.className = "header-actions";
  header.append(actions);
  actions.append(widget);
  if (theme) actions.append(theme);

  const trigger = widget.querySelector(".live-stack-trigger");
  const close = () => { widget.classList.remove("is-open"); trigger.setAttribute("aria-expanded", "false"); };
  trigger.addEventListener("click", (event) => {
    event.stopPropagation();
    const open = !widget.classList.contains("is-open");
    close();
    if (open) { widget.classList.add("is-open"); trigger.setAttribute("aria-expanded", "true"); }
  });
  widget.addEventListener("click", (event) => event.stopPropagation());
  document.addEventListener("click", close);
  document.addEventListener("keydown", (event) => { if (event.key === "Escape") { close(); trigger.focus(); } });
})();
