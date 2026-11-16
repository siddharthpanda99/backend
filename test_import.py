#!/usr/bin/env python3
"""Test script that applies all patches before importing diffusers."""

import sys
import typing
import types

# Patch 1: huggingface_hub.dataclasses.type_validator to support union types
import huggingface_hub.dataclasses as hf_dataclasses

_original_type_validator = hf_dataclasses.type_validator


def _is_union_type(expected_type):
    """Check if a type is a union type (typing.Union or Python 3.10+ union syntax)."""
    if isinstance(expected_type, types.UnionType):
        return True
    if hasattr(expected_type, "__origin__"):
        return (
            expected_type.__origin__ is typing.Union
            or expected_type.__origin__ is types.UnionType
        )
    return False


def _patched_type_validator(name, value, expected_type):
    if isinstance(expected_type, types.UnionType) or (
        hasattr(expected_type, "__origin__")
        and (
            expected_type.__origin__ is typing.Union
            or expected_type.__origin__ is types.UnionType
        )
    ):
        for arg in expected_type.__args__:
            try:
                hf_dataclasses.type_validator(name, value, arg)
                return
            except TypeError:
                continue
        raise TypeError(f"Unsupported type for field '{name}': {expected_type}")
    return _original_type_validator(name, value, expected_type)


hf_dataclasses.type_validator = _patched_type_validator
print("Patch 1 applied: huggingface_hub type_validator", file=sys.stderr)

# Patch 2: Disable transformers.integrations.hub_kernels LayerRepository
# This must be done before transformers is imported
import sys
from unittest.mock import MagicMock
import importlib.util

# Create a mock kernels module to prevent the real one from loading
mock_kernels = MagicMock()
mock_kernels.__spec__ = importlib.util.spec_from_loader("kernels", loader=None)
mock_kernels.layer = MagicMock()
mock_kernels.layer.LayerRepository = lambda *args, **kwargs: None
mock_kernels.validate = MagicMock()
mock_kernels.python_deps = MagicMock()
sys.modules["kernels"] = mock_kernels
sys.modules["kernels.layer"] = mock_kernels.layer
sys.modules["kernels.validate"] = mock_kernels.validate
sys.modules["kernels.python_deps"] = mock_kernels.python_deps
print("Patch 2 applied: kernels module mocked", file=sys.stderr)

# Now import diffusers
from diffusers import StableDiffusionPipeline

print("SUCCESS: StableDiffusionPipeline imported successfully", file=sys.stderr)
