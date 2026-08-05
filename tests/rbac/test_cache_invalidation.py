"""Tests for RBAC Cache Invalidation Submodule (SSOT 27).

Verifies CacheInvalidationService and PermissionCache work correctly.
"""

import pytest
from common_lib.modules.rbac.permission_cache import PermissionCache
from common_lib.modules.rbac.cache.invalidation import CacheInvalidationService


class TestPermissionCache:
    """Test the core PermissionCache."""

    def test_set_and_get(self):
        cache = PermissionCache(default_ttl_seconds=60)
        cache.set(1, "project", "read", True)
        assert cache.get(1, "project", "read") is True

    def test_cache_miss(self):
        cache = PermissionCache(default_ttl_seconds=60)
        assert cache.get(1, "project", "read") is None

    def test_invalidate_user(self):
        cache = PermissionCache(default_ttl_seconds=60)
        cache.set(1, "project", "read", True)
        cache.set(1, "issue", "write", False)
        cache.set(2, "project", "read", True)
        cache.invalidate_user(1)
        assert cache.get(1, "project", "read") is None
        assert cache.get(1, "issue", "write") is None
        # User 2 should be unaffected
        assert cache.get(2, "project", "read") is True

    def test_invalidate_all(self):
        cache = PermissionCache(default_ttl_seconds=60)
        cache.set(1, "project", "read", True)
        cache.set(2, "issue", "write", True)
        cache.invalidate_all()
        assert cache.get(1, "project", "read") is None
        assert cache.get(2, "issue", "write") is None

    def test_stats(self):
        cache = PermissionCache(default_ttl_seconds=60)
        cache.set(1, "project", "read", True)
        cache.get(1, "project", "read")  # hit
        cache.get(1, "project", "write")  # miss
        stats = cache.stats
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["size"] == 1


class TestCacheInvalidationService:
    """Test CacheInvalidationService wrapping PermissionCache."""

    def test_invalidate_user(self):
        cache = PermissionCache(default_ttl_seconds=60)
        cache.set(1, "project", "read", True)
        cache.set(2, "issue", "write", True)
        svc = CacheInvalidationService(cache=cache)
        count = svc.invalidate_user(1)
        assert count == 1
        assert cache.get(1, "project", "read") is None
        assert cache.get(2, "issue", "write") is True

    def test_invalidate_users(self):
        cache = PermissionCache(default_ttl_seconds=60)
        cache.set(1, "a", "b", True)
        cache.set(2, "a", "b", True)
        cache.set(3, "a", "b", True)
        svc = CacheInvalidationService(cache=cache)
        count = svc.invalidate_users([1, 3])
        assert count == 2

    def test_invalidate_role_with_users(self):
        cache = PermissionCache(default_ttl_seconds=60)
        cache.set(1, "a", "b", True)
        cache.set(2, "a", "b", True)
        svc = CacheInvalidationService(cache=cache)
        count = svc.invalidate_role(99, affected_user_ids=[1])
        assert count == 1

    def test_invalidate_role_full_flush(self):
        cache = PermissionCache(default_ttl_seconds=60)
        cache.set(1, "a", "b", True)
        cache.set(2, "a", "b", True)
        svc = CacheInvalidationService(cache=cache)
        count = svc.invalidate_role(99, affected_user_ids=None)
        assert count == 2

    def test_get_stats(self):
        cache = PermissionCache(default_ttl_seconds=60)
        cache.set(1, "a", "b", True)
        svc = CacheInvalidationService(cache=cache)
        svc.invalidate_user(1)
        stats = svc.get_stats()
        assert "cache_stats" in stats
        assert stats["total_invalidations"] == 1
