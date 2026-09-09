"""Achieve one desktop goal, the cheapest way that works.

THE DIVISION OF LABOUR, and it is the whole idea:

    the MODEL decides WHAT to click.      It is a judgement. Models are good at it.
    WINDOWS says WHERE that thing is.     It is a fact. UI Automation is exact.

Two tiers, and it only pays for the one it needs:

  1. REMEMBERED  - the model already chose this once and it worked. Click the
                   same element by name. ~1 s, no model call, no money.
  2. LOOK        - hand the model the screen AND a numbered list of everything
                   clickable, and ask which number. ~6 s.

There is deliberately NO string-matching tier. Matching goal text against
element names is guessing without understanding: "open my music" finds nothing
though Spotify is right there, and "open settings" would hit a Settings button
inside the current window instead of the app. Tier 1 is not string matching -
it is a cached decision the model already made and that we saw work.

THE ONE RULE THAT SHAPES THIS FILE: the model never sees a coordinate and never
supplies one. It picks a NUMBER from a list; the coordinates come from Windows
UI Automation, which is exact. Measured 2026-09-09, Gemini asked to point at an
icon in a 960x540 image answered y=971, then missed by 24 px. Reading a screen
and pointing at it are different skills, and general vision models only have the
first one.

The screenshot is attached on EVERY model turn, never requested. Perception is
not a tool the model can forget to call - which is exactly how the previous
attempt failed.
"""

from __future__ import annotations

import json
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

import act  # noqa: E402
import brain  # noqa: E402
import screen  # noqa: E402

MAX_STEPS = 6  # a hard cap: a loop that cannot finish must stop, not wander
SHOT = Path.home() / "AppData" / "Local" / "Temp" / "divyastra-screen.jpg"
MEMORY = _HERE / "memory.json"
OVERVIEW_WIDTH = 960  # half of 1920. Measured legibility floor; below this icons blur.

# Words that describe the doing, not the thing to be done.
_VERBS = r"(?:please\s+)?(?:can\s+you\s+)?(?:open|launch|start|go\s+to|bring\s+up|show|switch\s+to|run)\s+"


@dataclass
class Result:
    ok: bool
    how: str  # "remembered" | "looked" | "failed"
    detail: str
    steps: int = 0
    seconds: float = 0.0
    model_calls: int = 0
    tokens: int = 0
    trace: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        money = f", {self.model_calls} model call(s), {self.tokens} tokens" if self.model_calls else ", no model call"
        return (f"{'OK' if self.ok else 'FAILED'} [{self.how}] {self.detail} "
                f"({self.steps} step(s), {self.seconds:.1f}s{money})")


# --- memory: what worked last time ------------------------------------------


def _memory() -> dict:
    if MEMORY.exists():
        try:
            return json.loads(MEMORY.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def _remember(target: str, element_name: str) -> None:
    """Store the element NAME, not its coordinates.

    Names survive a taskbar that shifts when another app is pinned; coordinates
    do not. Looking the name up again is free, so there is nothing to gain by
    caching the position and a stale click to lose.
    """
    m = _memory()
    m[target] = {"element": element_name, "learned": time.strftime("%Y-%m-%d %H:%M")}
    MEMORY.write_text(json.dumps(m, indent=2), encoding="utf-8")


def target_of(goal: str) -> str:
    """"open YouTube please" -> "youtube". The thing, without the doing."""
    g = goal.strip().lower().rstrip(".!?")
    g = re.sub(_VERBS, "", g, count=1)
    g = re.sub(r"\s+(for me|please|now)$", "", g)
    return g.strip()


# --- the loop ----------------------------------------------------------------


def _numbered(elements: list[screen.Element], limit: int = 40) -> str:
    return "\n".join(f"{i}. {e.name}" for i, e in enumerate(elements[:limit]))


def _overview(path: Path) -> Path:
    """Full capture, then a half-size JPEG for the model. The full one stays on
    disk and costs nothing."""
    from PIL import Image

    raw = path.with_suffix(".png")
    screen.capture(raw)
    im = Image.open(raw).convert("RGB")
    if im.width > OVERVIEW_WIDTH:
        h = round(im.height * OVERVIEW_WIDTH / im.width)
        im = im.resize((OVERVIEW_WIDTH, h), Image.LANCZOS)
    im.save(path, "JPEG", quality=80)
    return path


def do(goal: str, verbose: bool = True) -> Result:
    """Do one desktop goal and report what it cost."""
    t0 = time.time()
    target = target_of(goal)
    trace: list[str] = []

    def log(msg: str) -> None:
        trace.append(msg)
        if verbose:
            print(f"  {msg}", flush=True)

    log(f'goal "{goal}" -> looking for "{target}"')
    elements = screen.everything()
    log(f"{len(elements)} clickable elements on screen")

    # --- tier 1: remembered ---
    known = _memory().get(target)
    if known:
        hits = [e for e in elements if e.name == known["element"]]
        if hits:
            e = hits[0]
            log(f"remembered: {e.name}")
            act.click(e.x, e.y)
            return Result(True, "remembered", e.name, 1, time.time() - t0, trace=trace)
        log("remembered it, but it is not on screen now")

    # NO STRING-MATCHING TIER. It was here and it was wrong: matching the goal
    # text against element names is guessing without understanding. "open chrome"
    # only matched "Batman - Chrome - 1 running window pinned" by luck; "open my
    # music" finds nothing though Spotify is right there, and "open settings"
    # would happily hit a Settings BUTTON inside the current window instead of
    # the app. Deciding what to click is a judgement, and that is exactly what
    # the model is good at. It just must not be asked where the thing is.

    # --- tier 2: look ---
    calls = tokens = 0
    for step in range(1, MAX_STEPS + 1):
        shot = _overview(SHOT)
        elements = screen.everything()
        prompt = (
            f"GOAL: {goal}\n\n"
            "You are looking at a Windows desktop. Below is every clickable thing on it, "
            "numbered. The screenshot is attached so you can see context.\n\n"
            f"{_numbered(elements)}\n\n"
            "Reply with strict JSON, one action only:\n"
            '  {"action":"click","n":<number from the list>,"why":"<6 words>"}\n'
            '  {"action":"type","text":"<text>","why":"..."}\n'
            '  {"action":"key","key":"return","why":"..."}\n'
            '  {"action":"done","why":"the goal is already achieved"}\n'
            "Never invent coordinates. Choose by number only."
        )
        reply = brain.ask(prompt, image=shot)
        calls += 1
        tokens += brain.last_tokens
        action = str(reply.get("action", "")).lower()
        why = str(reply.get("why", ""))[:60]
        log(f"step {step}: {action} {why} ({brain.last_seconds:.1f}s)")

        if action == "done":
            return Result(True, "looked", why or "model says done", step,
                          time.time() - t0, calls, tokens, trace)
        if action == "click":
            try:
                e = elements[int(reply["n"])]
            except (KeyError, ValueError, IndexError, TypeError):
                log(f"bad element number: {reply!r}")
                continue
            log(f"clicking {e.name} @ {e.x},{e.y}")
            act.click(e.x, e.y)
            _remember(target, e.name)
            return Result(True, "looked", e.name, step, time.time() - t0, calls, tokens, trace)
        if action == "type":
            act.type_text(str(reply.get("text", "")))
            continue
        if action == "key":
            act.press(str(reply.get("key", "return")))
            continue
        log(f"unusable reply: {reply!r}")

    return Result(False, "failed", f"gave up after {MAX_STEPS} steps",
                  MAX_STEPS, time.time() - t0, calls, tokens, trace)


if __name__ == "__main__":
    goal = " ".join(sys.argv[1:]) or "open youtube"
    print(do(goal))
