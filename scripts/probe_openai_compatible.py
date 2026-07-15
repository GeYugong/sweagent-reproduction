#!/usr/bin/env python3
"""Probe an OpenAI-compatible endpoint without printing credentials."""

from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone


def candidate_urls(base_url: str) -> list[str]:
    base = base_url.rstrip("/")
    if base.endswith("/v1"):
        return [f"{base}/models"]
    return [f"{base}/v1/models", f"{base}/models"]


def probe(url: str, api_key: str, timeout: float) -> dict[str, object]:
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "User-Agent": "sweagent-reproduction-probe/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=ssl.create_default_context()) as response:
            payload = json.load(response)
            model_ids = sorted(
                item["id"]
                for item in payload.get("data", [])
                if isinstance(item, dict) and isinstance(item.get("id"), str)
            )
            return {
                "url": url,
                "http_status": response.status,
                "content_type": response.headers.get("Content-Type"),
                "model_count": len(model_ids),
                "model_ids": model_ids,
                "openai_schema": isinstance(payload.get("data"), list),
            }
    except urllib.error.HTTPError as exc:
        return {"url": url, "http_status": exc.code, "error": "HTTPError"}
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {"url": url, "http_status": None, "error": type(exc).__name__}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=os.environ.get("OPENAI_BASE_URL"))
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key or not args.base_url:
        print("OPENAI_API_KEY and OPENAI_BASE_URL are required.", file=sys.stderr)
        return 2

    attempts = [probe(url, api_key, args.timeout) for url in candidate_urls(args.base_url)]
    report = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "base_url": args.base_url.rstrip("/"),
        "attempts": attempts,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if any(item.get("http_status") == 200 and item.get("openai_schema") for item in attempts) else 1


if __name__ == "__main__":
    raise SystemExit(main())
