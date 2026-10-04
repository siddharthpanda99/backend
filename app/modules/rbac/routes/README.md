# `app/modules/rbac/routes/` — DELIBERATELY UNMOUNTED (107 handlers)

These **107 route handlers in 17 files are intentionally NOT mounted.** There is no
`rbac` entry in `app/core/routers.py`, so nothing includes this router and every
endpoint here returns 404.

This file exists so that the hold is **explicit and auditable** rather than an
accident of a forgotten registry line. The guard test
`Backend/tests/test_dead_routes_guard.py` asserts exactly this: every router module
on disk is either mounted or carries a recorded exemption with a reason.

## Why it is held, not merely forgotten

`docs/duplication-audit/MODULE-AUDIT-rbac.md` (finding C2) established:

- **46 of the 107 handlers would return 500 if mounted.** They import service
  modules that **were never written**. Git history (`git log --all
  --diff-filter=AMD -- src/common_lib/modules/rbac`) shows those paths were never
  added and never removed — they are absent by construction, not deleted:

  ```
  MISSING rbac.api.service
  MISSING rbac.audit.access_reviews
  MISSING rbac.audit.entitlement_requests
  MISSING rbac.cache.invalidation
  MISSING rbac.dashboard_permission_service
  MISSING rbac.debug.service
  MISSING rbac.delegation.service
  MISSING rbac.guest_access_service
  MISSING rbac.hardening.service
  MISSING rbac.integrations.service
  MISSING rbac.session_mfa_service
  MISSING rbac.tenant_service
  MISSING rbac.testing.service
  MISSING rbac.ownership_service
  MISSING rbac.plugins.service
  ```

- Every handler body wraps its service import in
  `try: ... except Exception as e: raise HTTPException(500, str(e))`, so the
  failure mode after a naive mount is a wall of **500s at request time, not a
  startup error**. That is worse than a 404: it looks like a runtime fault.

## Why the flag-gated route was rejected

The obvious alternative — mount behind a default-OFF feature flag — was considered
and rejected on evidence:

- `module_pruning.resolve_flag_path` prunes on a **declared default-False** flag
  (`_is_effectively_disabled` deliberately ignores where the `False` came from).
- `rbac` owns **264 `@node` wrappers** that are live and reachable today via MCP
  (`@node` → MCP passes, C3). Registering a default-OFF flag inside the `rbac.*`
  namespace risks pruning those live nodes on boot, which would move the
  `test_discover_nodes_count_unchanged_with_no_flag_disabled` baseline off 25 961.
- The audit's own C2 recommendation explicitly escalated this as a **decision
  needed**, not a mechanical fix.

## What is live today (do not confuse this with "rbac is off")

`rbac` is **not** globally disabled. These are other modules and are mounted:

- `/api/v1/control-center/rbac` (1 route)
- `/api/v1/governance/rbac/*` (11 routes — `governance` module)
- `/api/v1/team/{team_id}/rbac*` (9 routes — `team` module)

Only this directory is dark.

## To lift the hold (requires a product decision)

Two viable paths, per the audit — pick one deliberately:

1. **Mount only the 43 handlers whose services exist**, under `/api/v1/rbac`. Makes
   the `RBACAdminPage` Roles panel genuinely work. The 64 broken handlers stay
   unmounted. Requires splitting `routes/router.py`, which is an aggregate that
   `include_router`s all 16 sub-routers.

   > **CORRECTED 2026-10-04 — this section originally said 61 working / 46 broken. The
   > measured split is 43 working / 64 broken.** `routes/router.py` imports its services
   > inside lazy loader helpers that the handler bodies only *call*, so a top-level-import
   > scan reports **zero** breakage in that file and the aggregate looked entirely healthy.
   > Measured by resolving each handler's imports transitively through those helpers.
   > Ground truth: **19 of the 26 rbac subpackages contain only `__init__.py`** (`api`,
   > `audit`, `authorization`, `cache`, `delegation`, `field_security`, `guest`,
   > `hardening`, `integrations`, `machine_auth`, `ownership`, `plugins`, `policies`,
   > `roles`, `sessions`, `tenancy`, `testing`, …); their `__pycache__` holds only
   > `__init__`, so they provably never existed. The working code lives in flat
   > `*_service.py` files at the package root, not in the subpackages the router imports.
   > The original error was in the **unsafe** direction — it overstated how much works.
   > **Also note:** every handler wraps its import in `try/except → HTTPException(500)`, so
   > mounting the aggregate produces **request-time 500s, not a startup error** — strictly
   > worse than the current 404.
   >
   > **Viable flag name (found 2026-10-04, absent from the original audit):** gate this
   > behind a **sibling single-segment** flag such as `rbac_http`, default OFF, asserting
   > registration. Do **not** name it `rbac` — `is_enabled` resolves an unregistered flag
   > to `True`, so a `rbac` flag would prune all 264 live `@node`s on boot and move the
   > 25 961 baseline. A single-segment name cannot be an ancestor of `rbac.*`, so
   > `resolve_flag_path` can never select it for a node.
2. **Write the missing services first**, then mount all 107.

`platform-demo/libs/ui/common/src/services/rbacApi.ts` and
`pages/RBACAdminPage/` already target `/api/v1/rbac/*` and document in-code that
the router is unmounted — so lifting the hold is a real, planned need, not wishful.