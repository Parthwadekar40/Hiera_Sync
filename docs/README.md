# HieraSync AI — Documentation Set

Project report material for *"HieraSync AI — Smart Academic Workflow & Event Management System"*, Dept. of CSE (AI & ML),
S. B. Jain Institute of Technology, Management & Research, Nagpur — AY 2026‑27, Group 11
(Atul Gupta CM23019 · Tanvi Beer CM23020 · Tanish Kesharwani CM23020 · Parth Wadekar CM23040), guide **Mrs. Neha Gurnani**.

Source of truth for scope and wording: **`HieraSync_AI_30_Slide_Master_Presentation_v2.pdf`** (repository root) — 23 pages,
titled "30 Slide Master" because several pages carry more than one slide. Every document below cites the page(s) it
implements; [`08 §2`](08_conclusion_and_bibliography.md#2-the-decks-own-roadmap--this-document-set) maps the deck's own
10-section roadmap onto this set, and `07 §5` is the full slide→artifact matrix.
Re-extract the deck text at any time with `backend/.venv/bin/python - <<'PY' … pypdf … PY` (see `docs/06`).

| Doc | Covers (deck) | Report chapter it feeds |
|---|---|---|
| [`01_vision_problem_objectives.md`](01_vision_problem_objectives.md) | Slides 1–6 — title, agenda, abstract, vision, scope, background, problem statement, objectives, success criteria | Ch. 1 Introduction |
| [`02_literature_and_comparative_analysis.md`](02_literature_and_comparative_analysis.md) | Slides 7–8 — existing systems, literature survey, gaps, **plus the measured model comparison** | Ch. 2 Literature Survey / Ch. 6 Results |
| [`03_architecture_and_design.md`](03_architecture_and_design.md) | Slides 9–15, 17–19 — methodology, 3‑tier architecture, DFD L0/L1, use case & RBAC, core workflow, module table, sequence flow | Ch. 3 System Design / Ch. 4 Implementation |
| [`04_database_design.md`](04_database_design.md) | Slide 14 — collections, field-level data dictionary, ER model, indexes, integrity, lifecycle | Ch. 3.4 Database Design |
| [`05_engineering_justifications.md`](05_engineering_justifications.md) | Slide 16 + Slides 18–19 — stack justifications, risk-engine math, delivery policy, security, reliability, **limitations** | Ch. 3.5 Justifications / Ch. 6.1 |
| [`05_RBAC_MATRIX.md`](05_RBAC_MATRIX.md) | Slide 13 — the authoritative 10 × 16 capability matrix (generated from `rbac.py`) | Appendix; quoted by 403 responses |
| [`06_run_test_deploy.md`](06_run_test_deploy.md) | Slide 22 (code & testing) — quickstart, demo logins, verification suite, env reference, SMTP/Twilio/WhatsApp setup, Docker, troubleshooting | Ch. 5 Testing / Appendix A |
| [`07_advantages_roi_traceability.md`](07_advantages_roi_traceability.md) | Slides 20–21 — advantages, quantified ROI, applications, roadmap alignment, traceability, deliberate deltas | Ch. 6 Results & Discussion |
| [`08_conclusion_and_bibliography.md`](08_conclusion_and_bibliography.md) | Slides 22–23 — conclusion, objectives closure, complete bibliography with the deck's roadmap mapping, **Q&A appendix** for the viva | Ch. 7 Conclusion / References |
| [`benchmark_results.json`](benchmark_results.json) | — | committed output of `python -m app.engine.benchmarks --tasks 500` |

## How to read this set in 10 minutes

1. `01 §5–6` — the problem and the five objectives (the examiner's first question).
2. `05 §2` — the risk-engine formula, weights and a worked example (the "AI" in the title).
3. `02 §4` — *why it is better*, with numbers, including where it is **not** better.
4. `06 §1` + `06 §3` — run it, then `python scripts/e2e_demo.py` to see the deck's success criterion execute.

## One-paragraph summary

HieraSync AI replaces a department's registers, spreadsheets and WhatsApp threads with one role-aware portal: work is
assigned on a Kanban board, requests move through HOD → Principal approvals with an SLA and a hash-chained audit trail,
a deterministic eight-factor risk engine scores every open obligation from 0–100 and explains itself, and an automation
layer turns those scores into reminders and escalations on in-app, e-mail, SMS and WhatsApp — with analytics and
one-click exports that make NAAC/NBA evidence assembly a query instead of a project.
