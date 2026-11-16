#!/usr/bin/env python3
"""Patch huggingface_hub to support union types (str | None) in dataclass validation.

This must be imported BEFORE any other imports that might trigger the kernels/transformers/diffusers import chain.
"""

import sys
import typing
import types

# Patch huggingface_hub.dataclasses.type_validator to support union types
import huggingface_hub.dataclasses as hf_dataclasses

_original_type_validator = hf_dataclasses.type_validator


def _is_union_type(expected_type):
    """Check if a type is a union type (typing.Union or Python 3.10+ union syntax)."""
    # Python 3.10+ union syntax (str | None) creates types.UnionType with __args__
    if isinstance(expected_type, types.UnionType):
        return True
    # typing.Union has __origin__ = typing.Union
    if hasattr(expected_type, "__origin__"):
        return (
            expected_type.__origin__ is typing.Union
            or expected_type.__origin__ is types.UnionType
        )
    return False


def _patched_type_validator(name, value, expected_type):
    """Support union types (str | None, etc.) in type validation."""
    if _is_union_type(expected_type):
        # It's a union type, check if value matches any of the union args
        for arg in expected_type.__args__:
            try:
                hf_dataclasses.type_validator(name, value, arg)
                return
            except TypeError:
                continue
        raise TypeError(f"Unsupported type for field '{name}': {expected_type}")
    return _original_type_validator(name, value, expected_type)


hf_dataclasses.type_validator = _patched_type_validator

print("huggingface_hub patched successfully", file=sys.stderr)
