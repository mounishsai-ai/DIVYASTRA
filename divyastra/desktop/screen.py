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


def foreground() -> list[Element]:
    """Every named, clickable thing in the window the user is currently looking at."""
    import uiautomation as auto

    out: list[Element] = []
    win = auto.GetForegroundControl()
    if win:
        title = (win.Name or "window").strip()
        _walk(win, f"window:{title[:40]}", out)
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
