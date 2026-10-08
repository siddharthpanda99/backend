"""S8-T6 probe: measure real 404 headers on the deprecated voice-control prefix.

Run with the app's own interpreter. Prints a deterministic, greppable block so
the before/after pair can be diffed verbatim.

Usage:  .venv/bin/python s8t6_measure_404.py > /tmp/opencode/s8t6_before.log 2>&1
"""

from __future__ import annotations

import warnings

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

PROBES = [
    ("deprecated-prefix-root", "/api/v1/voice-control"),
    ("deprecated-prefix-missing-resource", "/api/v1/voice-control/does-not-exist"),
    ("deprecated-prefix-health", "/api/v1/voice-control/health"),
    ("canonical-control-health", "/api/v1/platform-controls/health"),
    ("unrelated-404-control", "/api/v1/s8t6-control-path-that-does-not-exist"),
]

WATCHED = ("deprecation", "sunset", "link")


def main() -> None:
    print("@@BEGIN@@")
    print("mw_stack=" + ",".join(m.cls.__name__ for m in app.user_middleware))
    paths = sorted({r.path for r in app.routes})
    vc = [p for p in paths if p.startswith("/api/v1/voice-control")]
    print(f"served_voice_control_paths={vc!r} (total_app_routes={len(paths)})")

    with TestClient(app, raise_server_exceptions=False) as client:
        for label, path in PROBES:
            resp = client.get(path)
            present = {k: v for k, v in resp.headers.items() if k.lower() in WATCHED}
            print(
                f"PROBE {label} GET {path} -> {resp.status_code} "
                f"deprecation_headers={present!r}"
            )
    print("@@END@@")


if __name__ == "__main__":
    main()
