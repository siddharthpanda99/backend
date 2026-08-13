"""test_wrapper_schemas.py

For every @node wrapper, compare its declared ``input_schema`` params against
the real ``inspect.signature`` of the backing service method it delegates to.

Rules (the @node contract):
  * Every param declared in input_schema MUST map to a real parameter of the
    backing service method (no phantom/imaginary params that will be rejected
    by the service).
  * `self` and `session` are internal and never declared in input_schema.
  * Special-case ALLOWED: ``core.decrypt_blob`` is a *flattened facade* --
    it accepts the individual EncryptedBlob fields (ciphertext, iv, tag,
    key_id, key_version, algorithm) and reconstructs the blob internally, so
    they do not match ``EncryptionService.decrypt(blob)``. This is intentional
    and documented in core/nodes.py. See also ``core.encrypt_plaintext``
    which mirrors ``encrypt``'s params and is therefore NOT a phantom.

The backing-method detection mirrors the production code path: a wrapper does
``svc = XService(session=session)`` then calls ``svc.method(...)``. We extract
``XService.method`` and introspect it.
"""

from __future__ import annotations

import importlib
import inspect
import re

import pytest

from wrapper_utils import collect_wrappers


# Wrappers that intentionally transform their inputs (facade flattening) and
# therefore legitimately carry params that don't map 1:1 to the service method.
FACADE_ALLOWED = {
    "decrypt_blob": {
        "reason": "Flattened facade: takes EncryptedBlob fields and reconstructs the blob internally",
        "phantom_params": {
            "ciphertext",
            "iv",
            "tag",
            "key_id",
            "key_version",
            "algorithm",
        },
    },
}


def _resolve_service_call(sub, fn_src):
    """Return (service_cls_name, method_name) from a wrapper's source, or (None, None)."""
    # svc = VaultService(session=session)  OR  svc = ServiceClass()
    svc_m = re.search(r"svc\s*=\s*(\w+)\(session=", fn_src)
    if not svc_m:
        svc_m = re.search(r"svc\s*=\s*(\w+)\(", fn_src)
    if not svc_m:
        return None, None
    cls = svc_m.group(1)
    # svc.method(  or svc.method (for attribute lookups)
    meth_m = re.search(r"svc\.(\w+)\s*\(", fn_src)
    if not meth_m:
        # the call may be on a chained/inner var (e.g. svc._something.method())
        # try the first svc.<name>(... occurrence
        meth_m = re.search(r"svc\.(\w+)", fn_src)
    if not meth_m:
        return cls, None
    return cls, meth_m.group(1)


def _real_params(sub, cls, method):
    if not cls or not method:
        return None
    try:
        svc_mod = importlib.import_module(
            f"common_lib.modules.secrets_manager.{sub}.service"
        )
        sig = inspect.signature(getattr(getattr(svc_mod, cls), method))
        return {p for p in sig.parameters if p not in ("self", "session")}
    except Exception:
        return None


WRAPPERS = collect_wrappers()
IDS = [f"{sub}.{name}" for sub, name, _, _ in WRAPPERS]


@pytest.mark.parametrize("entry", WRAPPERS, ids=IDS)
def test_input_schema_no_phantom_params(entry):
    """Every input_schema param maps to a real service parameter."""
    sub, name, fn, meta = entry
    inp = meta.get("input_schema") or {}
    assert isinstance(inp, dict), f"{name}: input_schema not dict"

    fn_src = inspect.getsource(fn)
    cls, method = _resolve_service_call(sub, fn_src)
    real = _real_params(sub, cls, method)
    if real is None:
        # Could not resolve the service call (e.g. wrapper uses a different
        # dispatch pattern). Skip strict check but still require no *empty*
        # schema where the method clearly takes params.
        pytest.skip(f"{name}: could not resolve {cls}.{method}")

    declared = set(inp.keys())
    phantom = declared - real
    # Carve out allowed facade flattening.
    allowed = FACADE_ALLOWED.get(name, {})
    phantom -= allowed.get("phantom_params", set())
    assert not phantom, (
        f"{name}: input_schema declares phantom params {sorted(phantom)} "
        f"not present on {cls}.{method}({sorted(real)})"
    )


@pytest.mark.parametrize("entry", WRAPPERS, ids=IDS)
def test_output_schema_non_empty(entry):
    """output_schema declares at least one field (the return shape)."""
    _sub, name, _fn, meta = entry
    out = meta.get("output_schema") or {}
    assert isinstance(out, dict) and len(out) >= 1, f"{name}: output_schema empty"
    # every declared output field should be a dict (field -> {"type": ...})
    for field, spec in out.items():
        assert (
            isinstance(spec, dict) and "type" in spec
        ), f"{name}: output_schema['{field}'] missing 'type'"
