# ARIA – Automotive Retrieval Intelligence Assistant

> **KI-gestützter RAG-Wissensassistent für Autohäuser** — produktionsreifer Python-Backend-Stack mit hybridem Retrieval, Halluzinationserkennung, DSGVO-konformer PII-Redaktion und eingebautem Evaluierungssystem.

---

## Überblick

ARIA beantwortet Kundenfragen zu Fahrzeugbestand, Finanzierung, Service, Inzahlungnahme und Garantie — ausschließlich auf Basis einer gepflegten Wissensdatenbank. Jede Anfrage durchläuft eine mehrstufige Agent-Pipeline, die transparent im Audit-Log nachvollzogen werden kann.

Besonderes Merkmal: Der **GroundingVerifierAgent** prüft jede generierte Antwort Satz für Satz gegen die abgerufenen Quellen und meldet ungedeckte Behauptungen als Halluzinationsrisiko — kein zusätzlicher LLM-Call, keine Latenzkosten.

---

## Features

| Feature | Beschreibung |
|---|---|
| **Hybrid RRF Retrieval** | Lexikalische und Dense-Suche, fusioniert via Reciprocal Rank Fusion |
| **Query Rewriting** | Claude reformuliert Kundenanfragen für optimale Vektordatenbanksuche |
| **Contextual Retrieval** | Anthropic-Technik: Claude bereichert jeden Chunk mit Dokumentkontext vor dem Embedding |
| **Halluzinationserkennung** | Token-Overlap-Check je Satz — ohne Extra-LLM-Call |
| **PII-Redaktion** | E-Mail, IBAN, VIN, KFZ-Kennzeichen u.v.m. werden vor dem Audit-Logging anonymisiert |
| **RAGAS-Evaluation** | Claude-Richter bewertet Faithfulness + Relevanz jeder Antwort |
| **SSE Streaming** | Token-by-Token Antwort via Server-Sent Events |
| **Multi-Turn History** | Gesprächsverlauf wird pro Request mitgeführt (max. 10 Turns) |
| **Agent Trace** | Jeder Schritt der Pipeline ist mit Latenz, Entscheidung und Begründung protokolliert |
| **Audit-Logging** | DSGVO-konformes JSONL-Log aller Anfragen (nur redigierte Eingaben) |
| **Retrieval-Debug** | Diagnose-Endpunkt zeigt Rang, Score und Retrieval-Modus pro Chunk |

---

## Agent-Pipeline

```
Kundenanfrage
      │
      ▼
┌─────────────────────────┐
│  PrivacyGuardAgent      │  PII erkennen & anonymisieren
└──────────┬──────────────┘
           ▼
┌──────────────────────────┐
│  IntentClassifierAgent   │  Domänen-Intent erkennen (Finanzierung / Service / …)
└──────────┬───────────────┘
           ▼
┌──────────────────────────┐
│  QueryRewriterAgent      │  Anfrage für Vektor-Retrieval optimieren (Claude)
└──────────┬───────────────┘
           ▼
┌──────────────────────────┐
│  RetrieverAgent          │  Hybrid RRF: Lexikal + Dense → Fusionierte Rangliste
└──────────┬───────────────┘
           ▼
┌──────────────────────────┐
│  QualityGuardAgent       │  Konfidenz berechnen, Eskalationsentscheidung
└──────────┬───────────────┘
           ▼
┌──────────────────────────┐
│  ResponseComposerAgent   │  Antwort mit Claude synthetisieren (+ Template-Fallback)
└──────────┬───────────────┘
           ▼
┌──────────────────────────┐
│  GroundingVerifierAgent  │  Halluzinationsrisiko messen (offline, kein LLM-Call)
└──────────┬───────────────┘
           ▼
┌──────────────────────────┐
│  MetricsAgent            │  Latenz, Token-Kosten, Fallback-Rate erfassen
└──────────────────────────┘
```

---

## API-Endpunkte

| Methode | Pfad | Beschreibung |
|---|---|---|
| `POST` | `/api/v1/ask` | Frage stellen — vollständige Agenten-Pipeline |
| `POST` | `/api/v1/ask/stream` | Antwort als SSE-Stream (Token-by-Token) |
| `POST` | `/api/v1/ingest` | Dokumente in die Wissensdatenbank laden |
| `POST` | `/api/v1/eval/run` | RAG-Antwort evaluieren (Faithfulness + Relevanz) |
| `GET`  | `/api/v1/debug/retrieval?q=…` | Retrieval-Diagnose mit Scores und Modus |
| `GET`  | `/api/v1/metrics` | Laufzeitmetriken (Latenz, Token-Kosten, Intent-Verteilung) |
| `GET`  | `/api/v1/audit-logs` | Letzte Audit-Log-Einträge (redigierte Eingaben) |
| `GET`  | `/api/v1/health` | Systemstatus und Indexgröße |

### Beispiel: Frage stellen

```bash
curl -X POST http://localhost:8100/api/v1/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Welche Finanzierungsoptionen gibt es für Gebrauchtwagen?",
    "session_id": "demo-001"
  }'
```

**Antwort (gekürzt):**
```json
{
  "intent": "financing",
  "answer": "Für Gebrauchtwagen bieten wir Finanzierungen ab 5.000 € ...",
  "confidence": 0.83,
  "hallucination_risk": 0.0,
  "unsupported_claims": [],
  "human_review": false,
  "sources": [{ "title": "Finanzierung", "score": 0.312, "snippet": "..." }],
  "token_usage": { "input_tokens": 920, "output_tokens": 180, "model": "claude-opus-4-7" }
}
```

### Beispiel: RAG-Evaluation

```bash
curl -X POST http://localhost:8100/api/v1/eval/run \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Wie lange ist die Werkstatt samstags geöffnet?",
    "answer": "Die Werkstatt ist samstags von 08:00 bis 13:00 Uhr geöffnet.",
    "contexts": ["Öffnungszeiten Werkstatt: Samstag 08:00 – 13:00 Uhr"]
  }'
```

```json
{
  "faithfulness": 1.0,
  "relevancy": 1.0,
  "overall": 1.0,
  "explanation": "Alle Angaben vollständig durch den Kontext belegt.",
  "llm_model": "claude-opus-4-7"
}
```

---

## Schnellstart

### Voraussetzungen

- Python 3.11+
- Anthropic API Key (optional — funktioniert auch ohne LLM mit Template-Fallback)

### Installation

```bash
git clone <repo>
cd autohaus-ai-rag-agent-backend

python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Konfiguration

`.env` im Projektstamm anlegen:

```env
ANTHROPIC_API_KEY=sk-ant-...
LLM_MODEL=claude-opus-4-7
LLM_MAX_TOKENS=1024
HYBRID_SEARCH_ENABLED=true
```

### Starten

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8100
```

Web-Interface: `http://localhost:8100`  
API-Dokumentation: `http://localhost:8100/docs`

### Tests ausführen

```bash
pytest tests/ -v
```

---

## Wissensdatenbank befüllen

Markdown-Dateien einfach in `data/knowledge_base/` ablegen — ARIA lädt sie beim Start automatisch.

Alternativ per API mit optionalem **Contextual Retrieval** (Claude bereichert jeden Chunk mit Dokumentkontext vor dem Embedding):

```bash
curl -X POST http://localhost:8100/api/v1/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "contextual_enrichment": true,
    "documents": [{
      "title": "Garantiebedingungen 2025",
      "content": "...",
      "category": "warranty"
    }]
  }'
```

---

## Tech Stack

| Schicht | Technologie |
|---|---|
| **Framework** | FastAPI + Uvicorn (async, ASGI) |
| **LLM** | Claude Opus 4.7 via Anthropic SDK (Prompt Caching, Streaming) |
| **Retrieval** | Hybrid RRF (Lexikal + Dense), lokales Embedding |
| **Datenschutz** | Eigener PII-Redactor (Regex-basiert) |
| **Konfiguration** | Pydantic Settings v2 + `.env` |
| **Tests** | pytest + pytest-asyncio |
| **Logging** | JSONL Audit-Log, strukturiertes Python-Logging |

---

## Architektur-Entscheidungen

**Warum kein LangChain / LlamaIndex?**  
Die gesamte Pipeline ist von Hand gebaut, um volle Kontrolle über Retrieval-Logik, Agent-Verhalten und Datenschutz-Schicht zu behalten. Das macht den Code einfacher zu prüfen, zu testen und produktionsreif zu deployen — ohne Framework-Abstraktion, die Fehler versteckt.

**Warum RRF statt Score-Normalisierung?**  
Reciprocal Rank Fusion ist provider-agnostisch, benötigt keine Score-Kalibrierung und übertrifft lineare Kombinationen konsistent auf Benchmark-Datensätzen (Cormack et al., 2009).

**Warum offline Grounding-Verifikation?**  
Ein zweiter LLM-Call für Halluzinationserkennung würde Latenz und Kosten verdoppeln. Token-Overlap auf Satz-Ebene ist schnell (< 1 ms), deterministisch und für produktive Autohaus-Anwendungen ausreichend präzise.

---

## Lizenz

MIT License
