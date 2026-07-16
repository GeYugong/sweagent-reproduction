#!/usr/bin/env python3
"""Validate Requests off-host redirect authentication stripping locally."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


class RedirectHandler(BaseHTTPRequestHandler):
    """Serve one redirect and record the final request headers."""

    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        if self.path == "/redirect":
            port = self.server.server_address[1]
            self.send_response(302)
            self.send_header("Location", f"http://localhost:{port}/final")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        if self.path == "/final":
            self.server.final_authorization = self.headers.get("Authorization")
            payload = b"ok\n"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        self.send_error(404)

    def log_message(self, format: str, *args: Any) -> None:
        return


class RecordingHTTPServer(ThreadingHTTPServer):
    final_authorization: str | None = None


def validate(source: Path, input_manifest_path: Path) -> dict[str, Any]:
    source = source.resolve()
    sys.path.insert(0, str(source))
    import requests  # pylint: disable=import-outside-toplevel

    imported_from = Path(requests.__file__).resolve()
    if source not in imported_from.parents:
        raise RuntimeError(f"Requests imported outside source checkout: {imported_from}")

    input_manifest = json.loads(input_manifest_path.read_text(encoding="utf-8"))
    source_files = [source / "requests" / "sessions.py", source / "test_requests.py"]
    source_file_sha256 = {
        path.relative_to(source).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in source_files
    }

    server = RecordingHTTPServer(("127.0.0.1", 0), RedirectHandler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        port = server.server_address[1]
        session = requests.Session()
        session.trust_env = False
        response = session.get(
            f"http://127.0.0.1:{port}/redirect",
            auth=("user", "pass"),
            timeout=5,
        )
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)

    history_authorization = (
        response.history[0].request.headers.get("Authorization")
        if response.history
        else None
    )
    final_authorization = response.request.headers.get("Authorization")
    result = {
        "schema_version": 1,
        "validated_at_utc": datetime.now(timezone.utc).isoformat(),
        "validation_method": "local_cross_hostname_redirect",
        "instance_id": input_manifest["instance_id"],
        "source_base_commit": input_manifest["base_commit"],
        "gold_patch_sha256": input_manifest["gold_patch_sha256"],
        "test_patch_sha256": input_manifest["test_patch_sha256"],
        "source_file_sha256": source_file_sha256,
        "python_version": sys.version.split()[0],
        "requests_version": requests.__version__,
        "requests_import": imported_from.as_posix(),
        "status_code": response.status_code,
        "history_length": len(response.history),
        "initial_authorization_present": bool(history_authorization),
        "final_authorization_absent_client": final_authorization is None,
        "final_authorization_absent_server": server.final_authorization is None,
        "source_hostname": "127.0.0.1",
        "destination_hostname": "localhost",
    }
    expected = {
        "status_code": 200,
        "history_length": 1,
        "initial_authorization_present": True,
        "final_authorization_absent_client": True,
        "final_authorization_absent_server": True,
    }
    mismatches = {
        key: {"expected": value, "actual": result[key]}
        for key, value in expected.items()
        if result[key] != value
    }
    if mismatches:
        raise RuntimeError(f"Off-host redirect validation failed: {mismatches}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--input-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = (
        json.dumps(
            validate(args.source, args.input_manifest), indent=2, ensure_ascii=False
        )
        + "\n"
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
