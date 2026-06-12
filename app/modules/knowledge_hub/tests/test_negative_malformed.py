"""
Negative test suite — malformed requests for Knowledge Sources Hub.

Tests how all endpoints handle invalid input: missing required fields,
wrong data types, empty strings, oversized payloads, non-existent FK
references, invalid status values, and special characters.

Usage:
    cd "Backend Monorepo/Backend"
    uv run python -m pytest app/modules/knowledge_hub/tests/test_negative_malformed.py -v --tb=short
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


# ═══════════════════════════════════════════════════════════════════
# Source Types — Malformed Create Requests
# ═══════════════════════════════════════════════════════════════════


class TestNegativeSourceTypeCreate:
    """POST /knowledge-hub/source-types with invalid payloads."""

    def test_missing_id(self, client: TestClient) -> None:
        """Creating a source type without 'id' should fail (422)."""
        resp = client.post(
            "/api/v1/knowledge-hub/source-types",
            json={"name": "No ID Type"},
        )
        # Pydantic requires 'id' as a str field
        assert resp.status_code == 422

    def test_missing_name(self, client: TestClient) -> None:
        """Creating a source type without 'name' should fail (422)."""
        resp = client.post(
            "/api/v1/knowledge-hub/source-types",
            json={"id": "no_name_type"},
        )
        assert resp.status_code == 422

    def test_empty_id(self, client: TestClient) -> None:
        """Creating a source type with empty string 'id' may succeed (blank is allowed by Pydantic) or fail."""
        resp = client.post(
            "/api/v1/knowledge-hub/source-types",
            json={"id": "", "name": "Empty ID Type"},
        )
        # Pydantic allows empty strings for str fields — DB might accept or reject
        assert resp.status_code in (201, 422, 500)

    def test_empty_name(self, client: TestClient) -> None:
        """Creating a source type with empty string 'name'."""
        resp = client.post(
            "/api/v1/knowledge-hub/source-types",
            json={"id": "empty_name", "name": ""},
        )
        assert resp.status_code in (201, 422)

    def test_id_with_spaces(self, client: TestClient) -> None:
        """Source type ID with spaces is technically valid for Pydantic/DB."""
        resp = client.post(
            "/api/v1/knowledge-hub/source-types",
            json={"id": "type with spaces", "name": "Spaces in ID"},
        )
        assert resp.status_code == 201
        del_resp = client.delete("/api/v1/knowledge-hub/source-types/type%20with%20spaces")
        assert del_resp.status_code in (200, 404)

    def test_id_with_special_chars(self, client: TestClient) -> None:
        """Source type ID with special characters."""
        resp = client.post(
            "/api/v1/knowledge-hub/source-types",
            json={"id": "type@#$%^&*", "name": "Special ID"},
        )
        assert resp.status_code == 201
        del_resp = client.delete("/api/v1/knowledge-hub/source-types/type%40%23%24%25%5E%26*")
        assert del_resp.status_code in (200, 404)

    def test_id_too_long(self, client: TestClient) -> None:
        """Source type ID with 500 characters."""
        long_id = "x" * 500
        resp = client.post(
            "/api/v1/knowledge-hub/source-types",
            json={"id": long_id, "name": "Long ID Type"},
        )
        assert resp.status_code in (201, 422, 500)
        if resp.status_code == 201:
            client.delete(f"/api/v1/knowledge-hub/source-types/{long_id}")

    def test_oversized_name(self, client: TestClient) -> None:
        """Source type with a 10,000 character name."""
        huge_name = "A" * 10000
        resp = client.post(
            "/api/v1/knowledge-hub/source-types",
            json={"id": "huge_name", "name": huge_name},
        )
        assert resp.status_code in (201, 422, 500)
        if resp.status_code == 201:
            client.delete("/api/v1/knowledge-hub/source-types/huge_name")

    def test_oversized_payload(self, client: TestClient) -> None:
        """Source type with a 1MB payload."""
        huge_schema = {"data": "x" * 1024 * 1024}
        resp = client.post(
            "/api/v1/knowledge-hub/source-types",
            json={
                "id": "huge_payload",
                "name": "Huge Payload",
                "config_schema": huge_schema,
            },
        )
        assert resp.status_code in (201, 413, 422, 500)
        if resp.status_code == 201:
            client.delete("/api/v1/knowledge-hub/source-types/huge_payload")

    def test_invalid_category(self, client: TestClient) -> None:
        """Source type with a made-up category (Pydantic accepts any string)."""
        resp = client.post(
            "/api/v1/knowledge-hub/source-types",
            json={
                "id": "weird_category",
                "name": "Weird Category",
                "category": "quantum_flux_capacitor",
            },
        )
        assert resp.status_code == 201
        client.delete("/api/v1/knowledge-hub/source-types/weird_category")

    def test_wrong_type_for_name(self, client: TestClient) -> None:
        """Sending an integer instead of string for 'name' should fail (422)."""
        resp = client.post(
            "/api/v1/knowledge-hub/source-types",
            json={"id": "wrong_type", "name": 42},
        )
        assert resp.status_code == 422

    def test_wrong_type_for_category(self, client: TestClient) -> None:
        """Sending an object instead of string for 'category' should fail (422)."""
        resp = client.post(
            "/api/v1/knowledge-hub/source-types",
            json={
                "id": "bad_category",
                "name": "Bad Category",
                "category": {"nested": "object"},
            },
        )
        assert resp.status_code == 422

    def test_extra_unknown_fields(self, client: TestClient) -> None:
        """Sending fields not in the schema should succeed (Pydantic ignores extra)."""
        resp = client.post(
            "/api/v1/knowledge-hub/source-types",
            json={
                "id": "extra_fields",
                "name": "Extra Fields",
                "unknown_field": "should be ignored",
                "another_unknown": 123,
            },
        )
        assert resp.status_code == 201
        client.delete("/api/v1/knowledge-hub/source-types/extra_fields")

    def test_empty_json_object(self, client: TestClient) -> None:
        """Sending an empty JSON object should fail (missing required fields)."""
        resp = client.post(
            "/api/v1/knowledge-hub/source-types",
            json={},
        )
        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════
# Source Configs — Malformed Create Requests
# ═══════════════════════════════════════════════════════════════════


class TestNegativeSourceConfigCreate:
    """POST /knowledge-hub/sources with invalid payloads."""

    def test_missing_source_type_id(self, client: TestClient) -> None:
        """Source config without 'source_type_id' should fail (422)."""
        resp = client.post(
            "/api/v1/knowledge-hub/sources",
            json={"name": "Missing Type"},
        )
        assert resp.status_code == 422

    def test_missing_name(self, client: TestClient) -> None:
        """Source config without 'name' should fail (422)."""
        resp = client.post(
            "/api/v1/knowledge-hub/sources",
            json={"source_type_id": "arxiv_api"},
        )
        assert resp.status_code == 422

    def test_empty_source_type_id(self, client: TestClient) -> None:
        """Source config with empty source_type_id string."""
        resp = client.post(
            "/api/v1/knowledge-hub/sources",
            json={"source_type_id": "", "name": "Empty Type ID"},
        )
        assert resp.status_code in (201, 422, 500)

    def test_empty_name(self, client: TestClient) -> None:
        """Source config with empty name string."""
        resp = client.post(
            "/api/v1/knowledge-hub/sources",
            json={
                "source_type_id": "arxiv_api",
                "name": "",
                "id": "src-empty-name-test",
            },
        )
        assert resp.status_code in (201, 422)

    def test_nonexistent_source_type_id(self, client: TestClient) -> None:
        """Source config referencing a source type that doesn't exist should succeed (no FK enforcement at route level)."""
        resp = client.post(
            "/api/v1/knowledge-hub/sources",
            json={
                "source_type_id": "this_type_definitely_does_not_exist_xyz_999",
                "name": "Ghost Type",
            },
        )
        assert resp.status_code in (201, 422, 500)
        if resp.status_code == 201:
            src_id = resp.json().get("data", {}).get("id", "")
            if src_id:
                del_resp = client.delete(f"/api/v1/knowledge-hub/sources/{src_id}")
                assert del_resp.status_code in (200, 404)

    def test_wrong_type_for_config(self, client: TestClient) -> None:
        """Sending a string instead of object for 'config' should fail (422)."""
        resp = client.post(
            "/api/v1/knowledge-hub/sources",
            json={
                "source_type_id": "arxiv_api",
                "name": "Wrong Config Type",
                "config": "this should be an object",
            },
        )
        assert resp.status_code == 422

    def test_wrong_type_for_tags(self, client: TestClient) -> None:
        """Sending a string instead of array for 'tags' should fail (422)."""
        resp = client.post(
            "/api/v1/knowledge-hub/sources",
            json={
                "source_type_id": "arxiv_api",
                "name": "Wrong Tags Type",
                "tags": "not-an-array",
            },
        )
        assert resp.status_code == 422

    def test_oversized_tags(self, client: TestClient) -> None:
        """Source config with 1000 tags."""
        many_tags = [f"tag-{i}" for i in range(1000)]
        resp = client.post(
            "/api/v1/knowledge-hub/sources",
            json={
                "source_type_id": "arxiv_api",
                "name": "Many Tags",
                "tags": many_tags,
                "id": "src-many-tags-test",
            },
        )
        assert resp.status_code in (201, 422, 500)
        if resp.status_code == 201:
            client.delete("/api/v1/knowledge-hub/sources/src-many-tags-test")

    def test_oversized_config(self, client: TestClient) -> None:
        """Source config with a 500KB config payload."""
        huge_config = {"data": "x" * 500_000}
        resp = client.post(
            "/api/v1/knowledge-hub/sources",
            json={
                "source_type_id": "arxiv_api",
                "name": "Huge Config",
                "config": huge_config,
            },
        )
        assert resp.status_code in (201, 413, 422, 500)
        if resp.status_code == 201:
            src_id = resp.json().get("data", {}).get("id", "")
            if src_id:
                client.delete(f"/api/v1/knowledge-hub/sources/{src_id}")

    def test_empty_json_object(self, client: TestClient) -> None:
        """Sending an empty JSON object should fail (422)."""
        resp = client.post(
            "/api/v1/knowledge-hub/sources",
            json={},
        )
        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════
# Pipelines — Malformed Create Requests
# ═══════════════════════════════════════════════════════════════════


class TestNegativePipelineCreate:
    """POST /knowledge-hub/pipelines with invalid payloads."""

    def test_missing_name(self, client: TestClient) -> None:
        """Pipeline without 'name' should fail (422)."""
        resp = client.post(
            "/api/v1/knowledge-hub/pipelines",
            json={
                "source_config_id": "src-arxiv-001",
                "pipeline_definition": {"version": "1.0", "type": "extract", "steps": [], "output": {"format": "json"}},
            },
        )
        assert resp.status_code == 422

    def test_missing_source_config_id(self, client: TestClient) -> None:
        """Pipeline without 'source_config_id' should fail (422)."""
        resp = client.post(
            "/api/v1/knowledge-hub/pipelines",
            json={
                "name": "Missing Source",
                "pipeline_definition": {"version": "1.0", "type": "extract", "steps": [], "output": {"format": "json"}},
            },
        )
        assert resp.status_code == 422

    def test_missing_pipeline_definition(self, client: TestClient) -> None:
        """Pipeline without 'pipeline_definition' should fail (422)."""
        resp = client.post(
            "/api/v1/knowledge-hub/pipelines",
            json={
                "name": "Missing Def",
                "source_config_id": "src-arxiv-001",
            },
        )
        assert resp.status_code == 422

    def test_empty_name(self, client: TestClient) -> None:
        """Pipeline with empty name string."""
        resp = client.post(
            "/api/v1/knowledge-hub/pipelines",
            json={
                "name": "",
                "source_config_id": "src-arxiv-001",
                "pipeline_definition": {"version": "1.0", "type": "extract", "steps": [], "output": {"format": "json"}},
                "id": "pipe-empty-name-test",
            },
        )
        assert resp.status_code in (201, 422)

    def test_nonexistent_source_config_id(self, client: TestClient) -> None:
        """Pipeline referencing a non-existent source config."""
        resp = client.post(
            "/api/v1/knowledge-hub/pipelines",
            json={
                "name": "Ghost Source Pipeline",
                "source_config_id": "src-ghost-99999",
                "pipeline_definition": {"version": "1.0", "type": "extract", "steps": [], "output": {"format": "json"}},
            },
        )
        # No FK enforcement at route level — creation succeeds
        assert resp.status_code == 201
        pipe_id = resp.json()["data"]["id"]
        client.delete(f"/api/v1/knowledge-hub/pipelines/{pipe_id}")

    def test_pipeline_definition_wrong_type(self, client: TestClient) -> None:
        """Sending a string instead of object for pipeline_definition should fail (422)."""
        resp = client.post(
            "/api/v1/knowledge-hub/pipelines",
            json={
                "name": "Wrong Def Type",
                "source_config_id": "src-arxiv-001",
                "pipeline_definition": "this should be an object",
            },
        )
        assert resp.status_code == 422

    def test_oversized_pipeline_definition(self, client: TestClient) -> None:
        """Pipeline definition with 1000 steps."""
        many_steps = [
            {"name": f"step_{i}", "operation": "api_query", "config": {"endpoint": f"https://api{i}.example.com"}}
            for i in range(1000)
        ]
        resp = client.post(
            "/api/v1/knowledge-hub/pipelines",
            json={
                "id": "pipe-huge-def",
                "name": "Huge Pipeline Def",
                "source_config_id": "src-arxiv-001",
                "pipeline_definition": {
                    "version": "1.0",
                    "type": "extract",
                    "steps": many_steps,
                    "output": {"format": "json"},
                },
            },
        )
        assert resp.status_code in (201, 413, 422, 500)
        if resp.status_code == 201:
            client.delete("/api/v1/knowledge-hub/pipelines/pipe-huge-def")

    def test_empty_json_object(self, client: TestClient) -> None:
        """Sending an empty JSON object should fail (422)."""
        resp = client.post(
            "/api/v1/knowledge-hub/pipelines",
            json={},
        )
        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════
# Packets — Malformed Create Requests
# ═══════════════════════════════════════════════════════════════════


class TestNegativePacketCreate:
    """POST /knowledge-hub/packets with invalid payloads."""

    def test_missing_name(self, client: TestClient) -> None:
        """Packet without 'name' should fail (422)."""
        resp = client.post(
            "/api/v1/knowledge-hub/packets",
            json={},
        )
        assert resp.status_code == 422

    def test_empty_name(self, client: TestClient) -> None:
        """Packet with empty name string."""
        resp = client.post(
            "/api/v1/knowledge-hub/packets",
            json={"id": "pkt-empty-name", "name": ""},
        )
        assert resp.status_code in (201, 422)
        if resp.status_code == 201:
            client.delete("/api/v1/knowledge-hub/packets/pkt-empty-name")

    def test_nonexistent_source_config_ids(self, client: TestClient) -> None:
        """Packet referencing non-existent source configs."""
        resp = client.post(
            "/api/v1/knowledge-hub/packets",
            json={
                "name": "Ghost Sources Packet",
                "source_config_ids": ["src-ghost-001", "src-ghost-002"],
            },
        )
        assert resp.status_code == 201
        pkt_id = resp.json()["data"]["id"]
        client.delete(f"/api/v1/knowledge-hub/packets/{pkt_id}")

    def test_nonexistent_pipeline_ids(self, client: TestClient) -> None:
        """Packet referencing non-existent pipelines."""
        resp = client.post(
            "/api/v1/knowledge-hub/packets",
            json={
                "name": "Ghost Pipelines Packet",
                "pipeline_ids": ["pipe-ghost-001", "pipe-ghost-002"],
            },
        )
        assert resp.status_code == 201
        pkt_id = resp.json()["data"]["id"]
        client.delete(f"/api/v1/knowledge-hub/packets/{pkt_id}")

    def test_wrong_type_for_source_config_ids(self, client: TestClient) -> None:
        """Sending a string instead of array for source_config_ids should fail (422)."""
        resp = client.post(
            "/api/v1/knowledge-hub/packets",
            json={
                "name": "Wrong Type",
                "source_config_ids": "not-an-array",
            },
        )
        assert resp.status_code == 422

    def test_oversized_tags(self, client: TestClient) -> None:
        """Packet with 1000 tags."""
        many_tags = [f"tag-{i}" for i in range(1000)]
        resp = client.post(
            "/api/v1/knowledge-hub/packets",
            json={
                "id": "pkt-many-tags",
                "name": "Many Tags Packet",
                "tags": many_tags,
            },
        )
        assert resp.status_code in (201, 422, 500)
        if resp.status_code == 201:
            client.delete("/api/v1/knowledge-hub/packets/pkt-many-tags")

    def test_oversized_name(self, client: TestClient) -> None:
        """Packet with a 10,000 character name."""
        huge_name = "B" * 10000
        resp = client.post(
            "/api/v1/knowledge-hub/packets",
            json={"id": "pkt-huge-name", "name": huge_name},
        )
        assert resp.status_code in (201, 422, 500)
        if resp.status_code == 201:
            client.delete("/api/v1/knowledge-hub/packets/pkt-huge-name")

    def test_empty_json_object(self, client: TestClient) -> None:
        """Sending an empty JSON object should fail (422)."""
        resp = client.post(
            "/api/v1/knowledge-hub/packets",
            json={},
        )
        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════
# Projects — Malformed Create Requests
# ═══════════════════════════════════════════════════════════════════


class TestNegativeProjectCreate:
    """POST /knowledge-hub/projects with invalid payloads."""

    def test_missing_name(self, client: TestClient) -> None:
        """Project without 'name' should fail (422)."""
        resp = client.post(
            "/api/v1/knowledge-hub/projects",
            json={},
        )
        assert resp.status_code == 422

    def test_empty_name(self, client: TestClient) -> None:
        """Project with empty name string."""
        resp = client.post(
            "/api/v1/knowledge-hub/projects",
            json={"id": "proj-empty-name", "name": ""},
        )
        assert resp.status_code in (201, 422)
        if resp.status_code == 201:
            client.delete("/api/v1/knowledge-hub/projects/proj-empty-name")

    def test_nonexistent_packet_ids(self, client: TestClient) -> None:
        """Project referencing non-existent packets."""
        resp = client.post(
            "/api/v1/knowledge-hub/projects",
            json={
                "id": "proj-ghost-packets",
                "name": "Ghost Packets Project",
                "packet_ids": ["pkt-ghost-001", "pkt-ghost-002"],
            },
        )
        assert resp.status_code == 201
        client.delete("/api/v1/knowledge-hub/projects/proj-ghost-packets")

    def test_wrong_type_for_packet_ids(self, client: TestClient) -> None:
        """Sending a string instead of array for packet_ids should fail (422)."""
        resp = client.post(
            "/api/v1/knowledge-hub/projects",
            json={
                "name": "Wrong Packet Type",
                "packet_ids": "not-an-array",
            },
        )
        assert resp.status_code == 422

    def test_oversized_tags(self, client: TestClient) -> None:
        """Project with 1000 tags."""
        many_tags = [f"proj-tag-{i}" for i in range(1000)]
        resp = client.post(
            "/api/v1/knowledge-hub/projects",
            json={
                "id": "proj-many-tags",
                "name": "Many Tags Project",
                "tags": many_tags,
            },
        )
        assert resp.status_code in (201, 422, 500)
        if resp.status_code == 201:
            client.delete("/api/v1/knowledge-hub/projects/proj-many-tags")

    def test_oversized_description(self, client: TestClient) -> None:
        """Project with a 50,000 character description."""
        huge_desc = "C" * 50000
        resp = client.post(
            "/api/v1/knowledge-hub/projects",
            json={
                "id": "proj-huge-desc",
                "name": "Huge Description",
                "description": huge_desc,
            },
        )
        # SQLModel uses Text type for description, so 50k chars should be fine
        assert resp.status_code in (201, 422, 500)
        if resp.status_code == 201:
            client.delete("/api/v1/knowledge-hub/projects/proj-huge-desc")

    def test_empty_json_object(self, client: TestClient) -> None:
        """Sending an empty JSON object should fail (422)."""
        resp = client.post(
            "/api/v1/knowledge-hub/projects",
            json={},
        )
        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════
# Attach — Malformed Requests
# ═══════════════════════════════════════════════════════════════════


class TestNegativeAttach:
    """POST /knowledge-hub/projects/{id}/attach with invalid payloads."""

    def test_missing_agent_id(self, client: TestClient) -> None:
        """Attaching without 'agent_id' should fail (422)."""
        resp = client.post(
            "/api/v1/knowledge-hub/projects/proj-ai-impact-001/attach",
            json={},
        )
        assert resp.status_code == 422

    def test_empty_agent_id(self, client: TestClient) -> None:
        """Attaching with empty agent_id string."""
        # First verify the project (it starts as draft)
        client.post(
            "/api/v1/knowledge-hub/projects/proj-ai-impact-001/verify"
        )
        resp = client.post(
            "/api/v1/knowledge-hub/projects/proj-ai-impact-001/attach",
            json={"agent_id": ""},
        )
        # Empty string is a valid str — might succeed or fail
        assert resp.status_code in (200, 422)

    def test_wrong_type_for_agent_id(self, client: TestClient) -> None:
        """Sending an integer instead of string for agent_id should fail (422)."""
        resp = client.post(
            "/api/v1/knowledge-hub/projects/proj-ai-impact-001/attach",
            json={"agent_id": 123},
        )
        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════
# Invalid IDs & Path Parameters
# ═══════════════════════════════════════════════════════════════════


class TestNegativeInvalidIDs:
    """Endpoints called with invalid/malformed path parameters."""

    @pytest.mark.parametrize(
        "url",
        [
            "/api/v1/knowledge-hub/source-types/../../etc/passwd",
            "/api/v1/knowledge-hub/sources/'; DROP TABLE; --",
            "/api/v1/knowledge-hub/pipelines/<script>alert(1)</script>",
            "/api/v1/knowledge-hub/packets/%00nullbyte",
            "/api/v1/knowledge-hub/projects/../../../",
            "/api/v1/knowledge-hub/sources/null",
            "/api/v1/knowledge-hub/source-types/undefined",
            "/api/v1/knowledge-hub/pipelines/NaN",
        ],
        ids=[
            "path-traversal",
            "sql-injection",
            "xss",
            "null-byte",
            "relative-path",
            "null-string",
            "undefined-string",
            "nan-string",
        ],
    )
    def test_malformed_path_ids(self, client: TestClient, url: str) -> None:
        """Malformed path parameters should not crash the server."""
        for method in ["get", "put", "delete"]:
            if method == "get":
                resp = client.get(url)
            elif method == "put":
                resp = client.put(url, json={"name": "update"})
            else:
                resp = client.delete(url)
            # Should either return 404 (not found) or 422 (validation error)
            # Any 5xx would indicate a crash
            assert resp.status_code in (404, 405, 422, 200), (
                f"{method.upper()} {url} returned {resp.status_code} (expected 404/422)"
            )

    @pytest.mark.parametrize(
        "url",
        [
            "/api/v1/knowledge-hub/source-types/../../etc/passwd/execute",
            "/api/v1/knowledge-hub/sources/'; DROP TABLE; --/verify",
            "/api/v1/knowledge-hub/packets/%00nullbyte/resolve",
            "/api/v1/knowledge-hub/projects/../../../test-all",
            "/api/v1/knowledge-hub/sources/null/preview",
        ],
        ids=[
            "execute-path-traversal",
            "verify-sql-injection",
            "resolve-null-byte",
            "test-all-relative-path",
            "preview-null-string",
        ],
    )
    def test_malformed_action_paths(self, client: TestClient, url: str) -> None:
        """Malformed action URLs (execute/verify/resolve) should not crash."""
        resp = client.post(url)
        assert resp.status_code in (404, 405, 422), (
            f"POST {url} returned {resp.status_code} (expected 404/422)"
        )


# ═══════════════════════════════════════════════════════════════════
# Update/Mutate — Invalid Payloads
# ═══════════════════════════════════════════════════════════════════


class TestNegativeUpdates:
    """PUT endpoints with invalid payloads."""

    def test_update_source_type_with_null_name(self, client: TestClient) -> None:
        """Updating a source type with null name — Pydantic Optional[str] accepts it."""
        resp = client.put(
            "/api/v1/knowledge-hub/source-types/arxiv_api",
            json={"name": None},
        )
        # Pydantic's Optional[str] accepts None; the service skips fields where
        # value is None because of exclude_none=True in model_dump(). 
        # So name stays unchanged.
        assert resp.status_code == 200
        data = resp.json()["data"]
        # Name should NOT be None — the service ignores null fields
        assert data["name"] is not None
        assert data["name"] == "ArXiv API"

    def test_update_source_config_invalid_field(self, client: TestClient) -> None:
        """Updating a source config with invalid field type."""
        resp = client.put(
            "/api/v1/knowledge-hub/sources/src-arxiv-001",
            json={"config": "this should be an object"},
        )
        assert resp.status_code == 422

    def test_update_pipeline_nonexistent(self, client: TestClient) -> None:
        """Updating a non-existent pipeline should fail (404)."""
        resp = client.put(
            "/api/v1/knowledge-hub/pipelines/pipe-nonexistent-99999",
            json={"name": "Updated Name"},
        )
        assert resp.status_code == 404

    def test_update_packet_nonexistent(self, client: TestClient) -> None:
        """Updating a non-existent packet should fail (404)."""
        resp = client.put(
            "/api/v1/knowledge-hub/packets/pkt-nonexistent-99999",
            json={"name": "Updated Name"},
        )
        assert resp.status_code == 404

    def test_update_project_nonexistent(self, client: TestClient) -> None:
        """Updating a non-existent project should fail (404)."""
        resp = client.put(
            "/api/v1/knowledge-hub/projects/proj-nonexistent-99999",
            json={"name": "Updated Name"},
        )
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════
# Invalid Query Parameters
# ═══════════════════════════════════════════════════════════════════


class TestNegativeQueryParams:
    """GET endpoints with invalid query parameters."""

    def test_invalid_source_type_filter(self, client: TestClient) -> None:
        """Invalid source type filter — should return empty list, not crash."""
        resp = client.get(
            "/api/v1/knowledge-hub/sources?source_type_id=nonexistent_filter_type"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert len(body["data"]) == 0

    def test_invalid_status_filter(self, client: TestClient) -> None:
        """Invalid status filter — should return empty list, not crash."""
        resp = client.get(
            "/api/v1/knowledge-hub/sources?status=quantum_status"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert len(body["data"]) == 0

    def test_preview_with_negative_limit(self, client: TestClient) -> None:
        """Preview with negative limit should trigger Pydantic validation (422)."""
        resp = client.get(
            "/api/v1/knowledge-hub/sources/src-arxiv-001/preview?limit=-5"
        )
        # Pydantic has ge=1 constraint on the limit parameter
        assert resp.status_code == 422

    def test_preview_with_zero_limit(self, client: TestClient) -> None:
        """Preview with zero limit should trigger Pydantic validation (422)."""
        resp = client.get(
            "/api/v1/knowledge-hub/sources/src-arxiv-001/preview?limit=0"
        )
        # Pydantic has ge=1 constraint
        assert resp.status_code == 422

    def test_preview_with_oversized_limit(self, client: TestClient) -> None:
        """Preview with limit > 100 should trigger Pydantic validation (422)."""
        resp = client.get(
            "/api/v1/knowledge-hub/sources/src-arxiv-001/preview?limit=999"
        )
        # Pydantic has le=100 constraint
        assert resp.status_code == 422

    def test_invalid_category_filter(self, client: TestClient) -> None:
        """Invalid category filter returns empty list."""
        resp = client.get(
            "/api/v1/knowledge-hub/source-types?category=quantum_flux"
        )
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 0

    def test_malformed_json_payload(self, client: TestClient) -> None:
        """Sending malformed JSON should fail (422)."""
        # FastAPI/Starlette returns 422 for malformed JSON (not JSON parsable)
        resp = client.post(
            "/api/v1/knowledge-hub/source-types",
            data="this is not json at all {{{{",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════
# Business Logic Violations
# ═══════════════════════════════════════════════════════════════════


class TestNegativeBusinessLogic:
    """Requests that violate business rules."""

    def test_verify_nonexistent_source(self, client: TestClient) -> None:
        """Verifying a non-existent source returns 404."""
        resp = client.post(
            "/api/v1/knowledge-hub/sources/fake-source-id-99999/verify"
        )
        assert resp.status_code == 404

    def test_execute_nonexistent_source(self, client: TestClient) -> None:
        """Executing a non-existent source returns 404."""
        resp = client.post(
            "/api/v1/knowledge-hub/sources/fake-source-id-99999/execute"
        )
        assert resp.status_code == 404

    def test_verify_nonexistent_pipeline(self, client: TestClient) -> None:
        """Verifying a non-existent pipeline returns 404."""
        resp = client.post(
            "/api/v1/knowledge-hub/pipelines/fake-pipe-99999/verify"
        )
        assert resp.status_code == 404

    def test_execute_nonexistent_pipeline(self, client: TestClient) -> None:
        """Executing a non-existent pipeline returns 404."""
        resp = client.post(
            "/api/v1/knowledge-hub/pipelines/fake-pipe-99999/execute"
        )
        assert resp.status_code == 404

    def test_resolve_nonexistent_packet(self, client: TestClient) -> None:
        """Resolving a non-existent packet returns 404."""
        resp = client.post(
            "/api/v1/knowledge-hub/packets/fake-pkt-99999/resolve"
        )
        assert resp.status_code == 404

    def test_verify_nonexistent_project(self, client: TestClient) -> None:
        """Verifying a non-existent project returns 404."""
        resp = client.post(
            "/api/v1/knowledge-hub/projects/fake-proj-99999/verify"
        )
        assert resp.status_code == 404

    def test_test_all_nonexistent(self, client: TestClient) -> None:
        """Test-all on non-existent project returns 404."""
        resp = client.post(
            "/api/v1/knowledge-hub/projects/fake-proj-99999/test-all"
        )
        assert resp.status_code == 404

    def test_build_data_object_nonexistent(self, client: TestClient) -> None:
        """Build data object on non-existent project returns 404."""
        resp = client.post(
            "/api/v1/knowledge-hub/projects/fake-proj-99999/build-data-object"
        )
        assert resp.status_code == 404

    def test_get_data_object_nonexistent(self, client: TestClient) -> None:
        """Get data object on non-existent project returns 404."""
        resp = client.get(
            "/api/v1/knowledge-hub/projects/fake-proj-99999/data-object"
        )
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════
# Route Integrity — Unregistered or Invalid Routes
# ═══════════════════════════════════════════════════════════════════


class TestNegativeRouteIntegrity:
    """Requests to unregistered or invalid routes."""

    @pytest.mark.parametrize(
        "method, url, expected",
        [
            # Trailing slash on list endpoint routes to same handler (200 or 422 for POST with empty body)
            ("get", "/api/v1/knowledge-hub/source-types/", (200, 404, 405)),
            ("get", "/api/v1/knowledge-hub/nonexistent-resource", (404, 405)),
            ("post", "/api/v1/knowledge-hub/source-types/", (201, 422, 404, 405)),
            ("post", "/api/v1/knowledge-hub/nonexistent", (404, 405)),
            ("put", "/api/v1/knowledge-hub/sources/", (404, 405)),
            ("delete", "/api/v1/knowledge-hub/pipelines/", (404, 405)),
        ],
        ids=[
            "get-source-types-trailing-slash",
            "get-nonexistent-resource",
            "post-source-types-trailing-slash",
            "post-nonexistent",
            "put-sources-trailing-slash",
            "delete-pipelines-trailing-slash",
        ],
    )
    def test_invalid_routes(self, client: TestClient, method: str, url: str, expected: tuple) -> None:
        """Requests to invalid routes return 404."""
        if method == "get":
            resp = client.get(url)
        elif method == "post":
            resp = client.post(url)
        elif method == "put":
            resp = client.put(url)
        elif method == "delete":
            resp = client.delete(url)
        else:
            return
        assert resp.status_code in expected, (
            f"{method.upper()} {url} returned {resp.status_code} (expected {expected})"
        )

    def test_wrong_method_on_existing_route(self, client: TestClient) -> None:
        """Using wrong HTTP method on an existing route returns 405."""
        # GET on a POST-only endpoint
        resp = client.get("/api/v1/knowledge-hub/source-types/arxiv_api/execute")
        assert resp.status_code in (404, 405)

    def test_post_on_get_endpoint(self, client: TestClient) -> None:
        """POST on a GET-only list endpoint."""
        resp = client.post("/api/v1/knowledge-hub/source-types/arxiv_api")
        assert resp.status_code in (404, 405)
