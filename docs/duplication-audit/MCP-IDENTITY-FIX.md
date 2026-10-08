# MCP Identity Fix — removing the fabricated admin identity

**Status:** complete, uncommitted (central session commits)
**Scope:** `Backend Monorepo/Backend/app/mcp/**` + one new test file
**Base defect:** `app/mcp/tools/users.py:28` — `user_get_current` returned
`{"id": "system", "role": "admin", "permissions": ["*"]}` to every caller.

---

## 1. Where the identity comes from now

The root cause was not the one hardcoded line — it was that **`app/mcp/**` had
no request context at all**: no `ContextVar`, and `server.py` performed no token
verification. That void is *why* the mock was written.

The fix supplies the missing context rather than replacing one guess with another.

### New module: `app/mcp/identity.py`

- A `ContextVar` holding the current `Principal`, defaulting to `None`.
- `None` means **"no credential was presented"** — never an admin.
- `current_principal()` — what tool bodies call. Returns the bound principal, or
  an explicit **anonymous** `Principal` when nothing is bound. It has no code
  path that returns a fabricated identity.
- `resolve_mcp_principal(authorization_header)` — verifies a bearer token and
  returns a principal. **Fails closed**: absent, malformed, expired, or
  badly-signed tokens all yield anonymous.
- `bind_principal()` / `reset_principal()` — request-scoped, with a `finally`
  reset so one request's identity can never leak to the next on a pooled worker.

### Wired at the transport: `app/mcp/routes.py:146`

`call_mcp_tool` now takes the `Request`, resolves the principal from the
`Authorization` header, binds it for the duration of the call, and always resets
in a `finally`.

### Verification is delegated, never reimplemented

`identity.py` **does not decode tokens**. It calls
`common_lib.modules.auth.identity_context.resolve_principal` (the module already
committed as `80c20a643`) — the same `decode_access_token` code path that
`app/modules/auth/dependencies/authz.py:53` uses for HTTP auth. There is exactly
one verifier, so there is no second, weaker one. A test asserts
`decode_access_token` never appears in `identity.py`.

### Service identity is requested, never inferred

`resolve_mcp_principal` passes `allow_service_identity=False`. An unauthenticated
MCP caller therefore **cannot** silently inherit ambient service privilege by
omission. A tool that genuinely needs the service principal must pass
`include_service_identity=True` — a visible, auditable caller decision.

**No feature flag.** There is no switch that re-enables the permissive path.
This ships default-ON, unconditionally.

---

## 2. Can MCP clients present a verifiable token? What I found

I traced all three transports rather than assuming. They are **not** equally
authenticated:

| Transport | Mount | Authenticated? |
|---|---|---|
| `POST /api/v1/mcp/tools/call` | `include_router` | **Yes** — but identity was unreachable from the tool |
| `/mcp/transport` (SSE) | `app.mount` | **No** — raw ASGI mount |
| stdio (`standalone_node_server.py`) | subprocess | N/A (trusted local) |

### HTTP — authenticated, but the identity was dropped

`ROUTER_DEFINITIONS` declares the MCP router with `"auth": True`
(`app/core/routers.py:1618-1624`). That flag **is** consumed:
`mount_router_entry` does `deps = global_deps if entry.get("auth", True) else []`
(`app/core/router_hot_mount.py:300`), and `global_deps` is
`[Depends(get_current_active_user)]` when `DEV_MODE` is off
(`app/main.py:1593`).

So the HTTP transport *did* verify a bearer token. But the resulting `User`
object was never reachable from inside a tool — FastMCP hands a tool only its
declared arguments. **That** is the gap that made the fabricated identity look
necessary. This change closes it.

### SSE — genuinely unauthenticated

`app/main.py:1629` mounts SSE with `app.mount(...)`. `app.mount` attaches a raw
ASGI app and **bypasses the router dependency mechanism entirely**, so
`get_current_active_user` never runs on that path and there is no credential to
verify.

**Not fixed here** — `app/main.py` is off-limits to this change. Reported below.

### stdio

`app/mcp/standalone_node_server.py` registers only the `@node` bridge
(`register_dynamic_node_tools`); it never calls `register_user_tools`, so
`user_get_current` is **not reachable via stdio at all**.

---

## 3. What happens with no credential — stated plainly

**The tool honestly reports `anonymous`.** That is the correct outcome.

```json
{
  "id": "anonymous",
  "role": "anonymous",
  "permissions": [],
  "is_authenticated": false,
  "is_service": false,
  "is_admin": false,
  "source": "none",
  "reason": "no MCP request context is active"
}
```

This is a normal result, not an error. An SSE client calling `user_get_current`
gets `anonymous` — truthfully, because the platform has not established who it
is. Previously it got `admin` with `["*"]`, which was a lie the platform told
itself in order to look useful.

**What is lost:** any workflow that depended on `user_get_current` to *bootstrap*
an identity — e.g. an agent asking "what am I allowed to do?" and receiving a
permission list without having to authenticate — now gets an empty list. That is
a real behavioural break, and it is the correct one. **The fix is for the client
to authenticate, not for the server to guess.** A `["*"]`-bearing admin was never
a permission grant; it was an unearned assertion that any downstream
authorization decision built on it was unsound.

Note the honest inverse is preserved: a caller with a genuinely verified admin
token **does** get `role: "admin"` and `is_admin: true` — and even then the `["*"]`
wildcard is stripped from its claims. The fix does not merely suppress admin; it
makes admin *earned*.

---

## 4. Wildcard sweep — `app/mcp/**`

Scanned for `["*"]`, `role: admin`, and fabricated-identity shapes.

**Found and fixed — 2 items:**

1. `app/mcp/tools/users.py:32` — the reported defect. **Fixed.**
2. `app/mcp/tools/db_studio/migration.py:188` — **found during this sweep.**
   `approve_deployment(deployment_id, approved_by: str = "admin")` fabricated an
   *administrator attribution in the audit trail*: any caller omitting the
   argument had a deployment approved in "admin"'s name. Not the same bug, but the
   same class — the platform asserting an identity it never established.
   Now defaults to the resolved caller id, or `"anonymous"` when unverified.
   Signature stays backward-compatible (still accepts a string).

**Reviewed and correctly left alone:**

- `app/mcp/tools/db_studio/administration.py:94,105,112` — `admin_create_role`,
  `admin_list_roles`, `admin_grant_role`. These are *real* RBAC management tools
  that genuinely administer roles. `admin` here is a tool name, not a fabricated
  identity.
- No other fabricated identity (`"id": "system"`, hardcoded `current_user`,
  `is_admin: True`) exists anywhere in `app/mcp/`.

**Regression guard:** `test_no_fabricated_admin_literal_in_mcp_surface` walks every
`app/mcp/**/*.py` with `ast` and fails if a dict literal containing
`permissions: ["*"]` or `{id: "system", role: "admin"}` reappears in executable
code. It is AST-based deliberately — a text scan would also match the docstrings
that *describe* the removed bug.

---

## 5. Tests and red/green evidence

`Backend Monorepo/Backend/tests/app/mcp/test_mcp_identity_fails_closed.py` — **21 tests, all passing.**

The tests invoke the **real registered tool through a real FastMCP instance**
rather than re-implementing its body, so assertions are against the shipped code
path. Tokens are signed with the verifier's own `SECRET_KEY`/`ALGORITHM`, so
identities under test are genuinely verified.

### Green

```
$ .venv/bin/python -m pytest tests/app/mcp/test_mcp_identity_fails_closed.py -q
.....................                                                    [100%]
21 passed in 37.73s
```

### Red proof A — restore the original fabricated identity

Body replaced with the exact original mock
(`return {"id": "system", "role": "admin", "permissions": ["*"]}`):

```
FAILED test_cannot_return_admin_with_wildcard_permission
FAILED test_never_returns_wildcard_permission_in_any_mode
FAILED test_unauthenticated_caller_is_anonymous_not_admin
FAILED test_cannot_return_an_unverified_identity
FAILED test_no_context_defaults_to_anonymous_not_admin
FAILED test_bound_principal_is_visible_to_the_tool
FAILED test_verified_admin_token_reports_admin_truthfully
FAILED test_service_identity_is_not_inferred_by_default
FAILED test_service_identity_requires_explicit_request
FAILED test_service_identity_still_cannot_carry_the_wildcard
FAILED test_service_identity_enabled_without_id_refuses_to_mint
FAILED test_no_fabricated_admin_literal_in_mcp_surface
12 failed, 9 passed in 43.66s
```

The headline assertion `test_cannot_return_admin_with_wildcard_permission` — which
asserts exactly the original defect shape — went red, as did the AST sweep.

### Red proof B — restore the missing request context (the root cause)

`bind_principal` / `resolve_mcp_principal` removed from `call_mcp_tool`:

```
FAILED test_http_call_endpoint_binds_principal_for_the_tool
1 failed, 20 passed in 38.26s
```

Precisely one failure — the test that proves the transport actually binds an
identity to the tool.

### Green restored, with checksum proof

Both files were restored from backup and their md5sums verified against the
pre-red-proof values before re-running:

```
25c11234f9bdf38c55cd858b5d64cfb5  app/mcp/tools/users.py   (matches pre-mutation)
f6df7025833142709cdff32fc948323e  app/mcp/routes.py        (matches pre-mutation)
21 passed in 37.73s
```

### Contamination check

```
$ grep -rniE "NEUTERED|MUTATED|RED PROOF" <all 5 touched files>
CLEAN: zero occurrences
```

A repo-wide sweep found zero `NEUTERED` markers. The handful of `MUTATED` hits
elsewhere are pre-existing unrelated English prose (a vision prompt, a governance
test docstring, a flag-listener log message) — not test defects.

### Pre-existing tests not weakened

`common_lib/modules/auth/tests/test_identity_context_fails_closed.py` — **13 passed**,
both before and after this change.

---

## 6. What a client that expects an admin identity must do instead

1. **Authenticate.** Call over `POST /api/v1/mcp/tools/call` with a valid
   `Authorization: Bearer <jwt>`. That is the only MCP transport that verifies a
   credential. The token's `sub` becomes `id`; its `role`/`permissions` claims
   become the reported identity.
2. **Branch on `is_authenticated`, not on `role`.** `anonymous` is a valid,
   correct response — treat it as "no credential", not as an error.
3. **If you are an internal job with no user token,** configure the service
   identity (`SERVICE_IDENTITY_ENABLED`, `SERVICE_IDENTITY_ID`, `SERVICE_IDENTITY_ROLE`,
   `SERVICE_IDENTITY_PERMISSIONS`) and call with `include_service_identity=True`.
   Grant capabilities explicitly; the wildcard is stripped and will not appear.
4. **Do not rely on `permissions: ["*"]`.** It is unreachable by design — from
   token claims and from service config alike.
5. **SSE clients** will always see `anonymous` until `app/main.py:1629` gains auth
   (see below). If you need an identity over SSE, use the HTTP tool-call endpoint.

---

## 7. Reported, not edited (off-limits files)

| Location | Finding |
|---|---|
| `app/main.py:1629` | SSE mounted via `app.mount`, bypassing router deps → **no auth on the SSE MCP transport**. Should be wrapped with a dependency that resolves and binds a principal, so SSE callers get real identities instead of anonymous. |
| `app/main.py:1593` | `global_deps = [Depends(get_current_active_user)] if not settings.DEV_MODE else []` — in `DEV_MODE` the global dep is empty, so `user_get_current` correctly reports anonymous on HTTP too. Worth confirming `DEV_MODE` is never on outside local dev. |

Neither was edited; both are outside this change's permitted surface.

---

## 8. Files changed

**Modified**
- `app/mcp/tools/users.py` — fabricated identity replaced with `current_principal()`;
  `include_service_identity` opt-in; relative import `..mcp_dependencies` fixed to
  absolute (G5); unused `Optional` import dropped.
- `app/mcp/routes.py` — `call_mcp_tool` takes `Request`, resolves + binds the
  principal, resets in `finally`.
- `app/mcp/tools/db_studio/migration.py` — `approve_deployment` no longer defaults
  `approved_by` to the literal `"admin"`.

**Added**
- `app/mcp/identity.py` — request-scoped principal context.
- `tests/app/mcp/test_mcp_identity_fails_closed.py` — 21 tests.

**Not touched** (other active agents): `app/mcp/mcp_dependencies.py`,
`app/mcp/server.py`, `app/core/routers.py`, `app/main.py`, `common_lib/**`,
`pyproject.toml`. Note the `git diff` for `routes.py` and `migration.py` also
contains a concurrent session's `_await_node_tools` / formatting work — the
`call_mcp_tool` and `approve_deployment` hunks above are this change's
contribution.