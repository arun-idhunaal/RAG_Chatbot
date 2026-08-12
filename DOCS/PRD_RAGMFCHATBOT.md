# PRD — INDmoney MF FAQ Chatbot (RAG, ICICI Prudential Scope)

**Status:** v1 draft
**Scope:** ICICI Prudential AMC, 5 schemes
**Companion docs:** `PRODUCT_BRIEF_RAGMFCHATBOT.md` (why/business context), `SOURCE_LIST_RAGMFCHATBOT.md` (source URLs), `SAMPLE_Q&A_RAGMFCHATBOT.md` (example interactions)

---

## 0. Document Map

| Doc | Purpose |
|---|---|
| `PRODUCT_BRIEF_RAGMFCHATBOT.md` | Why we're building this, who it's for, business framing |
| **`PRD_RAGMFCHATBOT.md`** (this doc) | Functional spec — what the bot must do, exactly |
| `SOURCE_LIST_RAGMFCHATBOT.md` | The 15–25 URLs that make up the corpus |
| `SAMPLE_Q&A_RAGMFCHATBOT.md` | Example query/answer pairs (currently templated — needs real values before submission) |

---

## 1. Scope 

- **AMC:** ICICI Prudential Mutual Fund
- **Schemes (5):**
  1. ICICI Prudential Nasdaq 100 Index Fund (Direct Growth)
  2. ICICI Prudential Midcap Fund (Direct Plan Growth)
  3. ICICI Prudential Flexicap Fund (Direct Growth)
  4. ICICI Prudential Large Cap Fund (Direct Plan Growth)
  5. ICICI Prudential ELSS Tax Saver Fund (Direct Plan Growth)
- **Fact types in scope:** expense ratio, exit load, minimum SIP, lock-in (ELSS), riskometer, benchmark, capital-gains/statement download process
- **Fact types explicitly out of scope:** historical returns, performance vs. benchmark (see Section 6)
- **Delivery format:** standalone web app with a chat UI
- **Data freshness:** live-scraped from the source URLs daily morning at 10.00 AM.

---

## 2. Intent Taxonomy

Every incoming query must be classified into exactly one of these before retrieval happens. This taxonomy is the backbone of Sections 3 and drives what should stress-test.

| Intent | Example | Routes to |
|---|---|---|
| Scheme-specific factual | "Expense ratio of ICICI Flexicap?" | FR-3, FR-5, FR-6 |
| Cross-scheme factual comparison | "Which of these 5 has the lowest expense ratio?" | FR-4 |
| General factual (non-scheme) | "What is an exit load?" | FR-3, FR-5, FR-6 |
| Unsupported scheme | "Expense ratio of HDFC Flexicap?" | FR-9 |
| Out-of-corpus fact type | "What's the performance of ICICI Midcap today?" | FR-10 |
| Advisory / opinion | "Should I invest in this fund?" | FR-7 |
| Mixed (factual + advisory) | "Expense ratio of X, and is it good?" | FR-8 |
| PII / restricted input | Contains PAN, Aadhaar, account number, OTP, email, phone | FR-11 |

---

## 3. Functional Requirements

### FR-1: Query Intent Classification
**Behavior:** Every query is classified against the taxonomy in Section 2 before any retrieval call. Classification happens first — retrieval source selection (FR-3) depends on its output.
**Rules:**
- If a query could plausibly match more than one intent (e.g., contains both a scheme name and an opinion word), it must be classified as **Mixed**, not silently resolved to one side.
- Classification confidence/method is an architecture decision but the classifier's output must be one of the 8 taxonomy labels, with no fallthrough "unclassified" state left unhandled.

### FR-2: Scheme Identification & Matching
**Behavior:** When a query names or implies a scheme, fuzzy-match it against the 5 supported scheme names (confirmed approach — handles informal phrasing like "ICICI midcap" → ICICI Prudential Midcap Fund).
**Rules:**
- Fuzzy match against official scheme names, not against the raw URL slugs.
- If match confidence is below a reasonable threshold, or the query ties between two or more schemes ambiguously, do **not** guess — fall through to FR-9 (Unsupported Scheme Handling) and surface the list of 5 supported schemes rather than answering against a wrong scheme.
- A wrong-scheme match is worse than a no-match — bias the threshold conservatively.

### FR-3: Retrieval Source Routing
**Behavior:** Route retrieval to the correct corpus subset based on classified intent.
**Rules:**
- Scheme-specific factual → retrieve only from that scheme pages. Never pull facts about Scheme A from Scheme B's page.
- General factual → retrieve only from non-scheme sources (SEBI/AMFI/AMC FAQ pages listed in Source List).
- Never blend a scheme-specific fact with a general-source citation, or vice versa — the two corpora stay separate at retrieval time.

### FR-4: Cross-Scheme Comparison Handling
**Behavior:** Comparative factual questions across the 5 supported schemes are in scope.
**Rules:**
- Only these fields may be compared: expense ratio, exit load, minimum SIP, lock-in, riskometer category, benchmark.
- Answer must state each scheme's value individually with its own citation (e.g., "Scheme A: X% [source]. Scheme B: Y% [source].") — never a bare ranking without the underlying values shown.
- Phrasing must stay factual: "Scheme A has a lower expense ratio than Scheme B" is fine. "Scheme A is the better choice" is not — that's advisory and must route to FR-7 language instead, even mid-answer.

### FR-5: Answer Composition
**Behavior:** Every factual answer follows a fixed shape.
**Rules:**
- Maximum 3 sentences.
- Plain language, no jargon left unexplained.
- Every answer includes **at least one** citation link to the exact source document (see FR-6 for citation specificity).
- Every answer includes a `Last updated from sources: [date]` stamp. The date reflects the **actual source document/page url cited in that specific answer** — not one global "corpus last updated" date. 

### FR-6: Citation Requirements
**Behavior:** Citations must be specific enough to verify, not just a domain-level link.
**Rules:**
- Cite the exact scheme or public SEBI/AMFI page, with a link, and page reference where the source format allows it.
- One citation minimum per answer; multiple citations allowed for cross-scheme comparisons (FR-4) where each scheme needs its own source.
- A citation to the wrong scheme's document, even if the number happens to look plausible, is treated as a defect — this is the single most important quality bar for this bot.

### FR-7: Refusal Behavior (Advisory Queries)
**Behavior:** Any query classified as Advisory gets a polite, consistent refusal — never a partial or hedged factual answer.
**Rules:**
- Refusal message states the facts-only policy plainly (see disclaimer snippet in the Product Brief / UI copy).
- Optionally append a link to a relevant educational/regulatory page (e.g., SEBI investor education) — not a product recommendation, just general education.
- The refusal should not restate or engage with the specific advisory framing (e.g., don't echo "you asked if X is a good fund" — just decline cleanly).

### FR-8: Mixed Query Handling
**Behavior:** When a query has both a factual and an advisory component, answer only the factual part, then append the standard refusal for the advisory part.
**Rules:**
- Factual portion must independently satisfy FR-5 and FR-6 (still needs its own citation and date stamp).
- The two parts stay visually/structurally distinct in the response (fact answer, then refusal line) — never blended into one ambiguous sentence.

### FR-9: Unsupported Scheme Handling
**Behavior:** Query names a scheme outside the 5 supported (or FR-2 couldn't confidently match one).
**Rules:**
- Response states plainly that the scheme isn't covered, and lists the 5 supported scheme names.
- Does not attempt to answer from general knowledge or guess at the unsupported scheme's facts, even if the model "knows" them from training data — zero tolerance for un-cited facts anywhere in this bot.

### FR-10: Out-of-Corpus Fact Type Handling
**Behavior:** Query is about a supported scheme, but asks for a fact type not in scope ( historical returns, performance vs. benchmark).
**Rules:**
- This is a **distinct failure mode from FR-9** — the scheme is known, but the fact type isn't covered. Response should say so explicitly, not just fall back to a generic refusal.
- Redirect to the official factsheet link for that scheme rather than attempting a computed or approximate answer.
- Never compute, estimate, or infer a performance figure under any framing.

### FR-11: PII Rejection
**Behavior:** Detect and refuse any input containing PAN, Aadhaar, bank/account numbers, OTPs, email addresses, or phone numbers.
**Rules:**
- Refuse the entire query if PII is detected — do not process the non-PII part of that same message.
- Never echo the detected PII value back in the response (not even to confirm "I see you shared a PAN").
- Nothing containing PII is persisted/logged.

### FR-12: UI Requirements (Standalone Web Chat App)
**Behavior:** A minimal, self-contained chat interface.
**Rules:**
- Welcome message on load (facts-only framing stated up front).
- 3 clickable example questions to seed first-time use.
- Persistent, always-visible disclaimer (e.g., "Facts-only. No investment advice.") — not just shown once at welcome.
- Every bot answer renders its citation as a clickable link and shows the `Last updated from sources` stamp inline, not hidden behind a tooltip or secondary click.

---

## 4. Data & Corpus Requirements

**Source list:** see `SOURCE_LIST_RAGMFCHATBOT.md` for the full 15–25 URLs.
- **Scheme corpus** INDmoney scheme pages.
- **General corpus:** ICICI Pru AMC FAQ page, SEBI investor-education pages, AMFI knowledge-center pages.

**Freshness model:** live daily scheduled scrape, auto-refresh pipeline is being built.

---

## 5. Non-Functional Requirements

- **Citation correctness > latency.** A slow, correctly-cited answer is acceptable; a fast, wrongly-cited one is not.
- **No auth, no user accounts, no persistent user data.** This is a stateless factual lookup tool.
- **No PII storage anywhere in the pipeline** (ties directly to FR-11).
- **Must be reachable via a shareable link** for submission — not a local-only script.

---

## 6. Non-Goals (Explicitly Out of Scope)

| Non-goal | Why |
|---|---|
| Performance/returns computation or comparison | Explicitly excluded by the assignment brief; risk of implied advice |
| Multi-AMC support | Single AMC (ICICI Prudential) only, per chosen scope |
| Accounts, holdings lookup, portfolio features | No PII, no personalization — stays a pure factual lookup tool |

---

## 7. Acceptance Criteria

- [ ] Prototype deployed as a standalone web app with a shareable link
- [ ] All 8 intent types in Section 2 are correctly classified and routed
- [ ] Every factual answer (single-scheme and cross-scheme) includes ≥1 correct, specific citation and a per-answer date stamp
- [ ] Cross-scheme comparisons never include performance/return framing
- [ ] All advisory queries from `SAMPLE_Q&A_RAGMFCHATBOT.md` are correctly refused
- [ ] Mixed queries produce a distinct fact-then-refusal structure
- [ ] Unsupported-scheme queries list the 5 supported schemes
- [ ] Out-of-corpus fact-type queries are distinguished from unsupported-scheme queries
- [ ] PII inputs are refused and never stored or echoed
- [ ] UI shows welcome message, 3 example questions, persistent disclaimer

---