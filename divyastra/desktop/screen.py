"""Answer one question: what is on screen right now, and where exactly is it?

The only file that knows how to read the screen (rule 4).

WHY THIS EXISTS. Measured 2026-09-09: asked to point at the YouTube icon in a
960x540 screenshot, Gemini 3.8 Flash returned y=971 - outside a 540-pixel-tall
image - and on a second try landed 24 px from the target, which is wider than
the icon itself. General vision models read screens well and POINT BADLY.

So we never ask a model for coordinates. Windows already knows them exactly:

    (1155, 1050)  YouTube - 1 running window pinned
    ( 545, 1050)  Start

That is UI Automation, it is free, it takes milliseconds, and it is exact. The
model's job is to choose WHICH element, by name or by number. The coordinates
come from the operating system.

This is the same choice browser-use and Microsoft's UFO2 make. The alternative -
a model fine-tuned to output pixel coordinates, like UI-TARS - is the other
valid answer, and the only reason to want one.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

CUA = Path.home() / "AppData" / "Local" / "Programs" / "Cua" / "cua-driver" / "bin" / "cua-driver.exe"

# Control types worth clicking. Anything else is decoration.
CLICKABLE = ("ButtonControl", "ListItemControl", "MenuItemControl", "TabItemControl",
             "HyperlinkControl", "CheckBoxControl", "RadioButtonControl")

MAX_DEPTH = 6  # deep enough for the taskbar and ribbons, shallow enough to stay fast


@dataclass(frozen=True)
class Element:
    """One thing on screen that can be clicked, with the exact point to click."""

    name: str
    kind: str
    x: int  # centre, screen pixels
    y: int
    source: str  # "taskbar" | "window:<title>"
    token: str = ""  # cua-driver element token, when it came from a snapshot
    pid: int = 0  # owner, needed to use the token

    def __str__(self) -> str:
        return f"{self.name}  [{self.kind} @ {self.x},{self.y}]"


def _walk(node, source: str, out: list[Element], depth: int = 0) -> None:
    if depth > MAX_DEPTH:
        return
    for child in node.GetChildren():
        try:
            name = (child.Name or "").strip()
            if child.ControlTypeName in CLICKABLE and name:
                r = child.BoundingRectangle
                if r.right > r.left and r.bottom > r.top:  # skip zero-size ghosts
                    out.append(
                        Element(
                            name=" ".join(name.split()),  # names carry newlines
                            kind=child.ControlTypeName.replace("Control", ""),
                            x=(r.left + r.right) // 2,
                            y=(r.top + r.bottom) // 2,
                            source=source,
                        )
                    )
            _walk(child, source, out, depth + 1)
        except Exception:
            continue  # a control can vanish mid-walk; that is normal, not an error


def taskbar() -> list[Element]:
    """Every named, clickable thing on the Windows taskbar."""
    import uiautomation as auto

    out: list[Element] = []
    tb = auto.PaneControl(ClassName="Shell_TrayWnd")
    if tb.Exists(maxSearchSeconds=1):
        _walk(tb, "taskbar", out)
    return out


def foreground_window() -> tuple[int, int]:
    """(pid, hwnd) of the window the user is currently looking at."""
    import ctypes

    u = ctypes.windll.user32
    hwnd = u.GetForegroundWindow()
    pid = ctypes.c_ulong()
    u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return int(pid.value), int(hwnd)


def foreground(limit: int = 60) -> list[Element]:
    """Every named, clickable thing inside the focused window.

    THIS GOES THROUGH cua-driver, NOT the plain UIA walk above, and the
    difference is the whole reason "play a song in Spotify" failed. Chromium
    builds its accessibility tree lazily, so walking a Chromium window (Spotify's
    web player, Chrome, Cursor, anything Electron) the naive way returns FOUR
    elements - Minimize, Maximize, Restore, Close - and the search box the model
    needs is simply absent from the list. It then flails at keyboard shortcuts
    because nothing clickable was offered. Measured 2026-09-09.

    cua-driver's snapshot of the same window returns ~2500 elements, 1796 of
    them named. So this is a real capability difference, not a tuning knob.

    Elements carry an `element_token` valid only until the next snapshot of the
    same window, which is why the loop must act on the snapshot it just showed.
    """
    from act import _call

    pid, hwnd = foreground_window()
    try:
        d = _call("get_window_state", {"pid": pid, "window_id": hwnd,
                                       "max_elements": 400, "max_depth": 24})
    except Exception:
        return []

    title = str(d.get("app_name") or "window")
    out: list[Element] = []
    seen: set[tuple] = set()
    for e in d.get("elements") or []:
        label = " ".join(str(e.get("label") or "").split())
        role = str(e.get("role") or "")
        if not label or role in ("Document", "Pane", "Group", "Custom"):
            continue
        if not (set(e.get("actions") or []) & {"invoke", "set_value", "select", "toggle"}):
            continue
        f = e.get("frame") or {}
        w, h = int(f.get("w") or 0), int(f.get("h") or 0)
        if w <= 0 or h <= 0:  # off-screen or collapsed
            continue
        key = (label, role)
        if key in seen:
            continue
        seen.add(key)
        out.append(
            Element(
                name=label[:80],
                kind=role,
                x=int(f.get("x") or 0) + w // 2,
                y=int(f.get("y") or 0) + h // 2,
                source=f"window:{title[:30]}",
                token=str(e.get("element_token") or ""),
                pid=pid,
            )
        )
        if len(out) >= limit:
            break
    return out


def everything() -> list[Element]:
    """The taskbar plus the focused window - what a person can see and click."""
    return taskbar() + foreground()


def find(query: str, elements: list[Element] | None = None) -> list[Element]:
    """Elements whose name mentions `query`, best match first.

    A whole-word hit beats a substring one, so "chrome" does not lose to
    "Chromecast" and "mail" does not match "Gmail attachments" ahead of "Mail".
    """
    items = elements if elements is not None else everything()
    q = query.lower().strip()
    if not q:
        return []
    scored = []
    for e in items:
        low = e.name.lower()
        if q not in low:
            continue
        words = low.replace("-", " ").replace("_", " ").split()
        if q in words:
            rank = 0  # exact word
        elif low.startswith(q):
            rank = 1
        else:
            rank = 2
        scored.append((rank, len(e.name), e))
    scored.sort(key=lambda t: (t[0], t[1]))
    return [e for _r, _l, e in scored]


def capture(path: str | Path) -> tuple[int, int]:
    """Write a full-resolution screenshot to `path`. Returns (width, height).

    Written to a file rather than returned inline on purpose: a capture that
    lives on disk costs zero model tokens until something chooses to look at it.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        [str(CUA), "call", "get_desktop_state",
         "--args", f'{{"screenshot_out_file": "{path.as_posix()}"}}'],
        capture_output=True, text=True, timeout=60,
    )
    if r.returncode != 0:
        raise RuntimeError(f"screenshot failed: {(r.stderr or r.stdout)[:200]}")
    import json

    d = json.loads(r.stdout)
    return int(d.get("screenshot_width", 0)), int(d.get("screenshot_height", 0))


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        hits = find(" ".join(sys.argv[1:]))
        print(f"{len(hits)} match(es):")
        for e in hits[:10]:
            print(f"  {e}")
    else:
        items = everything()
        print(f"{len(items)} clickable elements on screen\n")
        for e in items:
            print(f"  ({e.x:>5},{e.y:>5})  {e.name[:60]}")
