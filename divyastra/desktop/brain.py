"""Ask Gemini one question about the screen and get one action back.

The only file that knows how to reach Vertex (rule 4). Mirrors
`brain/claude_cli.py` so the two are interchangeable.

TWO SETTINGS HERE ARE LOAD-BEARING, both measured 2026-09-09 on this machine:

1. `thinkingBudget: 0`. The same question took **31.7 s** with default thinking
   and **6.0 s** with it off. For "which of these numbered things do I click",
   deliberation buys nothing and costs five times the wall clock.

2. `responseMimeType: application/json`. The model returns a parseable action or
   we treat it as a failure. No prose to interpret.

WHAT IT COSTS: a 960x540 screenshot is **1100 image tokens** measured, not the
516 a naive tile count suggests. Fractions of a cent on Flash, but the real
budget is TIME, not money.
"""

from __future__ import annotations

import base64
import json
import time
from pathlib import Path

KEY = Path.home() / "AppData" / "Local" / "hermes" / "divyastra-vertex-key.json"
PROJECT = "divyastra-agent-37057"
LOCATION = "global"
MODEL = "gemini-3.8-flash"
SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]

RETRIES = 4   # 429s are common on the shared pool; give up only after real persistence
BACKOFF = 5   # seconds, doubling: 5, 10, 20

# Set by the last ask(). The loop budgets on these.
last_seconds: float = 0.0
last_tokens: int = 0

_creds = None


def _token() -> str:
    global _creds
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account

    if _creds is None:
        if not KEY.exists():
            raise FileNotFoundError(f"No Vertex key at {KEY}")
        _creds = service_account.Credentials.from_service_account_file(str(KEY), scopes=SCOPES)
    if not _creds.valid:
        _creds.refresh(Request())
    return _creds.token


def ask(prompt: str, image: str | Path | None = None, timeout: int = 120) -> dict:
    """Ask about the screen. Returns the parsed JSON reply, or {} on failure."""
    global last_seconds, last_tokens
    import requests

    parts: list[dict] = []
    if image:
        data = base64.b64encode(Path(image).read_bytes()).decode()
        parts.append({"inlineData": {"mimeType": "image/jpeg", "data": data}})
    parts.append({"text": prompt})

    url = (f"https://aiplatform.googleapis.com/v1/projects/{PROJECT}/locations/{LOCATION}"
           f"/publishers/google/models/{MODEL}:generateContent")
    body = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }

    # Vertex answers 429 RESOURCE_EXHAUSTED under load - hit for real on
    # 2026-09-09 mid-task, which killed the run outright. It is a shared,
    # on-demand pool, so the fix is to wait and retry rather than to fail.
    t0 = time.time()
    for attempt in range(RETRIES):
        r = requests.post(url, json=body, headers={"Authorization": f"Bearer {_token()}"},
                          timeout=timeout)
        if r.status_code != 429:
            break
        wait = BACKOFF * (2 ** attempt)
        print(f"    (Vertex busy, waiting {wait}s and retrying)", flush=True)
        time.sleep(wait)
    last_seconds = time.time() - t0
    if r.status_code != 200:
        raise RuntimeError(f"Vertex HTTP {r.status_code}: {r.text[:300]}")

    d = r.json()
    last_tokens = int(d.get("usageMetadata", {}).get("totalTokenCount") or 0)
    for cand in d.get("candidates", []):
        for p in cand.get("content", {}).get("parts", []):
            if "text" in p:
                try:
                    return json.loads(p["text"])
                except json.JSONDecodeError:
                    return {"_unparsed": p["text"][:400]}
    return {}


if __name__ == "__main__":
    print(json.dumps(ask('Reply exactly {"ok": true}'), indent=2))
    print(f"({last_seconds:.1f}s, {last_tokens} tokens)")
