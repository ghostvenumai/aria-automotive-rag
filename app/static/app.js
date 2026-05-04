// ── DOM-Referenzen ────────────────────────────────────────────────────────
const questionInput = document.querySelector("#question");
const runButton = document.querySelector("#run-button");
const statusLine = document.querySelector("#status-line");

const intentValue = document.querySelector("#intent-value");
const confidenceValue = document.querySelector("#confidence-value");
const reviewValue = document.querySelector("#review-value");
const hallucinationValue = document.querySelector("#hallucination-value");
const hallucinationWarning = document.querySelector("#hallucination-warning");
const unsupportedClaims = document.querySelector("#unsupported-claims");
const answerValue = document.querySelector("#answer-value");
const redactedValue = document.querySelector("#redacted-value");
const sourcesValue = document.querySelector("#sources-value");
const traceValue = document.querySelector("#trace-value");
const metricsValue = document.querySelector("#metrics-value");

// Eval-Panel
const evalQuestion = document.querySelector("#eval-question");
const evalAnswer = document.querySelector("#eval-answer");
const evalContext = document.querySelector("#eval-context");
const evalButton = document.querySelector("#eval-button");
const evalStatus = document.querySelector("#eval-status");
const evalFaithfulness = document.querySelector("#eval-faithfulness");
const evalRelevancy = document.querySelector("#eval-relevancy");
const evalOverall = document.querySelector("#eval-overall");
const evalExplanation = document.querySelector("#eval-explanation");

// Debug-Panel
const debugQuery = document.querySelector("#debug-query");
const debugButton = document.querySelector("#debug-button");
const debugStatus = document.querySelector("#debug-status");
const debugModeChip = document.querySelector("#debug-mode-chip");
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
    const wrapper = document.createElement("div");
    wrapper.className = "stack-item";
    wrapper.innerHTML = renderer(item);
    container.appendChild(wrapper);
  });
};

const intentLabel = (intent) =>
  ({
    vehicle_inventory: "Fahrzeugbestand",
    financing: "Finanzierung",
    service_booking: "Service",
    trade_in: "Inzahlungnahme",
    warranty: "Garantie",
    general: "Allgemein",
    privacy_request: "Datenschutz",
  })[intent] ?? intent;

const metrikLabel = (key) =>
  ({
    latency_ms: "Latenz (ms)",
    source_count: "Quellenanzahl",
    fallback_used: "Fallback aktiv",
    pii_detected: "PII erkannt",
    llm_input_tokens: "LLM Eingabe-Tokens",
    llm_output_tokens: "LLM Ausgabe-Tokens",
    llm_model: "LLM-Modell",
  })[key] ?? key;

const scoreColor = (score) => {
  if (score === null || score === undefined) return "";
  if (score >= 0.75) return "color:#22c55e";
  if (score >= 0.45) return "color:#f59e0b";
  return "color:#ef4444";
};

// ── Demo-Schaltflächen ────────────────────────────────────────────────────
document.querySelectorAll(".demo-case").forEach((button) => {
  button.addEventListener("click", () => {
    questionInput.value = button.dataset.case ?? "";
    questionInput.focus();
  });
});

// ── Haupt-Workflow ────────────────────────────────────────────────────────
runButton.addEventListener("click", async () => {
  const question = questionInput.value.trim();
  if (!question) {
    statusLine.textContent = "Bitte zuerst eine Anfrage eingeben.";
    return;
  }

  runButton.disabled = true;
  statusLine.textContent = "Agent-Workflow laeuft…";

  try {
    const response = await fetch("/api/v1/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    const payload = await response.json();

    if (!response.ok) {
      throw new Error(payload?.error?.message ?? "Anfrage fehlgeschlagen.");
    }

    intentValue.textContent = intentLabel(payload.intent);
    confidenceValue.textContent = `${Math.round(payload.confidence * 100)} %`;
    reviewValue.textContent = payload.human_review ? "Ja" : "Nein";

    // Halluzinationsrisiko anzeigen
    const risk = payload.hallucination_risk ?? 0;
    hallucinationValue.textContent = `${Math.round(risk * 100)} %`;
    hallucinationValue.style = scoreColor(1 - risk); // grün = kein Risiko, rot = hohes Risiko

    const claims = payload.unsupported_claims ?? [];
    if (claims.length > 0) {
      hallucinationWarning.style.display = "";
      unsupportedClaims.innerHTML = "";
      claims.forEach((claim) => {
        const div = document.createElement("div");
        div.className = "stack-item";
        div.innerHTML = `<p style="color:#ef4444;">${claim}</p>`;
        unsupportedClaims.appendChild(div);
      });
    } else {
      hallucinationWarning.style.display = "none";
      unsupportedClaims.innerHTML = "";
    }

    answerValue.textContent = payload.answer;
    redactedValue.textContent = payload.redacted_input;

    // Eval-Felder vorausfuellen fuer direkten Evaluierungs-Schnellstart
    evalQuestion.value = question;
    evalAnswer.value = payload.answer;
    if (payload.sources?.length) {
      evalContext.value = payload.sources.map((s) => s.snippet).join("\n");
    }

    renderStack(
      sourcesValue,
      payload.sources ?? [],
      "Keine Quellen gefunden.",
      (source) => `
        <strong>${source.title}</strong>
        <span class="pill">Score ${source.score.toFixed(3)}</span>
        <p>${source.snippet}</p>
        <span class="trace-meta">${source.metadata?.source_path ?? source.metadata?.doc_id ?? "-"}</span>
      `
    );

    renderStack(
      traceValue,
      payload.trace ?? [],
      "Kein Agenten-Trace vorhanden.",
      (step) => `
        <strong>${step.agent}</strong>
        <span class="pill">${step.decision}</span>
        <p>${step.rationale}</p>
        <span class="trace-meta">${step.latency_ms} ms | ${JSON.stringify(step.metadata)}</span>
      `
    );

    renderStack(
      metricsValue,
      Object.entries(payload.metrics ?? {}),
      "Keine Laufzeitmetriken vorhanden.",
      ([key, value]) => `<strong>${metrikLabel(key)}</strong><p>${JSON.stringify(value)}</p>`
    );

    statusLine.textContent = `Anfrage ${payload.request_id} erfolgreich verarbeitet.`;
  } catch (error) {
    statusLine.textContent = `Fehler: ${error.message}`;
  } finally {
    runButton.disabled = false;
  }
});

// ── RAG-Evaluierung ───────────────────────────────────────────────────────
evalButton.addEventListener("click", async () => {
  const question = evalQuestion.value.trim();
  const answer = evalAnswer.value.trim();
  const rawContext = evalContext.value.trim();

  if (!question || !answer || !rawContext) {
    evalStatus.textContent = "Bitte Frage, Antwort und Kontext ausfuellen.";
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

    if (!response.ok || payload.error) {
      throw new Error(payload?.error ?? payload?.detail ?? "Evaluation fehlgeschlagen.");
    }

    const fmt = (v) => v !== null && v !== undefined ? `${Math.round(v * 100)} %` : "n/v";

    evalFaithfulness.textContent = fmt(payload.faithfulness);
    evalFaithfulness.style = scoreColor(payload.faithfulness);
    evalRelevancy.textContent = fmt(payload.relevancy);
    evalRelevancy.style = scoreColor(payload.relevancy);
    evalOverall.textContent = fmt(payload.overall);
    evalOverall.style = scoreColor(payload.overall);
    evalExplanation.textContent = payload.explanation || "-";

    evalStatus.textContent = `Evaluation abgeschlossen (${payload.latency_ms ?? 0} ms, Modell: ${payload.llm_model || "-"}).`;
  } catch (error) {
    evalStatus.textContent = `Fehler: ${error.message}`;
  } finally {
    evalButton.disabled = false;
  }
});

// ── Retrieval-Debug ───────────────────────────────────────────────────────
debugButton.addEventListener("click", async () => {
  const q = debugQuery.value.trim();
  if (!q) {
    debugStatus.textContent = "Bitte eine Suchanfrage eingeben.";
    return;
  }

  debugButton.disabled = true;
  debugStatus.textContent = "Retrieval-Diagnose laeuft…";

  try {
    const response = await fetch(`/api/v1/debug/retrieval?q=${encodeURIComponent(q)}`);
    const payload = await response.json();

    if (!response.ok) {
      throw new Error(payload?.detail ?? "Diagnose fehlgeschlagen.");
    }

    debugModeChip.textContent = payload.embedding_mode;

    renderStack(
      debugResults,
      payload.results ?? [],
      "Keine Treffer fuer diese Anfrage.",
      (item) => `
        <strong>#${item.rank} – ${item.title}</strong>
        <span class="pill">Score ${item.score.toFixed(4)}</span>
        <span class="pill" style="background:var(--surface);">${item.retrieval_mode}</span>
        <p>${item.snippet}</p>
        <span class="trace-meta">${JSON.stringify(item.metadata)}</span>
      `
    );

    debugStatus.textContent = `${payload.results?.length ?? 0} Ergebnisse in ${payload.latency_ms} ms (${payload.total_chunks_indexed} Chunks indiziert).`;
  } catch (error) {
    debugStatus.textContent = `Fehler: ${error.message}`;
  } finally {
    debugButton.disabled = false;
  }
});
