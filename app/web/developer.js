(() => {
  "use strict";

  const form = document.querySelector("#key-form");
  const status = document.querySelector("#developer-status");
  const statusMirror = document.querySelector("#connection-status");
  const result = document.querySelector("#key-result");
  const keyOutput = document.querySelector("#api-key");
  const activeKeyInput = document.querySelector("#active-api-key");
  const expires = document.querySelector("#key-expires");
  const connectionCode = document.querySelector("#curl-example code");
  const workflowCode = document.querySelector("#workflow-example code");
  const copyButton = document.querySelector("#copy-key");
  const useKeyButton = document.querySelector("#use-key");
  const clearKeyButton = document.querySelector("#clear-key");
  const testButton = document.querySelector("#test-key");
  const revokeButton = document.querySelector("#revoke-key");
  const theme = document.querySelector("#theme-toggle");
  let apiKey = "";

  const templates = new Map([
    [connectionCode, connectionCode.textContent.replaceAll("SERVICE_URL", window.location.origin)],
    [workflowCode, workflowCode.textContent.replaceAll("SERVICE_URL", window.location.origin)],
  ]);

  const setStatus = (message, kind = "neutral") => {
    status.textContent = message;
    status.dataset.kind = kind;
    statusMirror.textContent = message;
    statusMirror.dataset.kind = kind;
  };

  const renderExamples = () => {
    const visibleKey = apiKey || "YOUR_API_KEY";
    for (const [node, template] of templates) {
      node.textContent = template.replaceAll("YOUR_API_KEY", visibleKey);
    }
  };

  const runButton = document.querySelector("#run-workflow");
  const runNote = document.querySelector("#run-workflow-note");
  const runResult = document.querySelector("#run-workflow-result");

  const reflectRunState = () => {
    if (!runButton) return;
    runButton.disabled = !apiKey;
    runNote.textContent = apiKey
      ? "Runs against your workspace only. Counts as one of your 25 model calls today."
      : "Load a key above first.";
  };

  const setActiveKey = (value) => {
    apiKey = String(value || "").trim();
    activeKeyInput.value = apiKey;
    renderExamples();
    reflectRunState();
  };

  const copy = async (value) => {
    try {
      await navigator.clipboard.writeText(value);
      return true;
    } catch {
      const area = document.createElement("textarea");
      area.value = value;
      area.style.position = "fixed";
      area.style.opacity = "0";
      document.body.append(area);
      area.select();
      const copied = document.execCommand("copy");
      area.remove();
      return copied;
    }
  };

  fetch("/developer/config")
    .then((response) => response.ok ? response.json() : Promise.reject())
    .then((config) => {
      // Test against the one mode that means "you cannot mint", not against a list of the
      // modes that mean you can. Checking for "invite_only" here left the button permanently
      // disabled the moment open issuance shipped.
      const disabled = config.issuance === "disabled";
      document.querySelector("#access-mode").textContent = disabled
        ? "Issuance is disabled"
        : config.issuance === "open"
          ? "Open to anyone, no invitation"
          : "Invite-only issuance is live";
      document.querySelector("#key-lifetime").textContent = config.ttl_hours + " hour lifetime";
      form.querySelector("button[type=submit]").disabled = disabled;
      if (disabled) {
        setStatus("Key creation is switched off on this deployment.", "error");
      }
      if (config.keys_per_day) {
        document.querySelector("#issuance-cap").textContent =
          "Up to " + config.keys_per_day + " keys a day from one network.";
      }
    })
    .catch(() => setStatus("Access configuration could not be loaded.", "error"));

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const submit = form.querySelector("button[type=submit]");
    submit.disabled = true;
    setStatus("Creating a scoped key...", "neutral");
    const data = new FormData(form);
    const payload = {
      tenant_id: String(data.get("tenant_id")).trim().toLowerCase(),
      label: String(data.get("label")).trim(),
      acknowledge_terms: data.get("acknowledge_terms") === "on",
    };
    try {
      const response = await fetch("/developer/keys", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload),
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body.detail || "The key could not be created.");
      setActiveKey(body.api_key);
      keyOutput.value = body.api_key;
      expires.textContent = new Date(body.expires_at).toLocaleString();
      result.hidden = false;
      setStatus("Key created and loaded into this browser session. Save it now.", "success");
      keyOutput.focus();
    } catch (error) {
      setStatus(error.message, "error");
    } finally {
      submit.disabled = false;
    }
  });

  // The workflow, run from the page rather than copied into a terminal, with the input on
  // screen. Showing only the output made the "every value is quoted" claim unverifiable: a
  // reader could not see the source text to check it against.
  const runDocument = document.querySelector("#run-document");
  const SAMPLE_REPORT = [
    "CULTURE AND SUSCEPTIBILITY REPORT",
    "Organism: Escherichia coli",
    "Specimen: Urine",
    "CEFTRIAXONE <=1 S",
    "CIPROFLOXACIN >2 R",
    "NITROFURANTOIN <=16 S",
  ].join("\n");
  const IDENTIFIER_LINE = "Patient: MARIA GONZALEZ    MRN 4472213";

  const escapeHtml = (value) => String(value).replace(/[&<>"]/g, (character) => (
    {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[character]
  ));

  if (runDocument) {
    runDocument.value = SAMPLE_REPORT;

    document.querySelector("#run-reset-document").addEventListener("click", () => {
      runDocument.value = SAMPLE_REPORT;
      runResult.hidden = true;
      reflectRunState();
    });

    document.querySelector("#run-add-identifiers").addEventListener("click", () => {
      if (runDocument.value.includes("MRN")) return;
      const lines = runDocument.value.split("\n");
      lines.splice(1, 0, IDENTIFIER_LINE);
      runDocument.value = lines.join("\n");
      runNote.textContent = "Now press send. Watch it refuse before the model is ever called.";
      runResult.hidden = true;
    });

    runButton.addEventListener("click", async () => {
      if (!apiKey) return;
      const document_text = runDocument.value.trim();
      if (document_text.length < 40) {
        runResult.innerHTML = "<p>That is too short to be a report. Send at least 40 characters.</p>";
        runResult.hidden = false;
        return;
      }
      runButton.disabled = true;
      runNote.textContent = "Sending...";
      runResult.hidden = true;
      try {
        const response = await fetch("/v1/intake", {
          method: "POST",
          headers: {"X-API-Key": apiKey, "Content-Type": "application/json"},
          body: JSON.stringify({
            document: document_text,
            subject_ref: "SUBJECT-101",
            acknowledge_deidentified: true,
          }),
        });
        const body = await response.json().catch(() => ({}));
        // FastAPI returns three shapes here: a string detail for our own refusals, a list of
        // field errors for schema validation, and no JSON at all for an unhandled 500. The
        // last one used to fall through to a bare "rejected", which told a reader nothing.
        let detail = "";
        if (typeof body.detail === "string") {
          detail = body.detail;
        } else if (Array.isArray(body.detail)) {
          detail = body.detail
            .map((item) => `${(item.loc || []).slice(-1)[0]}: ${item.msg}`)
            .join("; ");
        } else if (!response.ok) {
          detail = `The service returned HTTP ${response.status}. This is a fault on our side, `
            + "not something you did. Nothing was stored.";
        }

        if (response.status === 422 && detail.includes("identifier types")) {
          runResult.innerHTML = `
            <p class="run-refused"><b>Refused.</b> ${escapeHtml(detail)}</p>
            <p class="small muted">This happened before the model was called, so the identifiers
            were never sent anywhere. Your workspace is unchanged and this did not count against
            your daily allowance. Press <b>Reset text</b> and send it clean.</p>`;
          runResult.hidden = false;
          runNote.textContent = "Refused on purpose. That is the privacy boundary doing its job.";
          return;
        }
        if (!response.ok) throw new Error(detail || "The workflow call was rejected.");

        const rows = (body.isolate.susceptibilities || []).map((item) => `
          <li><b>${escapeHtml(item.drug)}</b> <span>${escapeHtml(item.interpretation)}</span>
          <q>${escapeHtml(item.quoted_text)}</q></li>`).join("");
        runResult.innerHTML = `
          <p><b>${escapeHtml(body.isolate.organism)}</b> from
          ${escapeHtml(body.isolate.specimen)}, read just now by
          <b>${escapeHtml((body.read_by || {}).model || "the model")}</b> on
          ${escapeHtml((body.read_by || {}).platform || "Vertex AI")}.</p>
          <ul class="run-rows">${rows}</ul>
          <p class="small muted">Compare each quote with the text you sent. Anything the model
          could not quote was dropped rather than guessed${
            body.dropped ? ` — ${body.dropped} value(s) dropped here` : ""}.</p>
          <p class="small muted">Your workspace is now at revision ${body.revision}, with
          ${body.cells_changed.length} cell(s) changed. The report text itself was not stored:
          <code>raw_document_persisted: ${body.raw_document_persisted}</code>. The public
          console is untouched.</p>`;
        runResult.hidden = false;
        runNote.textContent = "Done. Call GET /v1/antibiogram to see your own grid.";
      } catch (error) {
        runResult.innerHTML = `<p>${escapeHtml(error.message)}</p>`;
        runResult.hidden = false;
        runNote.textContent = "Something went wrong. Try again.";
      } finally {
        runButton.disabled = !apiKey;
      }
    });
  }

  copyButton.addEventListener("click", async () => {
    if (!apiKey) return;
    setStatus(await copy(apiKey) ? "API key copied." : "Copy failed. Select the key manually.",
      "success");
  });

  useKeyButton.addEventListener("click", () => {
    const value = activeKeyInput.value.trim();
    if (!value) {
      setStatus("Paste an API key before continuing.", "error");
      activeKeyInput.focus();
      return;
    }
    setActiveKey(value);
    setStatus("Key loaded for this page session. It has not been stored in the browser.", "success");
  });

  clearKeyButton.addEventListener("click", () => {
    setActiveKey("");
    keyOutput.value = "";
    result.hidden = true;
    setStatus("The key was cleared from this page session.", "success");
  });

  testButton.addEventListener("click", async () => {
    if (!apiKey) {
      setStatus("Create or load an API key before testing the connection.", "error");
      activeKeyInput.focus();
      return;
    }
    testButton.disabled = true;
    setStatus("Testing the key against this service...", "neutral");
    try {
      const response = await fetch("/v1", {headers: {"X-API-Key": apiKey}});
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body.detail || "The API rejected the key.");
      setStatus("Connection verified for tenant " + body.tenant + ".", "success");
    } catch (error) {
      setStatus(error.message, "error");
    } finally {
      testButton.disabled = false;
    }
  });

  revokeButton.addEventListener("click", async () => {
    if (!apiKey) {
      setStatus("Create or load an API key before revoking it.", "error");
      return;
    }
    revokeButton.disabled = true;
    setStatus("Revoking the key...", "neutral");
    try {
      const response = await fetch("/v1/key", {
        method: "DELETE",
        headers: {"X-API-Key": apiKey},
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body.detail || "The key could not be revoked.");
      setActiveKey("");
      keyOutput.value = "";
      result.hidden = true;
      setStatus("The key was revoked, cleared, and removed from both examples.", "success");
    } catch (error) {
      setStatus(error.message, "error");
    } finally {
      revokeButton.disabled = false;
    }
  });

  document.querySelectorAll("[data-copy-code]").forEach((button) => {
    button.addEventListener("click", async () => {
      const target = document.querySelector(button.dataset.copyCode);
      const copied = await copy(target.textContent);
      button.textContent = copied ? "Copied" : "Select and copy";
      window.setTimeout(() => { button.textContent = "Copy request"; }, 1600);
    });
  });

  theme.addEventListener("click", () => {
    const root = document.documentElement;
    const dark = root.dataset.theme !== "dark";
    root.dataset.theme = dark ? "dark" : "light";
    theme.textContent = dark ? "Use light mode" : "Use dark mode";
    theme.setAttribute("aria-pressed", String(dark));
  });

  renderExamples();
})();
