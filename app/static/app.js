// ── Tab-Navigation ────────────────────────────────────────────────────────
document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => {
      t.classList.remove("active");
      t.setAttribute("aria-selected", "false");
    });
    document.querySelectorAll(".tab-content").forEach((c) => c.classList.remove("active"));
    tab.classList.add("active");
    tab.setAttribute("aria-selected", "true");
    document.getElementById(`tab-${tab.dataset.tab}`).classList.add("active");
  });
});

// ── DOM-Referenzen: Workflow ──────────────────────────────────────────────
const questionInput     = document.querySelector("#question");
const runButton         = document.querySelector("#run-button");
const statusLine        = document.querySelector("#status-line");
const intentValue       = document.querySelector("#intent-value");
const confidenceValue   = document.querySelector("#confidence-value");
const reviewValue       = document.querySelector("#review-value");
const hallucinationValue  = document.querySelector("#hallucination-value");
const hallucinationWarning = document.querySelector("#hallucination-warning");
const unsupportedClaims = document.querySelector("#unsupported-claims");
const answerValue       = document.querySelector("#answer-value");
const redactedValue     = document.querySelector("#redacted-value");
const sourcesValue      = document.querySelector("#sources-value");
const traceValue        = document.querySelector("#trace-value");
const metricsValue      = document.querySelector("#metrics-value");

// ── DOM-Referenzen: Evaluation ────────────────────────────────────────────
const evalQuestion      = document.querySelector("#eval-question");
const evalAnswer        = document.querySelector("#eval-answer");
const evalContext       = document.querySelector("#eval-context");
const evalButton        = document.querySelector("#eval-button");
const evalStatus        = document.querySelector("#eval-status");
const evalFaithfulness  = document.querySelector("#eval-faithfulness");
const evalRelevancy     = document.querySelector("#eval-relevancy");
const evalOverall       = document.querySelector("#eval-overall");
const evalExplanation   = document.querySelector("#eval-explanation");

// ── DOM-Referenzen: Debug ─────────────────────────────────────────────────
const debugQuery   = document.querySelector("#debug-query");
const debugButton  = document.querySelector("#debug-button");
const debugStatus  = document.querySelector("#debug-status");
const debugCount   = document.querySelector("#debug-count");
const debugMode    = document.querySelector("#debug-mode");
const debugChunks  = document.querySelector("#debug-chunks");
const debugLatency = document.querySelector("#debug-latency");
const debugResults = document.querySelector("#debug-results");

// ── Hilfsfunktionen ───────────────────────────────────────────────────────
const renderStack = (container, items, emptyText, renderer) => {
  container.innerHTML = "";
  if (!items.length) {
    container.textContent = emptyText;
    container.classList.add("muted");
    return;
  }
  container.classList.remove("muted");
  items.forEach((item) => {
    const div = document.createElement("div");
    div.className = "stack-item";
    div.innerHTML = renderer(item);
    container.appendChild(div);
  });
};

const intentLabel = (intent) => ({
  leave_absence:          "Urlaub & Abwesenheit",
  payroll_compensation:   "Gehalt & Spesen",
  onboarding_offboarding: "On-/Offboarding",
  working_time:           "Arbeitszeit",
  benefits:               "Benefits",
  general:           "Allgemein",
  privacy_request:   "Datenschutz",
})[intent] ?? intent;

const metrikLabel = (key) => ({
  latency_ms:         "Latenz (ms)",
  source_count:       "Quellenanzahl",
  fallback_used:      "Fallback aktiv",
  pii_detected:       "PII erkannt",
  llm_input_tokens:   "LLM Eingabe-Tokens",
  llm_output_tokens:  "LLM Ausgabe-Tokens",
  llm_model:          "LLM-Modell",
})[key] ?? key;

const scoreColor = (score) => {
  if (score === null || score === undefined) return "";
  if (score >= 0.75) return "color:#16a34a";
  if (score >= 0.45) return "color:#d97706";
  return "color:#dc2626";
};

// Prozent-Anzeige mit Farbe (invertiert für Halluzinationsrisiko)
const riskColor = (risk) => {
  if (risk === null || risk === undefined) return "";
  if (risk === 0)    return "color:#16a34a";
  if (risk <= 0.25)  return "color:#d97706";
  return "color:#dc2626";
};

// ── Demo-Schaltflächen ────────────────────────────────────────────────────
document.querySelectorAll(".demo-case").forEach((btn) => {
  btn.addEventListener("click", () => {
    questionInput.value = btn.dataset.case ?? "";
    questionInput.focus();
  });
});

// ── Tab wechseln per Hilfsfunktion ────────────────────────────────────────
function switchTab(name) {
  document.querySelectorAll(".tab").forEach((t) => {
    const active = t.dataset.tab === name;
    t.classList.toggle("active", active);
    t.setAttribute("aria-selected", String(active));
  });
  document.querySelectorAll(".tab-content").forEach((c) => {
    c.classList.toggle("active", c.id === `tab-${name}`);
  });
}

// ── WORKFLOW ──────────────────────────────────────────────────────────────
runButton.addEventListener("click", async () => {
  const question = questionInput.value.trim();
  if (!question) { statusLine.textContent = "Bitte zuerst eine Anfrage eingeben."; return; }

  runButton.disabled = true;
  statusLine.textContent = "Agent-Workflow läuft…";

  try {
    const response = await fetch("/api/v1/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload?.error?.message ?? "Anfrage fehlgeschlagen.");

    // Metriken
    intentValue.textContent = intentLabel(payload.intent);
    confidenceValue.textContent = `${Math.round(payload.confidence * 100)} %`;
    reviewValue.textContent = payload.human_review ? "Ja" : "Nein";

    const risk = payload.hallucination_risk ?? 0;
    hallucinationValue.textContent = `${Math.round(risk * 100)} %`;
    hallucinationValue.style = riskColor(risk);

    // Halluzinations-Warnung
    const claims = payload.unsupported_claims ?? [];
    if (claims.length > 0) {
      hallucinationWarning.style.display = "";
      unsupportedClaims.innerHTML = "";
      claims.forEach((claim) => {
        const div = document.createElement("div");
        div.className = "stack-item";
        div.innerHTML = `<p style="color:#dc2626;">${claim}</p>`;
        unsupportedClaims.appendChild(div);
      });
    } else {
      hallucinationWarning.style.display = "none";
    }

    answerValue.textContent = payload.answer;
    redactedValue.textContent = payload.redacted_input;

    // Eval-Tab vorausfüllen
    evalQuestion.value = question;
    evalAnswer.value   = payload.answer;
    if (payload.sources?.length) {
      evalContext.value = payload.sources.map((s) => s.snippet).join("\n");
    }

    renderStack(sourcesValue, payload.sources ?? [], "Keine Quellen gefunden.",
      (s) => `
        <strong>${s.title}</strong>
        <span class="pill">Score ${s.score.toFixed(3)}</span>
        <p>${s.snippet}</p>
        <span class="trace-meta">${s.metadata?.source_path ?? s.metadata?.doc_id ?? "–"}</span>
      `
    );

    renderStack(traceValue, payload.trace ?? [], "Kein Agenten-Trace vorhanden.",
      (step) => `
        <strong>${step.agent}</strong>
        <span class="pill">${step.decision}</span>
        <p>${step.rationale}</p>
        <span class="trace-meta">${step.latency_ms} ms | ${JSON.stringify(step.metadata)}</span>
      `
    );

    renderStack(metricsValue, Object.entries(payload.metrics ?? {}), "Keine Metriken vorhanden.",
      ([key, value]) => `<strong>${metrikLabel(key)}</strong><p>${JSON.stringify(value)}</p>`
    );

    statusLine.textContent = `Anfrage ${payload.request_id} erfolgreich – Eval-Tab wurde vorausgefüllt.`;
  } catch (err) {
    statusLine.textContent = `Fehler: ${err.message}`;
  } finally {
    runButton.disabled = false;
  }
});

// ── EVALUATION ────────────────────────────────────────────────────────────
evalButton.addEventListener("click", async () => {
  const question   = evalQuestion.value.trim();
  const answer     = evalAnswer.value.trim();
  const rawContext = evalContext.value.trim();

  if (!question || !answer || !rawContext) {
    evalStatus.textContent = "Bitte Frage, Antwort und Kontext ausfüllen.";
    return;
  }

  const contexts = rawContext.split("\n").map((l) => l.trim()).filter(Boolean);
  evalButton.disabled = true;
  evalStatus.textContent = "Claude-Richter bewertet…";

  try {
    const response = await fetch("/api/v1/eval/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, answer, contexts }),
    });
    const payload = await response.json();
    if (!response.ok || payload.error) throw new Error(payload?.error ?? "Evaluation fehlgeschlagen.");

    const fmt = (v) => v !== null && v !== undefined ? `${Math.round(v * 100)} %` : "n/v";

    evalFaithfulness.textContent = fmt(payload.faithfulness);
    evalFaithfulness.style = scoreColor(payload.faithfulness);
    evalRelevancy.textContent   = fmt(payload.relevancy);
    evalRelevancy.style         = scoreColor(payload.relevancy);
    evalOverall.textContent     = fmt(payload.overall);
    evalOverall.style           = scoreColor(payload.overall);
    evalExplanation.textContent = payload.explanation || "–";

    evalStatus.textContent = `Evaluation abgeschlossen (${payload.latency_ms ?? 0} ms · ${payload.llm_model || "–"}).`;
  } catch (err) {
    evalStatus.textContent = `Fehler: ${err.message}`;
  } finally {
    evalButton.disabled = false;
  }
});

// ── RETRIEVAL-DEBUG ───────────────────────────────────────────────────────
debugButton.addEventListener("click", async () => {
  const q = debugQuery.value.trim();
  if (!q) { debugStatus.textContent = "Bitte eine Suchanfrage eingeben."; return; }

  debugButton.disabled = true;
  debugStatus.textContent = "Retrieval-Diagnose läuft…";

  try {
    const response = await fetch(`/api/v1/debug/retrieval?q=${encodeURIComponent(q)}`);
    const payload  = await response.json();
    if (!response.ok) throw new Error(payload?.detail ?? "Diagnose fehlgeschlagen.");

    debugCount.textContent   = payload.results?.length ?? 0;
    debugMode.textContent    = payload.embedding_mode;
    debugChunks.textContent  = payload.total_chunks_indexed;
    debugLatency.textContent = `${payload.latency_ms} ms`;

    renderStack(debugResults, payload.results ?? [], "Keine Treffer für diese Anfrage.",
      (item) => `
        <strong>#${item.rank} – ${item.title}</strong>
        <span class="pill">Score ${item.score.toFixed(4)}</span>
        <span class="pill" style="background:var(--surface-raised);color:var(--text-muted);">${item.retrieval_mode}</span>
        <p>${item.snippet}</p>
        <span class="trace-meta">${JSON.stringify(item.metadata)}</span>
      `
    );

    debugStatus.textContent = `${payload.results?.length ?? 0} Ergebnisse in ${payload.latency_ms} ms.`;
  } catch (err) {
    debugStatus.textContent = `Fehler: ${err.message}`;
  } finally {
    debugButton.disabled = false;
  }
});

// Enter-Taste im Debug-Input
debugQuery.addEventListener("keydown", (e) => {
  if (e.key === "Enter") debugButton.click();
});

