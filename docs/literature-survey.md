# Literature Survey Pack — HiéraSync AI

Working bibliography for the research paper on this project. Twenty recent papers (2024 – 2026),
grouped by how you will use them, with what to take from each and a comparison table you can fill in.

**One-line positioning of this project (use in the Abstract / Introduction):**

> HiéraSync AI is a department-level academic operations system that combines a drag-and-drop activity
> calendar, a role-based approval desk and an LLM assistant over one Firestore-backed API. Unlike
> timetable generators or campus ERPs, it optimises the *coordination* work of a Head of Department —
> who is doing what, when, and what needs a decision today — and it makes every AI suggestion
> inspectable and reversible instead of automatic.

**The gap you are claiming** (say this explicitly; it is what makes the paper non-trivial):
most published systems either (a) generate schedules/timetables from constraints, or (b) digitise a
document approval chain. Almost none model *departmental coordination state* — activities, task
requests, approvals, notifications and workload — as one queryable store that an LLM can read from and
write back to with human confirmation. That is the design space of this project.

---

## Group A — Systems like yours (cite these as "similar / existing work")

| # | Paper | Link | Use it for |
|---|---|---|---|
| A1 | *Academic Affairs Management System (AAMS)* — IJCRT, Dec 2025 | <https://www.ijcrt.org/papers/IJCRT2512536.pdf> | Closest published match: Employee → HOD → Principal approval chain, role-based dashboards, real-time notifications, AI document summarisation, React + Tailwind front end. Cite as "the nearest existing system"; your differentiators are the calendar as the primary surface, drag-and-drop rescheduling, and ICS/CSV portability. It also surveys SAP SLCM, Fedena, OpenEduCat and EduSec — reuse that as your "commercial systems" paragraph. |
| A2 | *A Formal Document Approval Workflow for Business Process in Higher Education Institutions* — Velásquez-Angamarca et al., Springer LNNS vol. 1747 (CISTI) | <https://link.springer.com/chapter/10.1007/978-3-032-12879-9_8> | Rigorous framing of an approval workflow as a *business process* with rules, validation and audit trail. Cite in your design chapter to justify storing request state transitions and activity logs rather than free-text statuses. |
| A3 | *Optimizing Budget Request Flow Through WU-P Automate: An Efficient Tracking and Approval System* — IJAEMR 10(5), 2025 | <https://www.ijaemr.com/uploads/pdf/archivepdf/2025/IJAEMR_743.pdf> | A measured before/after study of exactly your problem class (processing time, error frequency, usability), with a Likert questionnaire and Cronbach's α = 0.90 reliability check. Copy its evaluation table structure for your Results chapter. |
| A4 | *Development of Digital-Based Academic Services System in Higher Education* — IRJMS 6(4):92–103, 2025, DOI 10.47857/irjms.2025.v06i04.04750 | <https://www.irjms.com/wp-content/uploads/2025/10/Manuscript_IRJMS_04750_WS.pdf> | Uses **Design Science Research** (build → iterate → evaluate) and reports registration time falling "from several days to minutes". This is the methodological template for a project-thesis: cite it to justify DSR as your research method. |
| A5 | *Student Management System: A Web-Based Solution for Academic Administration* — Shelke, Khan, Kapse, 2025 | <https://www.researchgate.net/publication/391478463_Student_Management_System_A_Web-Based_Solution_for_Academic_Administration> | Typical Django/Bootstrap implementation of the same problem space — a fair "conventional approach" baseline in your comparison table (no AI, no calendar engine, relational schema). |
| A6 | *Smart Campus Management System Using Modern Web and Networking Technologies* — Pardeshi, Bari, Patil, IJERT 15(2), Feb 2026, DOI 10.5281/zenodo.18815064 | <https://www.ijert.org/smart-campus-management-system-using-modern-web-and-networking-technologies-ijertv15is020681> | Architecture-level vocabulary for your System Design chapter: layered client–server, deployment, secure authentication, scalability, and the "AI + IoT + cloud" future-work framing. |

## Group B — Calendar, scheduling and workload (your priority module)

| # | Paper | Link | Use it for |
|---|---|---|---|
| B1 | *ScheduleMe: Multi-Agent Calendar Assistant* — Wijerathne et al., PACLIC 2025 (arXiv:2509.25693) | <https://arxiv.org/abs/2509.25693> · <https://aclanthology.org/2025.paclic-1.27/> | The state of the art for conversational calendar management: a supervisory agent delegating to event-creation, availability and conflict agents over Google Calendar. Your `/events` + AI assistant is a smaller, domain-specific instance of this pattern; cite for the interaction design and for its privacy section (calendar text sent to cloud LLMs) which applies directly to you. |
| B2 | *Togedule: Scheduling Meetings with Large Language Models and Adaptive Representations of Group Availability* — Song, Ashktorab & Malone (MIT), CSCW 2025, DOI 10.1145/3757513 (arXiv:2505.01000) | <https://arxiv.org/abs/2505.01000> | LLM that adapts which candidate slots are shown and recommends a final time per attendee priority — a formative study (N=10) then two controlled experiments (N=66) measuring cognitive load, speed and decision quality. The closest published relative of your Approvals "Suggested order" feature and your conflict-aware slot logic. |
| B3 | *Automated Scheduling for Thematic Coherence in Conferences* — Emu, Ahmed, Choudhury, ACM AIware 2024, DOI 10.1145/3664646.3665085 | <https://dl.acm.org/doi/10.1145/3664646.3665085> | Hard vs soft constraints in a CSP solved with NLP-weighted similarity (SciBERT + GPT-3.5), beating manual scheduling. Cite when you describe overlap detection (`timesOverlap`) as a *hard* constraint and preference/fairness as *soft* ones. |
| B4 | *On the Prospects of Incorporating LLMs in Automated Planning and Scheduling* — Pallagani et al., ICAPS 2024 (arXiv:2401.02500) | <https://ojs.aaai.org/index.php/ICAPS/article/download/31503/33663/35560> | Survey of 53 papers, with the honest conclusion that LLM planners lag symbolic solvers on correctness/completeness. Perfect for your Discussion: it justifies keeping the deterministic checker in the backend and using the LLM only to *propose*. |
| B5 | *Artificial Intelligence for Real-Time Automated Timetable and Faculty Scheduling in Colleges* — All Scientific Journal 10(3), 2025 | <https://allscientificjournal.com/assets/archives/2025/vol10issue3/10072.pdf> | Explicitly describes calendar views plus **heat maps for faculty load**, conflict alerts and resolution suggestions — the same UI vocabulary as your heat view. Cite to justify that design decision. |
| B6 | *Adaptive Scheduler: AI Optimization of Academic Timetable* — IJSDR, 2025 | <https://ijsdr.org/papers/IJSDR2504317.pdf> | Genetic-algorithm scheduler with a faculty-feedback loop and PDF export, evaluated on time saved and stakeholder satisfaction. Use as the "optimisation-based" column of your comparison table; note it has no approval workflow, which yours does. |
| B7 | *Allocation Model for Workload Balance: A Case Study* — Guerreiro, Santos, Santos, Tereso, Springer LNNIS 1226 (HIS 2023), published 2025, DOI 10.1007/978-3-031-78934-2_10 | <https://link.springer.com/chapter/10.1007/978-3-031-78934-2_10> | Quantified workload-balance model you can reference for any "fair distribution of duties" claim, with a real institutional case study rather than a synthetic one. |
| B8 | *Machine Learning-Based Prediction System for Optimized Faculty Exam Duty Allocation* — Naik & Gururaja, IJERT 14(01), 2026, DOI 10.17577/IJERTCONV14IS010050 | <https://www.ijert.org/machine-learning-based-prediction-system-for-optimized-faculty-exam-duty-allocation-ijertconv14is010050> | Feature list worth reusing (prior duty count, experience, availability, leave status, preferences) and — more usefully for you — a candid limitations section (synthetic data, no hyper-parameter tuning) to contrast with your real-workflow evaluation. |

## Group C — AI/LLM in academic administration (your assistant + reports)

| # | Paper | Link | Use it for |
|---|---|---|---|
| C1 | *LLM Agents for Education: Advances and Applications* — Chu et al., EMNLP 2025 Findings (arXiv:2503.11733) | <https://arxiv.org/abs/2503.11733> | The survey to cite for "LLM agents in education": taxonomy, datasets/benchmarks, and the deployment challenges (hallucination, over-reliance, integration with existing ecosystems) that you address with human-in-the-loop confirmation. |
| C2 | *AI-Powered Educational Agents: Opportunities, Innovations, and Ethical Challenges* — MDPI *Information* 16(6):469, 2025, DOI 10.3390/info16060469 | <https://www.mdpi.com/2078-2489/16/6/469> | Peer-reviewed venue for the ethics/governance paragraph: consent, bias, and the "why does the AI rank my request first?" question your UI answers with a visible reason string. |
| C3 | *Optimizing University Administrative Services with Generative AI: Evidence from Email Inquiry Reduction and Assistant Performance* — López-Galisteo, MDPI *Information* 17(6):587, 2026, DOI 10.3390/info17060587 | <https://www.mdpi.com/2078-2489/17/6/587> | The strongest **measurement** paper for you: a real university deployment, query volumes before/after, performance broken down by query complexity, and the framing that the assistant is "augmentative, not autonomous". Model your Impact/Evaluation chapter on it. |
| C4 | *Smart Innovation Hub: An AI-Enabled Information System for Challenge-Based Innovation and Capstone Project Matching in Higher Education* — Albalawi, MDPI *Information* 17(6):588, 2026, DOI 10.3390/info17060588 | <https://www.mdpi.com/2078-2489/17/6/588> | Same issue, same journal: a full-stack AI information system for a university unit. Useful to show your work belongs to a recognised, currently active line of research rather than being a lone college project. |
| C5 | *Institutional approaches to generative AI management in higher education: a systematic review* — Frontiers in Education, 2026, DOI 10.3389/feduc.2026.1814426 | <https://www.frontiersin.org/journals/education/articles/10.3389/feduc.2026.1814426/full> | Pooled numbers for your Introduction: faculty administrative-workload reduction (62%), task-completion time cuts (>50%), automation of routine processes (~70%), plus the barriers (privacy, infrastructure, cultural resistance). |
| C6 | *LLM-Augmented Academic Analytics* (Retrieval-Augmented Academic Analytics Framework, RAAF) — JISEM, accepted 2025 | <https://jisem-journal.com/index.php/journal/article/download/14598/7035/25171> | RAG over institutional BI so staff can ask natural-language questions of live data. This is precisely your AI dashboard-summary endpoint; cite for architecture (retriever → context → generator) and for why static dashboards are insufficient. |

## Group D — Justifying your stack, security and evaluation method

| # | Paper | Link | Use it for |
|---|---|---|---|
| D1 | *Firestore: The NoSQL Serverless Database for the Application Developer* — Google Research (SIGMOD-industry) | <https://storage.googleapis.com/gweb-research2023-media/pubtools/7076.pdf> | Authoritative source for the properties you rely on: YCSB latency under load, relatively stable notification latency as Listen connections grow, and how document/field *size* (not count) drives commit latency. Cite it in Technology Overview when defending Firestore. |
| D2 | *Evaluation of NoSQL in the Energy Marketplace with GraphQL Optimization* — arXiv:2403.04935, 2024 | <https://arxiv.org/abs/2403.04935> | Concrete, quotable Firestore-vs-MySQL numbers (Firestore ≈25 writes/s vs MySQL ≈45; ~$1.30 vs ~$35 for 1M objects; 66.7 s Firestore vs 0.9 s MySQL on a million-doc range scan) and its conclusion that Firestore wins on cost/scalability while losing on large range queries. Use it honestly in your Performance/Discussion section — your range queries are department-scoped, which is exactly the case where Firestore behaves well. |
| D3 | *Cloud Computing: Google Firebase Firestore Optimization Analysis* — Semma, Ali, Saerozi, Mansur, Kusrini, *IJEEEE* 29(3):1719–1728, 2023, DOI 10.11591/ijeecs.v29.i3.pp1719-1728 | <https://www.researchgate.net/publication/368885308_Cloud_computing_google_firebase_firestore_optimization_analysis> | Best-practice evidence for the denormalisation your app uses: keep aggregate/summary documents separate and pre-compute, cutting read counts, response size and cost. Justifies your `activity_logs`, per-user `settings` and snapshot fields. |
| D4 | *Securing Academic Social Platforms: Implementing Role-Based Access Control in University-Based Digital Systems* — IJRTI 10(5), May 2025 | <https://www.ijrti.org/papers/IJRTI2505044.pdf> | RBAC role hierarchy (read-only student → editing faculty → administering staff) argued for an academic platform. Cite next to your `RoleEnum` + `check_role()` design and the HOD-only approve guards you added. |
| D5 | *System Usability Scale in Information System Application Development: A Systematic Mapping Study* — IJATIS 2(2), 2025, DOI 10.57152/ijatis.v2i2.2275 | <https://journal.irpi.or.id/index.php/ijatis/article/view/2275> | Maps 30 Springer-indexed IS papers (2021–2025) that used SUS: respondent counts, criteria and typical score ranges. Cite it to justify choosing SUS and to set expectations for sample size and reporting. |
| D6 | *System Usability Scale (SUS) Model in Evaluating Internal Quality Audit Systems for Accreditation Process Optimization* — JAIC 9(2):511–516, 2025, DOI 10.30871/jaic.v9i2.9210 | <https://jurnal.polibatam.ac.id/index.php/JAIC/article/view/9210> | SUS applied to a higher-education management system, including comparison against older academic systems and recommendations for workflow optimisation and AI-driven automation — the closest evaluation analogue to what you will report. |
| D7 | *Effects of task interruptions caused by notifications from communication applications on strain and performance* — Ohly & Bastin, *J. Occupational Health* 65(1):e12408, 2023, DOI 10.1002/1348-9585.12408 | <https://onlinelibrary.wiley.com/doi/full/10.1002/1348-9585.12408> | Field experiment (N=247) showing that fewer notification interruptions → better performance and lower strain, and that *batching* beats total silencing (which raises FoMO). This is your justification for the prioritised, digest-style Notification Centre instead of per-event alerts. |

---

## Literature-survey table (fill this in — examiners look for it)

Rows = the systems above; cells = present / partial / absent. Your rows should read like a gap
analysis, not a feature brag: every column where existing work says "no" is your contribution.

| System / paper | Calendar as primary UI | Drag-drop reschedule with conflict check | Approval workflow + audit trail | Workload view per faculty | AI suggestion with reason + confirm | Offline / demo fallback | Export (.ics / CSV) | Role-based access |
|---|---|---|---|---|---|---|---|---|
| AAMS (A1) | no | no | yes | partial | summarisation only | no | partial | yes |
| OpenEduCat / Fedena / SAP SLCM (via A1) | no | no | yes | partial | no | no | yes | yes |
| Timetable GA systems (B5, B6) | partial | no | no | yes | no | no | PDF | partial |
| ScheduleMe (B1) | yes (Google Calendar) | via NL only | no | no | yes | no | no | no |
| Togedule (B2) | partial | no | no | no | yes | no | no | no |
| **HiéraSync AI (this project)** | **yes** | **yes** | **yes** | **yes (heat view)** | **yes (Suggested order)** | **yes (in-memory double)** | **yes (ICS + CSV)** | **yes (5 roles + bootstrap)** |

## Evaluation plan you can actually run from this codebase

Report both a *system* metric and a *user* metric; one alone reads as incomplete.

1. **Functional / engineering results** (already reproducible here): 34-endpoint API sweep with zero
   5xx responses; unit tests for the calendar utilities (9 cases); bootstrap-path tests for the
   first-login deadlock; request→task conversion on approval. Tabulate pass/fail per suite.
2. **Performance**: read/write latency of `/events` for one department at 100 / 1 000 / 10 000
   documents, plus Firestore document-read counts (D3's methodology) — that turns "we used Firestore"
   into a measured claim.
3. **Usability**: SUS (10 items, 5-point Likert) with 15–20 faculty/HOD respondents; report mean ± SD
   and map to the adjective scale; add one task-based measure (time to move a conflicting activity,
   time to approve a request) as D6 and A3 did.
4. **AI quality**: for N=30 real approval requests, compare the assistant's suggested order against the
   HOD's final order; report precision@1 / Kendall's τ, and have the HOD rate each reason string 1–5.
   Also report what the AI got *wrong* — B4's caution is your shield here.
5. **Workload/fairness**: variance of activities-per-faculty before vs after using the queue.

## What not to over-claim

- You are not proposing a new scheduling algorithm — cite B3/B6 and position your contribution as the
  integrated coordination state + human-in-the-loop AI, which is the honest and defensible claim.
- The LLM never mutates the schedule autonomously in this design; say so, and cite C1/C3 for the
  "augmentative not autonomous" framing.
- Data is single-department and self-reported; sample size will be small. State it as a limitation with
  a concrete future work item (multi-department tenancy, calendar sync with the university's existing
  Google Workspace).

## Minimal BibTeX

```bibtex
@inproceedings{wijerathne2025scheduleme,
  title   = {ScheduleMe: Multi-Agent Calendar Assistant},
  author  = {Wijerathne, Oshadha and Nimasha, Amandi and Fernando, Dushan and de Silva, Nisansa and Perera, Srinath},
  booktitle = {PACLIC 2025}, year = {2025}, note = {arXiv:2509.25693},
  url = {https://aclanthology.org/2025.paclic-1.27/}
}
@article{song2025togedule,
  title = {Togedule: Scheduling Meetings with Large Language Models and Adaptive Representations of Group Availability},
  author = {Song, Jaeyoon and Ashktorab, Zahra and Malone, Thomas W.},
  journal = {Proceedings of the ACM on Human-Computer Interaction (CSCW 2025)}, year = {2025},
  doi = {10.1145/3757513}, url = {https://arxiv.org/abs/2505.01000}
}
@article{albalawi2026smart,
  title = {Smart Innovation Hub: An AI-Enabled Information System for Challenge-Based Innovation and Capstone Project Matching in Higher Education},
  author = {Albalawi, Omar H.}, journal = {Information}, volume = {17}, number = {6}, pages = {588},
  year = {2026}, doi = {10.3390/info17060588}, url = {https://www.mdpi.com/2078-2489/17/6/588}
}
@inproceedings{emu2024automated,
  title = {Automated Scheduling for Thematic Coherence in Conferences},
  author = {Emu, Mahzabeen and Ahmed, Tasnim and Choudhury, Salimur},
  booktitle = {AIware 2024}, year = {2024}, doi = {10.1145/3664646.3665085},
  url = {https://dl.acm.org/doi/10.1145/3664646.3665085}
}
@inproceedings{pallagani2024prospects,
  title = {On the Prospects of Incorporating Large Language Models (LLMs) in Automated Planning and Scheduling (APS)},
  author = {Pallagani, Vishal and Muppasani, Bharath and Roy, Kaushik and Fabiano, Francesco and Loreggia, Andrea and Murugesan, Keerthiram and Srivastava, Biplav and Rossi, Francesca and Horesh, Lior and Sheth, Amit},
  booktitle = {ICAPS 2024}, year = {2024}, url = {https://arxiv.org/abs/2401.02500}
}
@article{chu2025llmagents,
  title = {LLM Agents for Education: Advances and Applications},
  author = {Chu, Zhendong and Wang, Shen and Xie, Jian and Zhu, Tinghui and Yan, Yibo and Ye, Jinheng and Zhong, Aoxiao and Hu, Xuming and Liang, Jing and Yu, Philip S. and Wen, Qingsong},
  journal = {EMNLP 2025 Findings}, year = {2025}, url = {https://arxiv.org/abs/2503.11733}
}
@article{lopezgalisteo2026optimizing,
  title = {Optimizing University Administrative Services with Generative AI: Evidence from Email Inquiry Reduction and Assistant Performance},
  author = {L{\'o}pez-Galisteo, Antonio Julio}, journal = {Information}, volume = {17}, number = {6}, pages = {587},
  year = {2026}, doi = {10.3390/info17060587}, url = {https://www.mdpi.com/2078-2489/17/6/587}
}
@incollection{velasquez2026formal,
  title = {A Formal Document Approval Workflow for Business Process in Higher Education Institutions},
  author = {Vel{\'a}squez-Angamarca, V. and Arce-Cuesta, D. and Oyola-Flores, C. and Garc{\'i}a-Pes{\'a}ntez, A. and Pes{\'a}ntez-Avil{\'e}s, F. and C{\'a}rdenas-Tapia, J.},
  booktitle = {Information Systems and Technologies (CISTI)}, series = {LNNS}, volume = {1747}, publisher = {Springer},
  year = {2026}, doi = {10.1007/978-3-032-12879-9_8}
}
@incollection{guerreiro2025allocation,
  title = {Allocation Model for Workload Balance: A Case Study},
  author = {Guerreiro, R. and Santos, G. and Santos, A. S. and Tereso, A. P.},
  booktitle = {Hybrid Intelligent Systems (HIS 2023)}, series = {LNNIS}, volume = {1226}, publisher = {Springer},
  year = {2025}, doi = {10.1007/978-3-031-78934-2_10}
}
@misc{google2023firestore,
  title = {Firestore: The NoSQL Serverless Database for the Application Developer},
  author = {{Google Research}}, year = {2023},
  url = {https://storage.googleapis.com/gweb-research2023-media/pubtools/7076.pdf}
}
@article{semma2023firestoreopt,
  title = {Cloud Computing: Google Firebase Firestore Optimization Analysis},
  author = {Semma, Andi Bahtiar and Ali, Mukti and Saerozi, Muh and Mansur and Kusrini},
  journal = {Indonesian Journal of Electrical Engineering and Computer Science}, volume = {29}, number = {3},
  pages = {1719--1728}, year = {2023}, doi = {10.11591/ijeecs.v29.i3.pp1719-1728}
}
@article{ohly2023notifications,
  title = {Effects of Task Interruptions Caused by Notifications from Communication Applications on Strain and Performance},
  author = {Ohly, Sandra and Bastin, Luca}, journal = {Journal of Occupational Health}, volume = {65}, number = {1},
  pages = {e12408}, year = {2023}, doi = {10.1002/1348-9585.12408}
}
```

Every entry above was read off the publisher's own page, but re-open each PDF before submission and check
the volume/page numbers: an examiner who finds one wrong author name distrusts the whole bibliography.

## Reading order (start here, three sittings)

1. **C1 → C2** — establishes that LLM agents in education is a live research area, and gives you the
   challenge list (hallucination, over-reliance, integration) your design answers.
2. **B1 → B2 → B4** — calendar/scheduling agents and their limits; write your Related Work section from
   these three.
3. **A1 → A3 → A4** — the "similar system + how they measured it + which method they used" trio; copy
   their chapter structure for yours.
4. **D1 → D2 → D5/D6** — then your Technology Overview and Evaluation chapters practically write
   themselves.
