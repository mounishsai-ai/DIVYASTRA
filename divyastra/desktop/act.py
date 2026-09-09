"""Do one thing to the desktop, and say whether it worked.

The only file that knows how to drive cua-driver (rule 4). Every action is a
single call with a single effect - nothing here decides WHAT to do.

The action vocabulary is deliberately tiny and closed. Measured 2026-09-09:
when a weak model was told to "take a screenshot" it pressed Win+Shift+S and
hung, because a snip goes to the clipboard and never reaches the model. A model
can only pick a wrong action if a wrong action is on the menu.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

CUA = Path.home() / "AppData" / "Local" / "Programs" / "Cua" / "cua-driver" / "bin" / "cua-driver.exe"
TIMEOUT = 60


def _call(tool: str, args: dict) -> dict:
    """One cua-driver tool call. Raises on transport failure, not on refusal."""
    # encoding is not optional here: a Chromium window's UIA dump is ~600 KB of
    # UTF-8 and Python's default cp1252 on Windows dies on it mid-read.
    r = subprocess.run(
        [str(CUA), "call", tool, "--args", json.dumps(args)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=TIMEOUT,
    )
    out = (r.stdout or "").strip()
    if r.returncode != 0 and not out:
        raise RuntimeError(f"{tool} failed: {(r.stderr or '')[:200]}")
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return {"raw": out, "stderr": (r.stderr or "")[:200]}


def click(x: int, y: int) -> dict:
    """Click a point in screen pixels.

    `foreground` delivery is used deliberately: these coordinates come from UI
    Automation and point at shell surfaces like the taskbar, where background
    PostMessage delivery is silently dropped.
    """
    return _call("click", {"scope": "desktop", "x": int(x), "y": int(y),
                           "delivery_mode": "foreground"})


def type_text(text: str) -> dict:
    """Type into whatever currently has focus."""
    return _call("type_text", {"scope": "desktop", "text": text})


def press(key: str) -> dict:
    """Press a key or a combination - "return", "f5", "ctrl+k", "alt+tab".

    press_key takes ONE key; a combination has to go to `hotkey` instead.
    Measured 2026-09-09: the model asked for ctrl+k to open Spotify's search,
    it was sent to press_key, and nothing happened - so the model tried again,
    and again. A silently-ignored action looks exactly like a wrong decision.
    """
    parts = [k.strip().lower() for k in key.replace("-", "+").split("+") if k.strip()]
    if len(parts) > 1:
        return _call("hotkey", {"scope": "desktop", "keys": parts})
    return _call("press_key", {"scope": "desktop", "key": parts[0] if parts else key})


def click_token(token: str, pid: int) -> dict:
    """Click an element by its snapshot token - no coordinates at all.

    Tokens come from a get_window_state snapshot and expire when the next
    snapshot of that window replaces them, so click from the SAME snapshot that
    was shown to the model.
    """
    return _call("click", {"element_token": token, "pid": int(pid)})


def windows() -> list[dict]:
    """Every on-screen top-level window. Used to verify an action landed."""
    d = _call("list_windows", {"on_screen_only": True})
    return d.get("windows") or d.get("_legacy_windows") or []


def window_titles() -> list[str]:
    return [(w.get("title") or "") for w in windows()]


if __name__ == "__main__":
    import sys

    if len(sys.argv) >= 4 and sys.argv[1] == "click":
        print(click(int(sys.argv[2]), int(sys.argv[3])))
    else:
        for t in window_titles():
            print(" ", t[:70])
