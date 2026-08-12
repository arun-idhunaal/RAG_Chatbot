# PRD §7 Acceptance Checklist — Phase 6 sign-off

**Repo:** https://github.com/arun-idhunaal/RAG_Chatbot  
**Deploy URL:** _add after hosting_  
**Eval report:** `data/eval/latest_report.md` (from `python -m scripts.run_eval`)

## Automated gate

- [ ] `python -m scripts.run_eval` → Gate OK (no open S0/S1 in EDGECASES.md §12)
- [ ] `python -m scripts.health_check` → OK

## PRD §7 criteria (on deployed URL)

- [ ] Prototype deployed as a standalone web app with a shareable HTTPS link
- [ ] All 8 intent types correctly classified and routed
- [ ] Every factual answer (single + cross-scheme) has ≥1 correct citation + per-answer date stamp
- [ ] Cross-scheme comparisons never include performance/return framing
- [ ] Advisory queries from Sample Q&A correctly refused
- [ ] Mixed queries = distinct fact-then-refusal
- [ ] Unsupported-scheme queries list the 5 supported schemes
- [ ] Out-of-corpus fact-type queries distinguished from unsupported-scheme
- [ ] PII inputs refused and never stored or echoed
- [ ] UI shows welcome, 3 example questions, persistent disclaimer

## Live spot checks (EC-X)

- [ ] **EC-X-01** PII-first: compound message with PAN → FR-11 only, no echo
- [ ] **EC-X-02** Comparison + “which should I pick?” → values + refusal, never pick a scheme
- [ ] **EC-X-03** Lock-in + suitability → fact then separate refusal
- [ ] **EC-X-04** (ops) Empty index shows unavailable — no invented facts

## UI (EC-UI-01…04)

- [ ] Welcome + 3 examples on load
- [ ] Disclaimer always visible
- [ ] Citation links + inline date stamp
- [ ] Mixed answers visually distinct

## Sign-off

| Role | Name | Date | Result |
|---|---|---|---|
| Builder | | | |
| Reviewer | | | |
