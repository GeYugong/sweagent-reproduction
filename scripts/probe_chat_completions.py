#!/usr/bin/env python3
"""Send a minimal legacy Chat Completions request and report safe metadata."""

from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone


def endpoint(base_url: str) -> str:
    base = base_url.rstrip("/")
    return f"{base}/chat/completions" if base.endswith("/v1") else f"{base}/v1/chat/completions"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=os.environ.get("OPENAI_BASE_URL"))
    parser.add_argument("--model", required=True)
    parser.add_argument("--timeout", type=float, default=90.0)
    args = parser.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key or not args.base_url:
        print("OPENAI_API_KEY and OPENAI_BASE_URL are required.", file=sys.stderr)
        return 2

    body = json.dumps(
        {
            "model": args.model,
            "messages": [{"role": "user", "content": "Reply exactly with OK."}],
            "temperature": 0.0,
            "top_p": 0.95,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        endpoint(args.base_url),
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "sweagent-reproduction-probe/1.0",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=args.timeout, context=ssl.create_default_context()) as response:
            payload = json.load(response)
            choice = payload.get("choices", [{}])[0]
            message = choice.get("message", {}) if isinstance(choice, dict) else {}
            usage = payload.get("usage", {})
            report = {
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "endpoint": endpoint(args.base_url),
                "requested_model": args.model,
                "response_model": payload.get("model"),
                "http_status": response.status,
                "object": payload.get("object"),
                "finish_reason": choice.get("finish_reason") if isinstance(choice, dict) else None,
                "content": message.get("content") if isinstance(message, dict) else None,
                "usage": {
                    "prompt_tokens": usage.get("prompt_tokens"),
                    "completion_tokens": usage.get("completion_tokens"),
                    "total_tokens": usage.get("total_tokens"),
                },
                "legacy_chat_schema": isinstance(payload.get("choices"), list)
                and isinstance(message, dict)
                and "content" in message,
            }
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0 if report["legacy_chat_schema"] else 1
    except urllib.error.HTTPError as exc:
        print(
            json.dumps(
                {
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "endpoint": endpoint(args.base_url),
                    "requested_model": args.model,
                    "http_status": exc.code,
                    "error": "HTTPError",
                },
                indent=2,
            )
        )
        return 1
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(json.dumps({"requested_model": args.model, "error": type(exc).__name__}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
