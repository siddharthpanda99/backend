"""Tests for bulk operations - move, copy, tag."""

import pytest
import requests
import uuid


api_base = "http://localhost:8000/api/v1/file-browser"


def cleanup_file(file_id):
    """Cleanup a file."""
    try:
        requests.post(f"{api_base}/files/{file_id}/trash", timeout=2)
        requests.delete(f"{api_base}/files/{file_id}?permanent=true", timeout=2)
    except:
        pass


def cleanup_folder(folder_id):
    """Cleanup a folder."""
    try:
        requests.delete(f"{api_base}/folders/{folder_id}", timeout=2)
    except:
        pass


class TestBulkMove:
    """Tests for bulk move operation."""

    def test_bulk_move_single_file(self, api_base, temp_file, test_id):
        """Verify moving a single file to a folder."""
        folder_resp = requests.post(
            f"{api_base}/folders", json={"name": f"target_{test_id}"}
        )
        folder_id = folder_resp.json()["id"]

        try:
            resp = requests.post(
                f"{api_base}/files/bulk-move",
                json={"ids": [temp_file], "target_folder_id": folder_id},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] == True
        finally:
            cleanup_folder(folder_id)

    def test_bulk_move_multiple_files(self, api_base, test_id):
        """Verify moving multiple files to a folder."""
        folder_resp = requests.post(
            f"{api_base}/folders", json={"name": f"bulk_target_{test_id}"}
        )
        folder_id = folder_resp.json()["id"]
        file_ids = []

        try:
            for i in range(3):
                f = requests.post(
                    f"{api_base}/files",
                    files={"file": (f"file{i}.txt", b"content", "text/plain")},
                )
                file_ids.append(f.json()["id"])

            resp = requests.post(
                f"{api_base}/files/bulk-move",
                json={"ids": file_ids, "target_folder_id": folder_id},
            )
            assert resp.status_code == 200
        finally:
            for fid in file_ids:
                cleanup_file(fid)
            cleanup_folder(folder_id)

    def test_bulk_move_nonexistent_file(self, api_base):
        """Verify moving nonexistent file returns partial success."""
        resp = requests.post(
            f"{api_base}/files/bulk-move",
            json={"ids": ["nonexistent-id"], "target_folder_id": "root"},
        )
        assert resp.status_code == 200

    def test_bulk_move_to_root(self, api_base, temp_file):
        """Verify moving file to root folder."""
        resp = requests.post(
            f"{api_base}/files/bulk-move",
            json={"ids": [temp_file], "target_folder_id": "root"},
        )
        assert resp.status_code == 200


class TestBulkCopy:
    """Tests for bulk copy operation."""

    def test_bulk_copy_single_file(self, api_base, temp_file, test_id):
        """Verify copying a single file."""
        folder_resp = requests.post(
            f"{api_base}/folders", json={"name": f"copy_target_{test_id}"}
        )
        folder_id = folder_resp.json()["id"]

        try:
            resp = requests.post(
                f"{api_base}/files/bulk-copy",
                json={"ids": [temp_file], "target_folder_id": folder_id},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] == True
        finally:
            cleanup_folder(folder_id)


class TestBulkTag:
    """Tests for bulk tag operation."""

    def test_bulk_tag_single_file(self, api_base, temp_file):
        """Verify tagging a single file."""
        resp = requests.post(
            f"{api_base}/files/bulk-tag",
            json={"ids": [temp_file], "tags": ["important", "review"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] == True

    def test_bulk_tag_multiple_files(self, api_base):
        """Verify tagging multiple files."""
        file_ids = []
        try:
            for i in range(3):
                f = requests.post(
                    f"{api_base}/files",
                    files={"file": (f"tagtest{i}.txt", b"content", "text/plain")},
                )
                file_ids.append(f.json()["id"])

            resp = requests.post(
                f"{api_base}/files/bulk-tag",
                json={"ids": file_ids, "tags": ["bulk-tagged"]},
            )
            assert resp.status_code == 200
        finally:
            for fid in file_ids:
                cleanup_file(fid)

    def test_bulk_remove_tags(self, api_base, temp_file):
        """Verify removing tags from files."""
        requests.post(
            f"{api_base}/files/bulk-tag",
            json={"ids": [temp_file], "tags": ["temp-tag"]},
        )


class TestBulkDelete:
    """Tests for bulk delete operation."""

    def test_bulk_delete_files(self, api_base):
        """Verify bulk delete."""
        file_ids = []
        try:
            for i in range(3):
                f = requests.post(
                    f"{api_base}/files",
                    files={"file": (f"deleteme{i}.txt", b"content", "text/plain")},
                )
                file_ids.append(f.json()["id"])

            resp = requests.post(
                f"{api_base}/files/bulk-delete", json={"ids": file_ids}
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] == True
        except Exception as e:
            for fid in file_ids:
                cleanup_file(fid)
            raise
