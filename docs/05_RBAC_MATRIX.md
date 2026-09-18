# RBAC Capability Matrix — authoritative reference

Generated from `backend/app/auth/rbac.py` (`MATRIX`, `CAPABILITIES`, `ANALYTICS_SCOPE`) — the code the `403`
payloads quote. Deck reference: **Slide 13, "Use Case Diagram & Granular RBAC Permissions"**.

* `GET /api/v1/workflow/rbac` returns this matrix at runtime, so the SPA, this file and the API cannot disagree.
* 10 roles × 16 capabilities. ✅ = granted, · = denied.
* Role aliases keep legacy v1 documents working: `PROFESSOR→TEACHER`, `ASSISTANT_PROFESSOR→TEACHER`,
  `RESEARCH_ASSOCIATE→TA`, `DEPARTMENT_ADMIN→STAFF`.

## Capabilities (16)

`assign_tasks`, `approve_hod`, `approve_principal`, `view_analytics`, `manage_system`, `manage_users`, `create_events`, `update_subtasks`, `update_own_task`, `review_join_requests`, `link_goals`, `export_reports`, `configure_notifications`, `override_risk_weights`, `chat_with_ai`, `run_automation`

`run_automation` (manual job triggers, outbox flush) is new in v2 so operator/demo actions are gated like every
other mutation. `chat_with_ai`, `configure_notifications`, `override_risk_weights`, `export_reports`,
`review_join_requests`, `link_goals` have no equivalent in v1's inline `check_role([...])` lists.

## Matrix

| Role | `assign_tasks` | `approve_hod` | `approve_principal` | `view_analytics` | `manage_system` | `manage_users` | `create_events` | `update_subtasks` | `update_own_task` | `review_join_requests` | `link_goals` | `export_reports` | `configure_notifications` | `override_risk_weights` | `chat_with_ai` | `run_automation` |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| **ADMIN** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **PRINCIPAL** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **HOD** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **TEACHER** | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · |
| **FACULTY** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **TA** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | · |
| **STUDENT** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | · |
| **STUDENT_REP** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | · |
| **LAB_ASSISTANT** | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · |
| **STAFF** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | · |

## Analytics scope (row-level, not menu-level)

| Role | Analytics scope | Effective visibility |
|---|---|---|
| `ADMIN` | `full_institute` | every department |
| `PRINCIPAL` | `full_institute` | every department |
| `HOD` | `department` | own `department_id` only |
| `TEACHER` | `self` | own assignments |
| `FACULTY` | `self` | own assignments |
| `TA` | `none` | public event feed only |
| `STUDENT` | `none` | public event feed only |
| `STUDENT_REP` | `none` | public event feed only |
| `LAB_ASSISTANT` | `none` | public event feed only |
| `STAFF` | `none` | public event feed only |

The scope is applied *inside the query*, so an unauthorised role cannot read another department's numbers even
by calling the endpoint directly.

## Enforcement pattern

```python
@router.post("/{approval_id}/decide")
async def decide(..., user: User = Depends(require("approve_hod"))):
```

Denial text: `Role 'FACULTY' requires capability 'approve_hod'. See docs/05_RBAC_MATRIX.md.`

Approval **stage** authorisation is separate from RBAC: `app/engine/approvals.py` returns `wrong_stage` if a role
acts out of turn, and a single-stage kind (`leave`, `generic`) completes at the HOD by design — the deck's
Principal stage applies to `event`, `purchase` >= Rs 50,000, `budget`, `deadline_change` and `outcome_approval`
(`GET /api/v1/workflow/policies` is the live source). AuthN: JWT HS256 (`sub=email`), bcrypt cost 12, v1
decorators retained for backward compatibility.
