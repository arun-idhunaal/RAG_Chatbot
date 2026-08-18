# Implementation Plan — INDmoney MF FAQ Chatbot (RAG)

**Status:** v1 — Phases 1–7 implemented. Streamlit MVP removed; production UI is React + Vite + FastAPI.  
**Based on:** `Architecture.md` (confirmed stack)  
**Also aligns with:** `PRD_RAGMFCHATBOT.md`, `PRODUCT_BRIEF_RAGMFCHATBOT.md`  
**Source inputs:** `SOURCE_LIST_RAGMFCHATBOT.md`, `SAMPLE_Q&A_RAGMFCHATBOT.md`  
**Edge cases:** `EDGECASES.md` (required per-phase tests; S0/S1 = acceptance blockers)

**Confirmed stack:** Playwright scrape · `bge-m3` · Chroma DB · Streamlit (Phase 5 MVP only) · **React + Vite + FastAPI (Phase 7 production)** · Hybrid classifier · Extract-then-template comparisons

---

## How to use this plan

Implement **one phase at a time**. Do not start the next phase until that phase’s **Exit criteria** are met — including the listed **`EDGECASES.md` IDs**.

| Phase | Name | Primary outcome | Edge-case focus |
|---|---|---|---|
| **1** | Foundation & Corpus | Sources scraped, chunked, embedded (`bge-m3`), stored in Chroma with metadata | EC-ING-* |
| **2** | Control Plane & Retrieval | PII → hybrid intent → scheme match → routed dual-corpus retrieval | EC-PII, EC-INT, EC-SCH, EC-RET |
| **3** | Grounded Answers | Single-scheme + general factual answers with citations and date stamps | EC-ANS, EC-CIT, EC-RET-04 |
| **4** | Comparisons & Guardrails | FR-4 extract→template; FR-7/8/9/10/11 refusals; citation validator | EC-CMP, EC-ADV, EC-MIX, EC-UNS, EC-OOC, EC-X |
| **5** | Streamlit UI (MVP) | Local/MVP chat UI meeting FR-12 | EC-UI-* |
| **6** | Eval, Freshness & Deploy | Daily 10:00 AM IST refresh, full edge-case eval, public URL, PRD acceptance | All EC-* suites |
| **7** | React + Vite + FastAPI | Production chat UI + HTTP API; Streamlit removed from runtime | EC-UI-*, EC-PII, EC-X-04 |

---

## Global conventions (all phases)

- **Citation correctness > latency** (Architecture design priority #1).
- **No PII persistence** anywhere in the pipeline.
- **Dual corpora stay isolated:** scheme vs general (FR-3).
- **Secrets** only via env vars (LLM keys); never commit `.env`.
- **Edge cases:** Implement and test against `EDGECASES.md`. Any **S0** failure blocks release; any **S1** failure blocks PRD acceptance.
- Follow suggested layout from Architecture §14:

```
RAG_Chatbot/
├── DOCS/                # includes EDGECASES.md, IMPLEMENTATION_PLAN.md, Architecture.md
├── app/                 # Streamlit MVP (Phase 5) — remove at Phase 7 exit
├── web/                 # React + Vite + TypeScript SPA (Phase 7)
├── src/
│   ├── api/             # FastAPI (Phase 7) — POST /v1/chat, GET /health
│   ├── ingestion/       # Phase 1
│   ├── retrieval/       # Phase 2
│   ├── pipeline/        # Phases 2–4
│   ├── prompts/         # Phases 2–4
│   └── config/          # Phase 1
├── data/raw/ · data/chroma/
├── eval/                # Phase 6 — Sample Q&A + EDGECASES.md
├── scripts/             # Phase 6
└── requirements.txt / pyproject.toml
```

---

## Phase 1 — Foundation & Corpus

**Goal:** Stand up the project and produce a queryable Chroma index from `SOURCE_LIST_RAGMFCHATBOT.md`.

### Scope

1. **Repo bootstrap**
   - Python project (`pyproject.toml` or `requirements.txt`)
   - Package layout under `src/`
   - `.env.example`, `.gitignore` (exclude `data/`, `.env`, caches)
2. **Config**
   - Load all **18** SOURCE_LIST URLs (5 scheme + 1 AMC FAQ + 9 SEBI + 3 AMFI)
   - Canonical `scheme_id`s, official names, and aliases (Architecture §3.2)
   - In-scope fact-type tags (`expense_ratio`, `exit_load`, `min_sip`, `lock_in`, `riskometer`, `benchmark`, `statement_download`)
3. **Ingestion pipeline**
   - Fetch HTML with **Playwright** (headless Chromium) so JS-rendered INDmoney / AMFI / AMC pages yield real content; **BeautifulSoup** for cleaning only; `httpx` fallback if Playwright cannot run (restricted hosts)
   - Clean: strip nav/ads; preserve fact tables; avoid cross-scheme contamination (**EC-ING-06**)
   - Chunk: structure-aware (~400–700 tokens, 50–80 overlap)
   - Attach metadata: `corpus`, `scheme_id`, `fact_types`, `source_url`, `source_title`, `page_ref`, `scraped_at`, `content_hash`
   - Tag/exclude performance-only content as `out_of_scope` (**EC-ING-05**)
   - Embed with **`BAAI/bge-m3`** only (**EC-ING-08**)
   - Upsert into **Chroma** collections: `mf_scheme_chunks`, `mf_general_chunks`
4. **CLI**
   - `python -m scripts.ingest` (or equivalent) to run a full ingest
   - Audit log: url, status, chunk_count, scraped_at (no user PII)
   - Partial failure behavior: keep last-good chunks (**EC-ING-01…03**)

### Deliverables

- [x] Runnable ingest script
- [x] Populated Chroma under `data/chroma/` (local / post-deploy bootstrap)
- [x] Config module for schemes + sources
- [x] Brief ingest success report (counts per corpus / scheme)
- [x] Notes/tests covering **EC-ING-01, EC-ING-05, EC-ING-06**

### Exit criteria

- All SOURCE_LIST URLs attempted; scheme + general collections non-empty
- Sample Chroma queries with metadata filters return only the intended `corpus` / `scheme_id` (**EC-RET-01** readiness)
- Re-running ingest is idempotent (content_hash / upsert behavior) (**EC-ING-04**)
- Related-fund chrome does not contaminate another `scheme_id` (**EC-ING-06**)
- Single-URL scrape failure does not wipe the index (**EC-ING-01**)

### Out of scope this phase

Chat UI, LLM answers, intent classification, scheduling.

### Depends on

Nothing (first phase).

---

## Phase 2 — Control Plane & Retrieval

**Goal:** Classify and route every query correctly; retrieve the right chunks without generating final user-facing answers yet.

### Scope

1. **PII gate (FR-11)**
   - Detect PAN, Aadhaar, account numbers, OTP-like codes, email, phone
   - On hit: short-circuit; never echo; never log raw message; never call LLM/retrieval
2. **Hybrid intent classifier (FR-1)**
   - Rules pre-filter: advisory / performance / comparison / unsupported-AMC cues
   - LLM structured output → exactly one of 8 taxonomy labels
   - Tie-break: factual + advisory → `mixed`; no unhandled fallthrough
3. **Scheme resolver (FR-2)**
   - Fuzzy match (`rapidfuzz`) against canonical names + aliases
   - Conservative threshold; ambiguity / low confidence → treat as unsupported (FR-9 path later)
4. **Retriever (FR-3)**
   - Scheme-specific → `corpus=scheme` AND `scheme_id=...`
   - General → `corpus=general` only
   - Never blend corpora in one retrieval call
   - Top-k 3–5; similarity floor; optional keyword boost for field labels

### Deliverables

- [x] `pii_guard`, `intent_classifier`, `scheme_resolver`, `retriever` modules
- [x] Orchestrator stub that returns `{intent, scheme_id?, chunks[], short_circuit?}`
- [x] Unit/smoke tests for each of the 8 intents’ **routing** (retrieval filters / early exit)
- [x] Edge-case fixtures from `EDGECASES.md`: **EC-PII-01…02**, **EC-INT-01…08**, **EC-INT-12**, **EC-SCH-01…06**, **EC-RET-01…04**

### Exit criteria

- Given Sample Q&A-style inputs, intent labels and retrieval filters match Architecture routing table
- PII inputs never reach retriever or logs (**EC-PII-***); PII+fact compound → FR-11 only (**EC-X-01** routing at gate)
- Wrong-scheme / ambiguous names do not retrieve a guessed scheme’s chunks (**EC-SCH-02**, **EC-SCH-03**)
- Factual+advisory → `mixed` (**EC-INT-01**); performance asks → `out_of_corpus_fact_type` (**EC-INT-03**, **EC-INT-12**)
- Scheme vs general filters never blend (**EC-RET-01**, **EC-RET-02**)

### Out of scope this phase

Final answer prose, comparison templates, chat UI.

### Depends on

Phase 1 (Chroma index + scheme config).

---

## Phase 3 — Grounded Answers (Single-Scheme & General)

**Goal:** Produce PRD-compliant factual answers for scheme-specific and general intents.

### Scope

1. **Grounded generator (FR-5, FR-6)**
   - Use **only** retrieved context (no model world knowledge)
   - Max 3 sentences; plain language
   - ≥1 citation with exact `source_url` (+ `page_ref` if available)
   - `Last updated from sources: YYYY-MM-DD` from cited chunk `scraped_at`
2. **Prompts**
   - Facts-only system prompt; forbid advice language
3. **Basic citation check**
   - Cited URL must be in the retrieved set for that turn
   - Scheme answers must not cite another scheme’s URL
4. **Wire into orchestrator**
   - Paths: `scheme_specific_factual`, `general_factual`
   - Insufficient context → “not found in sources” (not hallucinated fill)

### Deliverables

- [x] `answer_generator` + prompts
- [x] Response schema: `answer_text`, `citations[]`, `last_updated_from_sources`, `intent`
- [x] Manual notebook/CLI demos for ~5 scheme + ~5 general questions from Sample Q&A (`scripts/pipeline_route.py`)
- [x] Tests for **EC-ANS-01**, **EC-ANS-03**, **EC-ANS-04**, **EC-CIT-01…04**, **EC-RET-04**

### Exit criteria

- Factual answers include correct specific citation + per-answer date stamp (**EC-ANS-01**, **EC-CIT-04**)
- No advisory phrasing on pure factual queries
- Empty/wrong retrieval fails closed (no uncited numbers) (**EC-RET-04**, **EC-ANS-04**)
- Wrong-scheme citation rejected (**EC-CIT-02**); URL must be in retrieved set (**EC-CIT-03**)
- Domain-only citations rejected (**EC-CIT-01**)

### Out of scope this phase

Cross-scheme comparisons, full refusal matrix UI, deploy.

### Depends on

Phase 2.

---

## Phase 4 — Comparisons & Guardrails

**Goal:** Complete all remaining intent behaviors required by the PRD.

### Scope

1. **Cross-scheme comparison (FR-4) — extract → template**
   - Allowed fields only: expense ratio, exit load, min SIP, lock-in, riskometer, benchmark
   - Per-scheme retrieve → structured extract  
     `{scheme_id, scheme_name, field, value, source_url, scraped_at}`
   - Deterministic template listing each scheme’s value + own citation
   - No “better choice” / advice language; optional factual “lower than” only when values support it
   - Missing extract → “unavailable from sources” for that scheme (no guess)
2. **Refusal & edge handlers**
   - **FR-7 Advisory:** fixed refusal; optional SEBI education link; do not echo advisory framing
   - **FR-8 Mixed:** factual block (Phase 3 / FR-4) + distinct refusal line
   - **FR-9 Unsupported scheme:** not covered + list all 5 canonical names; no uncited knowledge
   - **FR-10 Out-of-corpus fact type:** distinct from FR-9; link official scheme source; never compute returns
   - **FR-11:** already in Phase 2 — re-verify end-to-end
3. **Citation validator (harden)**
   - Fail closed on invalid / cross-scheme citations
   - One retry extract/generate, then safe fallback message
4. **Comparison templater + field extractor modules**

### Deliverables

- [x] `field_extractor`, `comparison_templater`, refusal templates, hardened `citation_validator`
- [x] Full orchestrator covering all 8 taxonomy paths
- [x] CLI walkthrough matching Sample Q&A sections 1–4 (advisory, mixed, etc.)
- [x] Edge-case tests: **EC-CMP-01…06**, **EC-ADV-01…03**, **EC-MIX-01…04**, **EC-UNS-01…04**, **EC-OOC-01…04**, **EC-X-02…03**

### Exit criteria

- All 8 intent types classified and routed with correct response shape
- Comparisons: per-scheme values + citations; no performance/return framing (**EC-CMP-01…03**, **EC-CIT-05**)
- Missing extract → unavailable row, no guess (**EC-CMP-05**); no “better choice” (**EC-CMP-06**)
- Mixed = fact then separate refusal (**EC-MIX-01**, **EC-MIX-02**)
- Unsupported lists exactly the 5 schemes (**EC-UNS-01**); out-of-corpus **distinct** from unsupported (**EC-OOC-01**, **EC-OOC-04**)
- Advisory never hedges with uncited facts (**EC-ADV-01**); no echo of advisory framing (**EC-ADV-02**)
- PII refused with no echo/storage (**EC-PII-***)

### Out of scope this phase

Polished chat chrome (can use CLI/API only).

### Depends on

Phase 3.

---

## Phase 5 — Streamlit UI (FR-12, MVP)

**Goal:** Ship a standalone MVP chat experience described in the Product Brief and PRD. **Superseded at runtime by Phase 7** (React + FastAPI); keep this phase as the completed FR-12 proof on Streamlit.

### Scope

1. **Streamlit app (`app/`)**
   - Welcome message with facts-only framing
   - 3 clickable example questions
   - Persistent always-visible disclaimer: `Facts-only. No investment advice.`
   - Chat input → call Phase 4 orchestrator
2. **Answer rendering**
   - Answer text
   - Clickable citation links
   - Inline `Last updated from sources: [date]`
   - Mixed answers: visually distinct fact block vs refusal line
3. **UX constraints**
   - No auth / accounts
   - No server-side user history or PII storage
   - Stateless backend call per message

### Deliverables

- [x] `streamlit run app/...` local chat working against live pipeline
- [x] Example questions covering scheme fact, general fact, and comparison (or advisory demo)
- [x] Manual checks for **EC-UI-01…06**

### Exit criteria

- UI checklist from PRD §7 satisfied locally
- Welcome + 3 examples on load (**EC-UI-01**); disclaimer always visible (**EC-UI-02**)
- Every bot answer shows citation link(s) + date stamp **inline** (**EC-UI-03**)
- Mixed answers visually distinct (**EC-UI-04**); FR-9 lists all 5 names (**EC-UI-05**)
- Example buttons run the real pipeline (**EC-UI-06**)

### Out of scope this phase

Production hosting, daily cron, React rewrite (Phase 7).

### Depends on

Phase 4.

---

## Phase 6 — Eval, Freshness & Deploy

**Goal:** Make the system submission-ready: measurable quality, daily freshness, public shareable link.

### Scope

1. **Eval harness (`eval/`)**
   - Happy paths from `SAMPLE_Q&A_RAGMFCHATBOT.md`
   - Full stress suite from `EDGECASES.md` §12 (minimum ID set)
   - Suites: intent, scheme match, retrieval isolation, citations, comparison, advisory/mixed, FR-9 vs FR-10, PII, UI (manual OK), ingest, compound
   - Release gate: **S0** fail → block release; **S1** fail → block PRD acceptance
2. **Daily freshness**
   - Scheduler / GitHub Action / cron at **10:00 AM IST**
   - Full **Playwright** scrape of all 18 SOURCE_LIST URLs → re-embed changed content → Chroma upsert
   - Keep last-good chunks on single-URL failure (**EC-ING-01**, Architecture §4.6)
   - Post-ingest health check (collections non-empty + sample query); cold-start fail closed (**EC-X-04**)
3. **Deploy**
   - Host the MVP Streamlit app if needed for an interim shareable URL (Community Cloud / Railway / Render)
   - **Production shareable URL (Phase 7):** FastAPI serving the React SPA (Railway / Render / Fly) — one HTTPS origin
   - Env-based secrets only
4. **Acceptance sign-off**
   - Walk PRD §7 checklist end-to-end on the deployed URL
   - Spot-check compound cases **EC-X-01…03** on the live link
5. **Ops metrics (lightweight, no PII)**
   - Intent distribution, empty-hit rate, citation validation failures, scrape success rate

### Deliverables

- [x] `eval` runner with pass/fail report mapped to `EDGECASES.md` IDs
- [x] Scheduled ingest job + health check
- [ ] Deployed shareable link _(see `DOCS/DEPLOY.md` — push to https://github.com/arun-idhunaal/RAG_Chatbot then host)_
- [x] Checked-off PRD acceptance checklist template + S0/S1 gate (`DOCS/ACCEPTANCE_CHECKLIST.md`)

### Exit criteria (PRD §7 + EDGECASES)

- [ ] Prototype deployed as standalone web app with shareable link
- [x] All 8 intent types correctly classified and routed (eval + tests)
- [x] Every factual answer (single + cross-scheme) has ≥1 correct citation + per-answer date stamp
- [x] Cross-scheme comparisons never include performance/return framing
- [x] Advisory queries from Sample Q&A correctly refused
- [x] Mixed queries = distinct fact-then-refusal
- [x] Unsupported-scheme queries list the 5 supported schemes
- [x] Out-of-corpus fact-type queries distinguished from unsupported-scheme
- [x] PII inputs refused and never stored or echoed
- [x] UI shows welcome, 3 example questions, persistent disclaimer
- [x] `EDGECASES.md` §12 minimum suite wired in `eval/` (run `python -m scripts.run_eval`)

### Out of scope this phase

React + Vite + FastAPI production UI (Phase 7).

### Depends on

Phase 5 (MVP UI for interim demo). Pipeline itself only depends on Phase 4.

---

## Phase 7 — React + Vite + FastAPI (production UI)

**Goal:** Replace Streamlit with a production chat UI and HTTP API. Meet FR-12 and `EC-UI-*` on the React app. Streamlit is not required to run the product after this phase’s exit.

### Scope

1. **FastAPI app (`src/api/`)**
   - App lifespan: singleton `Retriever` (same role as Streamlit `@st.cache_resource`)
   - `GET /health` — reuse `check_index_health` (EC-X-04 fail closed when index empty)
   - `POST /v1/chat` — `{ "message": "..." }` → `process_query` → JSON DTO (Architecture §6.1)
   - DTO fields: `intent`, `answer_text`, `refusal_message`, `refusal_appended`, `citations[]`, `last_updated_from_sources`, `supported_schemes`, `comparison_field`, `comparison_rows`, `insufficient_context`, `corpus_available`
   - **Never** leak retrieved chunk text to the client
   - **PII:** if intent is `pii`, do not return `original_message`; client shows `[Message not shown — personal information detected]`
   - **Do not** expose unauthenticated ingest / “Build index” on the public chat UI. Ingest stays CLI / scheduled job (`scripts/ingest.py`, daily refresh)
2. **API tests**
   - Contract tests for `/v1/chat` and `/health`
   - PII request body never echoed in the response
   - Empty / unhealthy index → `corpus_available: false` and safe copy (EC-X-04)
3. **React + Vite + TypeScript (`web/`)**
   - Welcome + facts-only framing; 3 example questions (same copy as `app/ui_copy.py`)
   - Sticky / always-visible disclaimer: `Facts-only. No investment advice.` (EC-UI-02)
   - Chat transcript (browser session only; no server-side user history)
   - Mixed answers: two distinct visual blocks — facts (citations + date) then refusal (EC-UI-04)
   - Comparisons: table from `comparison_rows` (per-scheme value + citation); missing = “Unavailable from sources”
   - Citation links + inline `Last updated from sources: YYYY-MM-DD` (EC-UI-03)
   - FR-9: list all 5 canonical scheme names (EC-UI-05)
   - Loading caption: `Looking up approved sources…`
   - Corpus-unavailable state when `/health` or `corpus_available` fails
   - Example chips call the live `POST /v1/chat` pipeline (EC-UI-06) — not hardcoded answers
4. **Wire-up & deploy**
   - Local: Vite (`localhost:5173`) → FastAPI with CORS allowlist for that origin only
   - Production: FastAPI serves `web/dist` (single public HTTPS origin)
   - Docker Compose listen on **8000** (replace Streamlit **8501**)
5. **EC-UI tests**
   - Move/adapt `tests/test_ec_ui.py` to shared copy constants + DTO helpers (not Streamlit markdown)
6. **Remove Streamlit from runtime**
   - Drop `streamlit` dependency, `app/streamlit_app.py`, `.streamlit/`
   - Production shareable URL is FastAPI + React only

### Deliverables

- [x] FastAPI `GET /health` and `POST /v1/chat`
- [x] JSON DTO matching Architecture §6.1 (no chunk leak, no PII echo)
- [x] `web/` React SPA meeting FR-12 / EC-UI-01…06
- [x] Production static mount + Docker port 8000
- [x] Streamlit removed from runtime dependencies
- [x] API + adapted EC-UI tests

### Exit criteria

- Public shareable URL is FastAPI serving the React SPA (not Streamlit)
- Welcome + 3 examples on load (**EC-UI-01**); disclaimer always visible (**EC-UI-02**)
- Factual answers show clickable citations + inline date stamp (**EC-UI-03**)
- Mixed answers are two distinct blocks (**EC-UI-04**); FR-9 lists all 5 names (**EC-UI-05**)
- Example questions hit the live API/pipeline (**EC-UI-06**)
- PII path uses the client placeholder and never returns the raw message
- Comparison rows include per-scheme citations; no advice / returns chrome
- Streamlit is not required to run or deploy the product

### Out of scope this phase

New RAG features, multi-AMC, auth/accounts, streaming tokens (full JSON response is sufficient; client may show a typing indicator while waiting).

### Depends on

Phase 4 (orchestrator). Phase 5 Streamlit is **not** a runtime dependency.

---

## Phase dependency graph

```
Phase 1 Foundation & Corpus
    │
    ▼
Phase 2 Control Plane & Retrieval
    │
    ▼
Phase 3 Grounded Answers
    │
    ▼
Phase 4 Comparisons & Guardrails
    │
    ├──► Phase 5 Streamlit UI (MVP)
    │         │
    │         ▼
    │    Phase 6 Eval, Freshness & Deploy
    │
    ╰──► Phase 7 React + Vite + FastAPI (production UI; replaces Streamlit)
```

---

## Suggested order of coding within each phase

| Phase | First | Then | Last |
|---|---|---|---|
| 1 | Config + 18 SOURCE_LIST URLs | Playwright scrape / clean / chunk (anti-contamination) | bge-m3 + Chroma upsert + EC-ING checks |
| 2 | PII gate | Hybrid classifier + scheme resolver | Metadata-filtered retriever + EC-INT/SCH/RET tests |
| 3 | Generator prompt + schema | Wire scheme/general paths | Citation URL checks (EC-CIT) |
| 4 | Refusal templates | Field extract + comparison template | Full orchestrator + EC-CMP/UNS/OOC/MIX |
| 5 | Welcome / disclaimer / examples | Chat loop | EC-UI rendering checks |
| 6 | Eval cases from EDGECASES.md §12 | Cron ingest | Deploy + PRD + S0/S1 gate |
| 7 | FastAPI `/v1/chat` + `/health` DTO | React FR-12 screens | Static mount, Docker 8000, remove Streamlit |

---

## Definition of Done (project)

The project is done when Phase 6 quality gates are met, **Phase 7** is complete (deployed FastAPI + React SPA as the shareable URL, Streamlit removed from runtime), and **`EDGECASES.md` has no open S0/S1 failures**. Next.js is not part of the plan.
