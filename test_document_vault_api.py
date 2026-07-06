#!/usr/bin/env python3
"""Test Document Vault API endpoints end-to-end."""
import sys
import os
import threading
import time
import urllib.request
import json

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'Python Libs', 'common_lib', 'src'))

from app.main import app
import uvicorn

PORT = 18771
BASE = f"http://127.0.0.1:{PORT}/api/v1/document-vault"

passed = 0
failed = 0


def test(method, path, data=None, expect=200, desc=""):
    global passed, failed
    url = f"{BASE}{path}"
    req = urllib.request.Request(url, method=method)
    req.add_header("Content-Type", "application/json")
    if data:
        req.data = json.dumps(data).encode()
    try:
        resp = urllib.request.urlopen(req)
        status = resp.getcode()
        body = json.loads(resp.read())
        if status == expect:
            passed += 1
            print(f"  PASS  {method:6s} {path} -> {status}  {desc}")
        else:
            failed += 1
            print(f"  FAIL  {method:6s} {path} -> {status} (expected {expect})  {desc}")
        return body
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode()[:200]
        except Exception:
            pass
        if e.code == expect:
            passed += 1
            print(f"  PASS  {method:6s} {path} -> {e.code}  {desc}")
        else:
            failed += 1
            print(f"  FAIL  {method:6s} {path} -> {e.code} (expected {expect})  {desc}  {body}")
        return None
    except Exception as e:
        failed += 1
        print(f"  FAIL  {method:6s} {path} -> {type(e).__name__}: {e}  {desc}")
        return None


def run_tests():
    print("\n=== Document Vault API End-to-End Tests ===\n")

    print("--- List & Stats ---")
    test("GET", "", desc="list documents")
    test("GET", "/stats", desc="vault stats")

    print("\n--- Create & Read ---")
    test("POST", "", {"document_id": "e2e-test-001", "filename": "report.pdf", "status": "pending"}, desc="create document")
    test("GET", "/e2e-test-001", desc="get document")
    test("GET", "/e2e-test-001/files", desc="list files (empty)")
    test("GET", "/e2e-test-001/metadata", expect=404, desc="get metadata (not found)")

    print("\n--- Update ---")
    test("PUT", "/e2e-test-001", {"status": "completed"}, desc="update document status")

    print("\n--- Files ---")
    test("POST", "/e2e-test-001/files", {
        "document_id": "e2e-test-001", "filename": "report.pdf",
        "content_type": "application/pdf", "file_size": 1024000,
        "minio_key": "vault/e2e/report.pdf"
    }, desc="add file")
    test("GET", "/e2e-test-001/files", desc="list files (1 file)")

    print("\n--- Metadata ---")
    test("PUT", "/e2e-test-001/metadata", {
        "title": "E2E Test Report", "page_count": 42, "word_count": 15000, "language": "en"
    }, desc="upsert metadata (create)")
    test("GET", "/e2e-test-001/metadata", desc="get metadata")
    test("PUT", "/e2e-test-001/metadata", {"title": "Updated Title"}, desc="upsert metadata (update)")

    print("\n--- Content ---")
    test("POST", "/e2e-test-001/content", {
        "parser_id": "pdf-v1", "text_content": "Extracted text from test document.",
        "text_length": 33, "success": True
    }, desc="store content")
    test("GET", "/e2e-test-001/content", desc="list contents")
    test("GET", "/e2e-test-001/content/pdf-v1", desc="get content by parser")

    print("\n--- Stats After Create ---")
    test("GET", "/stats", desc="stats with documents")

    print("\n--- Delete & Verify ---")
    test("DELETE", "/e2e-test-001", desc="delete document")
    test("GET", "/e2e-test-001", expect=404, desc="verify deleted (404)")
    test("GET", "/e2e-test-001/files", expect=404, desc="files of deleted doc (404)")

    print("\n--- Edge Cases ---")
    test("POST", "", {"document_id": "dup-001", "filename": "a.md"}, desc="create first doc")
    test("POST", "", {"document_id": "dup-001", "filename": "b.md"}, expect=409, desc="duplicate (409)")
    test("GET", "/nonexistent-id", expect=404, desc="nonexistent doc (404)")
    test("DELETE", "/dup-001", desc="cleanup")

    print(f"\n=== Results: {passed} passed, {failed} failed ===")
    return failed == 0


if __name__ == "__main__":
    # Start server
    config = uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Wait for server
    print(f"Starting server on port {PORT}...")
    for i in range(30):
        time.sleep(1)
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/docs", timeout=2)
            print(f"Server ready after {i+1}s\n")
            break
        except Exception:
            if i == 29:
                print("Server failed to start after 30s")
                sys.exit(1)

    # Run tests
    success = run_tests()

    # Stop server
    server.should_exit = True
    time.sleep(1)

    sys.exit(0 if success else 1)
