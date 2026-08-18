# Architecture — INDmoney MF FAQ Chatbot (RAG)

**Status:** v1 draft (stack decisions confirmed)  
**Scope:** ICICI Prudential AMC, 5 schemes  
**Companion docs:** `PRODUCT_BRIEF_RAGMFCHATBOT.md`, `PRD_RAGMFCHATBOT.md`, `SOURCE_LIST_RAGMFCHATBOT.md`, `SAMPLE_Q&A_RAGMFCHATBOT.md`, `IMPLEMENTATION_PLAN.md`, `EDGECASES.md`

**Confirmed stack:** Playwright scrape · `bge-m3` · Chroma DB · Streamlit (Phase 5 MVP only) · **React + Vite + FastAPI (Phase 7 production)** · Hybrid classifier · Extract-then-template comparisons

**Edge cases:** Full catalog in `EDGECASES.md` (IDs `EC-*`). S0/S1 failures block acceptance.

---

## 0. Document Purpose

This document defines the end-to-end technical architecture for the INDmoney MF Support chatbot: ingestion, storage, retrieval, generation, UI, and compliance controls. It implements the functional requirements in `PRD_RAGMFCHATBOT.md` and the product constraints in `PRODUCT_BRIEF_RAGMFCHATBOT.md`.

**Design priorities (ordered):**

1. Citation correctness (wrong source = defect)
2. Facts-only / no advice leakage
3. Corpus isolation (scheme vs general)
4. PII non-persistence
5. Latency (acceptable to trade speed for correctness)

---

## 1. System Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│              STANDALONE WEB CHAT APP (React + Vite SPA)                  │
│  Welcome · 3 example Qs · Persistent disclaimer · Citations + date stamp │
└─────────────────────────────────┬────────────────────────────────────────┘
                                  │ HTTPS  POST /v1/chat
                                  ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                    FASTAPI  (serves SPA dist in prod)                    │
│  PII → Hybrid intent → Scheme match → Route → Retrieve → Gen/Template    │
└───────────────┬───────────────────────────────┬──────────────────────────┘
                │                               │
                ▼                               ▼
┌───────────────────────────┐     ┌─────────────────────────────────────────┐
│   SCHEME CORPUS (Chroma)  │     │   GENERAL CORPUS (Chroma)               │
│   5 INDmoney scheme pages │     │   13 pages: AMC FAQ · SEBI · AMFI       │
│   embeddings: bge-m3      │     │   embeddings: bge-m3                    │
│   metadata: scheme_id,    │     │   metadata: source_type, url, scraped_at│
│   fact_type, url, date    │     │                                         │
└─────────────▲─────────────┘     └──────────────────▲──────────────────────┘
              │                                      │
              └──────────────┬───────────────────────┘
                             │ Daily 10:00 AM scrape
                             ▼
              ┌──────────────────────────────┐
              │  INGESTION PIPELINE          │
              │  Scrape → Clean → Chunk →    │
              │  bge-m3 Embed → Chroma upsert│
              └──────────────────────────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │  SOURCE_LIST URLs (18)       │
              │  5 scheme + 13 general       │
              └──────────────────────────────┘
```

**Runtime model:** Stateless per request (no server session). The browser may send optional `prior_scheme_id` for a field-only follow-up. No user accounts, no chat-history persistence, no PII logs.

---

## 2. Confirmed Tech Stack

| Layer | Choice | Rationale |
|---|---|---|
| **Frontend** | **React + Vite + TypeScript** (Phase 7 production). Streamlit was Phase 5 MVP only | Polished FR-12 chat UI; single SPA origin in production |
| **API / Orchestration** | **FastAPI** wrapping `process_query` | Clear HTTP contract; `GET /health`, `POST /v1/chat`; easy to unit-test each FR stage |
| **Scraping** | **Playwright** (headless Chromium) to render and fetch HTML; BeautifulSoup to clean extracted DOM | INDmoney, AMFI, and AMC pages are JS-rendered; static `httpx` often returns shells/challenges. `httpx` is fallback only if Playwright cannot run |
| **Chunking / RAG framework** | LangChain or LlamaIndex | Document loaders, metadata filters, citation plumbing |
| **Embeddings** | **`BAAI/bge-m3`** | Confirmed embedding model; strong multilingual/retrieval quality for short factual chunks; runs locally or via compatible hosting |
| **Vector DB** | **Chroma DB** | Confirmed store; metadata filtering is mandatory for FR-3; sufficient for 5 schemes + 13 general pages (18 URLs total) |
| **LLM (generation)** | GPT-4o-mini / Claude Haiku-class (primary); used also as hybrid classifier LLM stage | Constrained factual rewrite / field extraction, not open-ended reasoning |
| **Intent classifier** | **Hybrid** — keyword/regex rules pre-filter + LLM structured-output label | Must emit exactly one of 8 taxonomy labels (FR-1); rules bias advisory / out-of-corpus / mixed before LLM confirms |
| **Comparison answers** | **Extract structured fields → deterministic template** | Safer citations than free-form LLM comparison prose (FR-4, FR-6) |
| **Scheme matcher** | Fuzzy string match (`rapidfuzz`) over canonical scheme names + aliases | FR-2; conservative threshold |
| **PII detector** | Regex + lightweight NER patterns (PAN, Aadhaar, phone, email, OTP, account) | FR-11; run before any LLM/log |
| **Scheduler** | Cron / GitHub Actions / cloud scheduler at 10:00 IST daily | Freshness model from PRD §1 |
| **Hosting** | Railway, Render, or Fly (FastAPI + static SPA) | Must expose a shareable public HTTPS URL (NFR). Not Streamlit Community Cloud |
| **Secrets** | Env vars only (LLM API keys); never in repo | Compliance |

**Confirmed build target:** **React + Vite SPA** + **FastAPI** (`POST /v1/chat`) + **Playwright ingest** + **Chroma DB** + **bge-m3** embeddings + hybrid classifier + extract-then-template comparisons + daily cron scrape. Streamlit remains a completed Phase 5 MVP only and is removed at Phase 7 exit.

---

## 3. Corpus Model

### 3.1 Two isolated corpora

| Corpus | Sources | Used for intents |
|---|---|---|
| **Scheme corpus** | 5 INDmoney ICICI Prudential scheme URLs | Scheme-specific factual, Cross-scheme comparison, Mixed (factual part), Out-of-corpus fact-type redirect |
| **General corpus** | 13 pages: ICICI Pru AMC FAQ (1) · SEBI investor pages (9) · AMFI knowledge-center pages (3) | General factual (non-scheme) |

**Hard rule (FR-3):** Never retrieve scheme facts from general pages, and never retrieve general definitions from scheme pages in the same retrieval call. Comparators pull **only** from the scheme corpus, filtered per `scheme_id`.

### 3.2 Supported schemes (canonical IDs)

| `scheme_id` | Canonical name | Aliases (examples) |
|---|---|---|
| `icici_nasdaq100_dg` | ICICI Prudential Nasdaq 100 Index Fund (Direct Growth) | nasdaq 100, icici nasdaq |
| `icici_midcap_dg` | ICICI Prudential Midcap Fund (Direct Plan Growth) | icici midcap, midcap fund |
| `icici_flexicap_dg` | ICICI Prudential Flexicap Fund (Direct Growth) | icici flexicap, flexi cap |
| `icici_largecap_dg` | ICICI Prudential Large Cap Fund (Direct Plan Growth) | icici large cap, largecap |
| `icici_elss_dg` | ICICI Prudential ELSS Tax Saver Fund (Direct Plan Growth) | icici elss, tax saver |

Aliases are used only for matching; retrieval and citations always use canonical names + source URLs.

### 3.3 In-scope fact types (scheme)

Structured metadata tags attached at chunk/ingest time where possible:

- `expense_ratio`
- `exit_load`
- `min_sip`
- `lock_in` (ELSS and others)
- `riskometer`
- `benchmark`
- `statement_download` (process; may also live in general corpus)

**Out of corpus (FR-10):** historical returns, performance vs benchmark — never ingested as answerable fact chunks; if scraped incidentally, tagged `out_of_scope` and excluded from retrieval filters.

### 3.4 Chunk metadata schema

Every vector record:

```json
{
  "chunk_id": "uuid",
  "corpus": "scheme | general",
  "scheme_id": "icici_flexicap_dg | null",
  "fact_types": ["expense_ratio"],
  "source_url": "https://...",
  "source_title": "ICICI Prudential Flexicap Fund Direct Growth",
  "page_ref": "optional section/heading",
  "scraped_at": "2026-08-12T10:00:00+05:30",
  "content_hash": "sha256...",
  "text": "..."
}
```

`scraped_at` on the **cited chunk(s)** drives the per-answer `Last updated from sources: [date]` stamp (FR-5).

---

## 4. Ingestion Pipeline (Offline / Scheduled)

### 4.1 Schedule

- **Frequency:** Daily at **10:00 AM IST**
- **Trigger:** Cloud cron / GitHub Actions / host scheduler
- **Idempotency:** Re-scrape all **18** `SOURCE_LIST` URLs via Playwright; upsert by `(source_url, content_hash)`; delete stale chunks for a URL when content changes

### 4.2 Stages

```
SOURCE_LIST URLs
      │
      ▼
[1] Fetch HTML (Playwright; httpx fallback)
      │
      ▼
[2] Extract main content (strip nav/ads/scripts)
      │
      ▼
[3] Normalize (whitespace, tables → markdown/text rows)
      │
      ▼
[4] Tag corpus + scheme_id + candidate fact_types
      │
      ▼
[5] Chunk (see 4.3)
      │
      ▼
[6] Embed
      │
      ▼
[7] Upsert into vector store with metadata
      │
      ▼
[8] Write scrape audit log (url, status, scraped_at, chunk_count) — no user PII
```

### 4.3 Cleaning rules

- Remove chrome: headers, footers, cookie banners, related-fund carousels that belong to **other** schemes (critical for citation correctness)
- Preserve tables for expense ratio / exit load / SIP where present
- Normalize currency and percentages as text (do not invent values)
- Drop or quarantine chunks that only contain performance/returns charts if they cannot be cleanly separated — prefer exclusion over wrong retrieval

### 4.4 Chunking strategy

| Parameter | Recommendation |
|---|---|
| Strategy | Structure-aware: split by H2/H3 sections; table rows kept intact where possible |
| Size | ~400–700 tokens target |
| Overlap | 50–80 tokens between narrative chunks |
| Scheme pages | Prefer smaller, fact-dense chunks keyed by `fact_types` |
| General pages | Slightly larger topical chunks (definitions, processes) |

**Why:** Citation correctness > recall. Over-large chunks increase risk of pulling the wrong field; over-tiny chunks lose table context.

### 4.5 Embeddings (`bge-m3`)

- **Model:** `BAAI/bge-m3` (confirmed)
- Embed `text` only (not metadata)
- Store vectors in **Chroma DB** with full metadata side-by-side
- Re-embed only when `content_hash` changes
- Keep embedding dimension / Chroma collection config consistent across ingest and query; never mix embedding models in the same collection

### 4.6 Failure handling

| Failure | Behavior |
|---|---|
| Single URL scrape fail | Keep last-good chunks for that URL; mark `stale=true` in audit; alert |
| Partial HTML / soft 403 / JS shell | Retry Playwright; if Playwright is unavailable (restricted hosts), try `httpx` then keep last-good |
| Embedding model/runtime failure | Abort upsert for that run; do not wipe existing Chroma index |
| Empty extract | Do not delete prior chunks until a valid replace is confirmed |

---

## 5. Online Query Pipeline

Every user message flows through a fixed ordered pipeline. Stages that short-circuit never call retrieval or the answer LLM with user content that should be refused.

```
User message
    │
    ▼
┌─────────────────┐  PII found ──► FR-11 refusal (no echo, no persist) ──► END
│ 1. PII Gate     │
└────────┬────────┘
         │ clean
         ▼
┌─────────────────┐
│ 2. Hybrid       │  → rules bias + LLM → one of 8 labels (FR-1)
│    Classifier   │
└────────┬────────┘
         │
         ├── advisory ──────────────────────────► FR-7 refusal (+ optional SEBI edu link)
         ├── unsupported scheme (after match) ─► FR-9 list 5 schemes
         ├── out_of_corpus_fact_type ───────────► FR-10 + factsheet redirect
         ├── general_factual ───────────────────► retrieve GENERAL only
         ├── scheme_specific_factual ───────────► match scheme → retrieve SCHEME(scheme_id)
         ├── cross_scheme_comparison ───────────► keyword-scan SCHEME chunks for all 5
         └── mixed ─────────────────────────────► factual path + append FR-7 refusal
         │
         ▼
┌─────────────────┐
│ 3. Scheme Match │  (when needed) fuzzy vs canonical + aliases (FR-2)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 4. Retrieval    │  metadata-filtered vector search (FR-3, FR-4)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 5. Grounded Gen │  single/general: LLM rewrite
│  or Template    │  comparison: extract → template (FR-4)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 6. Response     │  UI renders links + stamp + disclaimer (FR-12)
│    Guardrails   │
└─────────────────┘
```

### 5.1 Stage 1 — PII Gate (FR-11)

**Detect:** PAN, Aadhaar, bank/account numbers, OTP-like codes, email, phone.

**On hit:**

- Return fixed refusal copy
- Do **not** echo matched values
- Do **not** log raw message
- Do **not** run classifier / retrieval / LLM on the message
- Refuse entire message even if non-PII text is also present

### 5.2 Stage 2 — Intent Classification (FR-1)

Classifier must return **exactly one** of:

| Label | Maps to |
|---|---|
| `scheme_specific_factual` | FR-3, FR-5, FR-6 |
| `cross_scheme_comparison` | FR-4 |
| `general_factual` | FR-3, FR-5, FR-6 |
| `unsupported_scheme` | FR-9 (may also be decided post-match) |
| `out_of_corpus_fact_type` | FR-10 |
| `advisory` | FR-7 |
| `mixed` | FR-8 |
| `pii` | Should already be caught; treat as FR-11 if reached |

**Rules:**

- If factual + advisory signals coexist → **`mixed`**, never silent resolve to factual-only
- No unhandled `"unclassified"` fallthrough — default safe path: treat as `advisory` refusal **or** ask to rephrase within facts-only scope (prefer refusal consistency over guessing)

**Implementation (confirmed: Hybrid classifier):**

1. **Rules pre-filter (deterministic bias):**
   - Advice verbs / opinion cues (`should I`, `best`, `recommend`, `good fund`, `suitable`) → bias `advisory` or `mixed`
   - Performance terms (`return`, `CAGR`, `outperform`, `performance`) → bias `out_of_corpus_fact_type`
   - Comparison cues across schemes (`which of these`, `lowest`, `highest`, `compare`) → bias `cross_scheme_comparison`
   - Known unsupported AMC/scheme tokens (e.g. HDFC, SBI) → bias `unsupported_scheme`
2. **LLM structured-output stage:** JSON schema label ∈ 8 taxonomy labels; temperature 0; system prompt includes PRD §2 tie-break rules and the rules-stage hint
3. **Resolve:** Rules may force-safe certain paths (e.g. clear advisory with no factual ask → `advisory` without needing retrieval). Ambiguous cases defer to LLM label. Final emitted label is always exactly one taxonomy value.

### 5.3 Stage 3 — Scheme Identification (FR-2)

- Fuzzy-match query against canonical names + aliases (`rapidfuzz` token/partial ratios)
- **Conservative threshold** (e.g. require high score; ties → no match)
- Wrong-scheme match is worse than no match → on low confidence or ambiguity → FR-9
- For `cross_scheme_comparison`, scheme match may be “all five” without a single named scheme
- For unsupported AMC/scheme names (e.g. HDFC Flexicap) → FR-9 without retrieval
- **Field-only follow-up (EC-SCH-09):** if the client sends a valid `prior_scheme_id` and the new message is an in-scope field ask with no new scheme/AMC named (and is not a standalone definition / comparison / advice), resolve to that scheme. Do not default a scheme when `prior_scheme_id` is absent.

### 5.4 Stage 4 — Retrieval Routing (FR-3, FR-4)

| Intent | Filter |
|---|---|
| Scheme-specific | `corpus=scheme` AND `scheme_id=<matched>` |
| Cross-scheme | For each of 5 `scheme_id`s: `corpus=scheme` AND `scheme_id=...` AND preferably `fact_types` contains requested field; top-k per scheme |
| General factual | `corpus=general` only |
| Mixed | Same as factual subset only |
| Out-of-corpus | No generative retrieval for the requested figure; return official scheme page/factsheet link |

**Retrieval params (starting point):**

- Top-k: 3–5 per filter scope
- Similarity floor: drop chunks below threshold rather than force context
- Optional hybrid: keyword boost for exact field labels (`Expense Ratio`, `Exit Load`)

**Cross-scheme (FR-4) — confirmed: extract structured fields → template:**

- Allowed fields only: expense ratio, exit load, min SIP, lock-in, riskometer, benchmark
- For each of the 5 schemes, **keyword-scan stored chunks** for the requested field (`expense ratio`, TER, etc.) under that `scheme_id`. Do not rely on vector top-k of the user’s ranking question — those embeddings often miss the TER card even when a single-scheme LLM answer can still see it.
- Fall back to a field-focused vector query only if no keyword/tag hits exist.
- **Extract** a structured record per scheme (rule/table parse first, including TER values **without** a `%` sign and concatenated labels like `ExpenseRatio`; LLM extract only if regex fails), e.g.:
  ```json
  {
    "scheme_id": "icici_flexicap_dg",
    "scheme_name": "ICICI Prudential Flexicap Fund (Direct Growth)",
    "field": "expense_ratio",
    "value": "0.xx%",
    "source_url": "https://...",
    "scraped_at": "2026-08-12"
  }
  ```
- **Do not** ask the LLM to write free-form comparative prose that invents rankings or advice
- **Render** via a deterministic template that lists each scheme’s value with its own citation, e.g.  
  `Scheme A: X% ([source](url)). Scheme B: Y% ([source](url)). …`  
  plus `Last updated from sources` derived from the cited chunk dates (per-scheme or earliest/latest policy — prefer showing the date tied to each citation when dates differ)
- Factual comparative phrasing only when values support it (“Scheme A has a lower expense ratio than Scheme B”); never “better choice”
- If extraction fails for a scheme → state that scheme’s value as unavailable from sources (still cite attempt scope / scheme page), do not guess
- Expense-ratio parse must skip intervening dates (`as on 31 Jul 2026`), accept Direct values **with or without** `%`, and prefer the **Direct** figure when Direct and Regular are both listed (EC-CMP-09, EC-CMP-10). A ranking question must not return all-unavailable when the scheme pages contain the field.

### 5.5 Stage 5 — Answer Composition (FR-5, FR-6, FR-8)

**Path A — Single-scheme / general factual:** grounded LLM rewrite under constraints below.

**Path B — Cross-scheme comparison:** structured extract + template only (see §5.4). LLM is limited to field extraction, not final answer narration.

**Generator constraints (system prompt + post-checks) for Path A:**

- Use **only** retrieved context; if insufficient → say data not found in sources (do not use model world knowledge)
- Max **3 sentences** for the factual block
- Plain language
- ≥1 citation: exact `source_url` (+ `page_ref` if available)
- `Last updated from sources: YYYY-MM-DD` from cited chunk’s `scraped_at` (per-answer, not global)
- For mixed: factual block first (with citation + stamp), then a **separate** refusal line (FR-8)

**Citation validation (post-generation / post-template guard):**

- Every cited URL must appear in the retrieved set for that turn
- Scheme answers must not cite another scheme’s URL
- Comparison templates must carry one citation per scheme row shown
- Fail closed: if validation fails, regenerate/extract once or return safe “unable to verify from sources” message

### 5.6 Stage 6 — Refusal Templates

| Case | Behavior |
|---|---|
| FR-7 Advisory | Fixed polite refusal; optional SEBI investor-education link; do not echo advisory framing |
| FR-8 Mixed | Fact answer + distinct refusal line |
| FR-9 Unsupported scheme | State not covered + list all 5 canonical scheme names |
| FR-10 Out-of-corpus fact type | Explicitly distinguish from FR-9; link official scheme source; never compute/estimate returns |
| FR-11 PII | Refuse entirely; no echo; no storage |

### 5.7 Edge-case handling (normative)

Pipeline stages must satisfy the cases in `EDGECASES.md`. Highest-priority rules called out here:

| Risk | Rule | Edge case IDs |
|---|---|---|
| Wrong-scheme answer | Prefer FR-9 over low-confidence / ambiguous match | EC-SCH-02, EC-SCH-03, EC-SCH-06 |
| Wrong citation | Fail closed if URL ∉ retrieved set or scheme URL mismatch | EC-CIT-02, EC-CIT-03, EC-CIT-05 |
| Corpus blend | Never retrieve scheme facts from general (or vice versa) in one call | EC-RET-01, EC-RET-02 |
| Advice leakage | Pure advice → FR-7; fact+advice → FR-8; never hedge with uncited facts | EC-ADV-01, EC-MIX-01, EC-INT-01 |
| FR-9 vs FR-10 | Unsupported scheme ≠ out-of-corpus fact type — distinct copy | EC-UNS-*, EC-OOC-*, EC-OOC-04 |
| Performance asks | Never compute/estimate returns under any framing | EC-INT-03, EC-INT-12, EC-CMP-03, EC-OOC-* |
| PII | Gate before everything; refuse entire message; no echo/logs | EC-PII-*, EC-X-01 |
| Comparison safety | Keyword-scan field chunks + extract → template; no “better choice”; no bare ranking without values | EC-CMP-02, EC-CMP-05, EC-CMP-06, EC-CMP-09, EC-CMP-10 |
| Empty / failed retrieval | “Not found in sources” — no model world knowledge | EC-RET-04, EC-ANS-04 |
| Ingest failure | Keep last-good Chroma; no wipe on partial failure | EC-ING-01…03 |

---

## 6. Component Design

### 6.1 Orchestrator (API)

**Endpoints:**

| Method | Path | Role |
|---|---|---|
| `POST` | `/v1/chat` | User message → pipeline DTO (no retrieved chunk text) |
| `GET` | `/health` | Index health (`check_index_health`); fail closed when empty (EC-X-04) |

Production: FastAPI also serves `web/dist` (React SPA) on the same origin. Local: Vite on `localhost:5173` with CORS allowlisted to that origin only.

**Do not** expose unauthenticated ingest / “Build index” on the public chat API. Ingest remains CLI / scheduled job.

```json
// POST /v1/chat request
{ "message": "What is the expense ratio of ICICI Flexicap?" }

// Field-only follow-up (optional; browser-held last scheme)
{ "message": "minimum sip amount?", "prior_scheme_id": "icici_nasdaq100_dg" }

// POST /v1/chat response
{
  "intent": "scheme_specific_factual",
  "answer_text": "...",
  "refusal_message": null,
  "refusal_appended": false,
  "citations": [
    { "title": "...", "url": "https://...", "page_ref": null }
  ],
  "last_updated_from_sources": "2026-08-12",
  "supported_schemes": [],
  "comparison_field": null,
  "comparison_rows": [],
  "insufficient_context": false,
  "corpus_available": true,
  "scheme_id": "icici_flexicap_dg"
}
```

**PII:** if `intent` is `pii`, do **not** include `original_message` (or any echo of the user text). The React client displays `[Message not shown — personal information detected]`.

**Retriever:** constructed once in FastAPI app lifespan (singleton), analogous to Streamlit `@st.cache_resource`.

Pipeline modules (testable units):

1. `pii_guard`
2. `intent_classifier` (hybrid: rules + LLM)
3. `scheme_resolver`
4. `retriever` (scheme / general / multi-scheme; Chroma + bge-m3)
5. `field_extractor` (structured values for comparisons)
6. `answer_generator` (single-scheme / general grounded rewrite)
7. `comparison_templater` (deterministic FR-4 rendering)
8. `citation_validator`
9. `response_formatter`

### 6.2 Vector store collections (Chroma DB)

Use **two Chroma collections** (or one collection with mandatory `corpus` filter on every query):

- `mf_scheme_chunks`
- `mf_general_chunks`

Application code must never query without a corpus filter. All vectors are produced by **`bge-m3`** only.

### 6.3 Prompting & templating strategy

| Component | Role |
|---|---|
| Hybrid classifier rules | Bias advisory / out-of-corpus / comparison / unsupported before LLM |
| Classifier system prompt | Emit one taxonomy label + brief rationale (rationale not shown to user) |
| Generator system prompt | Facts-only, 3-sentence max, cite URLs from context, include date stamp field, no advice language |
| Field extractor prompt | Output structured `{scheme_id, field, value, source_url, scraped_at}` from retrieved chunks only |
| Comparison template | Deterministic per-scheme value + citation lines; forbid ranking-as-advice |
| Refusal templates | Deterministic FR-7/9/10/11 copy (not free-form LLM) |

Prefer templates for FR-7/9/10/11 and for **all FR-4 comparisons** to guarantee citation safety and consistency with `SAMPLE_Q&A_RAGMFCHATBOT.md`.

---

## 7. UI Architecture (FR-12)

**Surface:** Standalone **React + Vite** SPA calling **FastAPI** `POST /v1/chat`, shareable as one HTTPS origin (FastAPI serves `web/dist` in production).  
**MVP (completed):** Streamlit in `app/` — Phase 5 only; removed from runtime at Phase 7 exit. Not Next.js.

**Required elements:**

1. Welcome message stating facts-only framing on load
2. Three clickable example questions (seed from Sample Q&A factual set); clicks hit the live API, not hardcoded answers
3. Persistent always-visible (sticky) disclaimer: e.g. `Facts-only. No investment advice.`
4. Bot messages render:
   - Answer text
   - Clickable citation link(s) inline (not tooltip-only)
   - Inline `Last updated from sources: [date]`
5. Mixed answers: two distinct visual blocks (facts card with citations + date, then separate refusal)
6. Cross-scheme comparisons: per-scheme table from `comparison_rows` (value + own citation); missing values as “Unavailable from sources”; no “best/winner” chrome
7. FR-9: all 5 canonical scheme names readable
8. Loading: `Looking up approved sources…` (full JSON response; optional client typing indicator)
9. Corpus unavailable: when `/health` or `corpus_available` is false (EC-X-04)

**Non-requirements:** Auth, accounts, chat history server-side persistence, personalization, unauthenticated ingest from the UI. Optional same-scheme field follow-up uses a client-held `prior_scheme_id` only (EC-SCH-09) — not a stored transcript.

**Example questions (illustrative):**

- “What is the expense ratio of ICICI Prudential Flexicap Fund?”
- “What is an exit load?”
- “Which of these 5 has the lowest expense ratio?”

---

## 8. Security, Privacy & Compliance

| Control | Implementation |
|---|---|
| No PII storage | PII gate before logging; redact or drop request bodies that fail gate |
| No user accounts | Stateless API |
| Public sources only | Ingest only `SOURCE_LIST` URLs |
| Facts-only | Classifier + refusal templates + generator constraints |
| Secrets | API keys in environment / secret manager |
| Transport | HTTPS for public deployment |
| Audit | Scrape/job logs and optional anonymized metrics (intent counts); never store raw PII-bearing messages |

---

## 9. Non-Functional Architecture Notes

| NFR | Approach |
|---|---|
| Citation correctness > latency | Allow multi-step retrieval for comparisons; validate citations before return |
| Shareable link | Deploy FastAPI + React SPA (one public HTTPS origin; not localhost-only) |
| Freshness | Daily 10:00 AM IST Playwright refresh of 18 URLs; per-answer `scraped_at` from cited chunk |
| Scale (v1) | 18 SOURCE_LIST URLs (5 scheme + 13 general) → single small vector index is sufficient |

---

## 10. Mapping: PRD Requirements → Architecture

| PRD ID | Architecture mechanism |
|---|---|
| FR-1 | Hybrid intent classifier (rules + LLM) before retrieval |
| FR-2 | Fuzzy scheme resolver + conservative threshold → FR-9 on fail |
| FR-3 | Dual Chroma corpora + metadata filters |
| FR-4 | Multi-scheme retrieval → structured field extract → comparison template + per-scheme citations |
| FR-5 | Generator constraints + date from cited `scraped_at` |
| FR-6 | Citation objects from retrieved metadata + post-validator |
| FR-7 | Deterministic advisory refusal template |
| FR-8 | Factual path then append refusal block |
| FR-9 | Unsupported / low-confidence match handler listing 5 schemes |
| FR-10 | Out-of-corpus intent + factsheet/source redirect, no computation |
| FR-11 | Pre-pipeline PII gate |
| FR-12 | React chat UI + FastAPI: welcome, 3 examples, sticky disclaimer, inline citations/date, mixed two-block, comparison table |
| NFR | Stateless deploy, no PII logs, public URL, correctness-first |

---

## 11. Sequence Diagrams

### 11.1 Scheme-specific factual

```
User → React SPA → FastAPI POST /v1/chat
API → PIIGate (pass)
API → Classifier(hybrid) → scheme_specific_factual
API → SchemeResolver → icici_flexicap_dg
API → Retriever(scheme_id=icici_flexicap_dg, fact≈expense_ratio)
Retriever → Chroma(bge-m3) → chunks[]
API → Generator(chunks) → answer + citations + date
API → CitationValidator (pass)
API → UI → User
```

### 11.2 Advisory

```
User → React SPA → FastAPI POST /v1/chat
API → PIIGate (pass)
API → Classifier(hybrid) → advisory
API → RefusalTemplate(FR-7) → UI → User
(no retrieval, no generator grounded call required)
```

### 11.3 Mixed

```
User → React SPA → FastAPI POST /v1/chat
API → Classifier(hybrid) → mixed
API → SchemeResolver + Retriever + Generator  → factual block
API → Append FR-7 refusal line
API → UI (two distinct blocks) → User
```

### 11.4 Cross-scheme comparison

```
User → React SPA → FastAPI POST /v1/chat
API → Classifier(hybrid) → cross_scheme_comparison
API → for scheme in [5]: Retriever(scheme_id, fact_field) → Chroma
API → FieldExtractor → structured rows[{value, source_url, scraped_at}, ...]
API → ComparisonTemplater → 5 values + 5 citations + dates
API → CitationValidator (pass)
API → UI → User
```

---

## 12. Data Freshness & Operations

| Job | When | Owner module |
|---|---|---|
| Full scrape + re-index | Daily 10:00 AM IST | `ingestion/` |
| Health check (index non-empty, sample query) | Post-ingest | `ops/health` |
| Manual re-ingest | On SOURCE_LIST change | CLI/script |
| Prompt/eval regression | On PR / before demo | `eval/` against Sample Q&A intents |

**Operational metrics (no PII):**

- Intent distribution
- Retrieval empty-hit rate
- Citation validation failure rate
- Scrape success rate per URL
- p50/p95 latency (informational only)

---

## 13. Evaluation & Acceptance Alignment

Build an eval harness that runs labeled cases from:

1. `SAMPLE_Q&A_RAGMFCHATBOT.md` (happy paths)
2. `EDGECASES.md` (stress / failure modes — required)
3. PRD §7 acceptance checklist

| Suite | Pass criteria | Primary edge cases |
|---|---|---|
| Intent classification | All 8 taxonomy paths route correctly | EC-INT-* |
| Scheme matching | Conservative; ambiguity → FR-9 | EC-SCH-* |
| Retrieval isolation | No cross-scheme / cross-corpus bleed | EC-RET-* |
| Citation correctness | Scheme answers cite that scheme’s URL only | EC-CIT-*, EC-ANS-* |
| Comparison | Structured extract + template; values + per-scheme citations; no advice language | EC-CMP-* |
| Advisory / mixed | Refusal / fact-then-refusal structure | EC-ADV-*, EC-MIX-* |
| Unsupported scheme | Lists exactly the 5 supported names | EC-UNS-* |
| Out-of-corpus | Distinct from unsupported; no computed returns | EC-OOC-* |
| PII | Refuse; no storage/echo | EC-PII-* |
| UI checklist | Welcome, 3 examples, persistent disclaimer, inline citation + date | EC-UI-* |
| Ingest resilience | Last-good retained; no contamination | EC-ING-* |
| Compound | PII-first, mixed comparison+advice, etc. | EC-X-* |

**Release gate:** Any **S0** failure in `EDGECASES.md` blocks release. Any **S1** failure blocks PRD acceptance.

---

## 14. Suggested Repository Layout

```
RAG_Chatbot/
├── DOCS/
│   ├── PRODUCT_BRIEF_RAGMFCHATBOT.md
│   ├── PRD_RAGMFCHATBOT.md
│   ├── SOURCE_LIST_RAGMFCHATBOT.md
│   ├── SAMPLE_Q&A_RAGMFCHATBOT.md
│   ├── Architecture.md
│   ├── IMPLEMENTATION_PLAN.md
│   └── EDGECASES.md
├── app/                    # Streamlit MVP (Phase 5); remove at Phase 7 exit
├── web/                    # React + Vite + TypeScript SPA (Phase 7)
├── src/
│   ├── api/                # FastAPI: POST /v1/chat, GET /health, serve web/dist
│   ├── ingestion/          # Playwright scrape, clean, chunk, bge-m3 embed, Chroma upsert
│   ├── retrieval/          # corpus filters, Chroma query
│   ├── pipeline/           # pii, hybrid intent, scheme match, extract, generate, template, validate
│   ├── prompts/
│   └── config/             # schemes, aliases, source list loader
├── data/
│   ├── raw/                # optional cached HTML (no PII)
│   └── chroma/             # Chroma DB persistence
├── eval/                   # Sample Q&A + EDGECASES.md suites
├── scripts/                # cron entrypoints
└── requirements.txt / pyproject.toml
```

---

## 15. Build Phases (Architecture Delivery Plan)

Detailed phase exit criteria and edge-case IDs: see `IMPLEMENTATION_PLAN.md`.

1. **Corpus v1:** Playwright-scrape all 18 SOURCE_LIST URLs → clean → chunk → **bge-m3** embed → **Chroma** with metadata (EC-ING)  
2. **Pipeline v1:** PII → **hybrid intent** → scheme match → routed retrieval → cited answers (EC-PII, EC-INT, EC-SCH, EC-RET)  
3. **Comparisons:** Field extractor + deterministic template (FR-4) (EC-CMP)  
4. **Guardrails:** Refusal templates for FR-7/9/10/11; citation validator (EC-ADV, EC-MIX, EC-UNS, EC-OOC, EC-CIT)  
5. **UI v1 (Streamlit MVP):** Welcome, examples, disclaimer, citation + date rendering (EC-UI)  
6. **Scheduler:** Daily 10:00 AM IST refresh  
7. **Eval:** Sample Q&A + `EDGECASES.md` + PRD acceptance checklist  
8. **Deploy:** Public shareable URL (interim Streamlit optional; production = Phase 7)  
9. **Phase 7:** React + Vite + FastAPI cutover — replace Streamlit; FastAPI serves SPA; Docker port 8000

---

## 16. Confirmed Architecture Decisions

| Decision | Confirmed choice |
|---|---|
| Embedding model | **`BAAI/bge-m3`** |
| Vector store | **Chroma DB** |
| UI framework | **React + Vite + TypeScript** (production); Streamlit = completed Phase 5 MVP only |
| API | **FastAPI** — `POST /v1/chat`, `GET /health`; serves `web/dist` in production |
| Intent classifier | **Hybrid** (rules pre-filter + LLM structured label) |
| Comparison answers | **Extract structured fields → deterministic template** (safer citations) |
| Scraping | **Playwright** (primary); `httpx` fallback; BeautifulSoup for cleaning |
| Corpus size | **18 URLs** (5 scheme + 13 general) from `SOURCE_LIST_RAGMFCHATBOT.md` |
| LLM vendor (generation / classifier LLM stage) | Still flexible (e.g. OpenAI / Anthropic / Groq); abstract behind an interface |

---

## 17. Summary

The system is a **dual-corpus, Chroma-backed RAG** using **`bge-m3` embeddings**, with a **strict pre-retrieval control plane** (PII → **hybrid intent** → scheme resolution). Single-scheme and general answers use constrained grounded generation; **cross-scheme comparisons extract structured fields and render via templates** for citation safety. The production surface is a **React + Vite SPA** over **FastAPI** (`POST /v1/chat`). Correctness is enforced by corpus isolation, conservative scheme matching, deterministic refusals, and citation validation — matching the PRD’s bar that a wrongly cited answer is a defect even if the number looks plausible. Concrete failure modes and test IDs live in **`EDGECASES.md`**.
