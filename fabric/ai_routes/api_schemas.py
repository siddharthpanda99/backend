"""Fabric-side mirror of the backend ``APIResponse`` response wrapper.

The Backend defines this shape in ``app/modules/common/types/index.py``.
The fabric (common_lib) cannot import the Backend app package, so the
same shape is mirrored here; the fields and defaults are identical so
clients of the fabric paths observe the same response envelopes.
"""

from typing import Any, Dict, Generic, Optional, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    """
    Standard API Response wrapper.
    """

    status: str = "success"
    message: Optional[str] = None
    data: Optional[T] = None
    meta: Optional[Dict[str, Any]] = None
    model_config = ConfigDict(from_attributes=True)
