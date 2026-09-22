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

MAX_STEPS = 8  # a hard cap: a loop that cannot finish must stop, not wander
SETTLE = 1.2   # seconds to let the UI catch up before looking again
SHOT = Path.home() / "AppData" / "Local" / "Temp" / "divyastra-screen.jpg"
MEMORY = _HERE / "memory.json"
OVERVIEW_WIDTH = 960  # half of 1920. Measured legibility floor; below this icons blur.

# Words that describe the doing, not the thing to be done. Used to STRIP the
# verb off a goal so "open YouTube" -> "youtube" for the memory key.
_VERBS = r"(?:please\s+)?(?:can\s+you\s+)?(?:open|launch|start|go\s+to|bring\s+up|show|switch\s+to|run)\s+"

# A SEPARATE verb set, for ROUTING only: does a spoken sentence look like a
# desktop command at all, or is it conversation for the brain? Kept apart from
# _VERBS on purpose - "what can you open" must NOT route here, so this one is
# anchored to the start of the sentence, and it is wider (play/close/pause are
# desktop actions but are not app-openers, so they do not belong in _VERBS).
# Do not merge the two: stripping and routing are different jobs.
_ROUTE = re.compile(
    r"^\s*(?:please\s+|hey\s+divya[,\s]+|divya[,\s]+)?"
    r"(?:can\s+you\s+|could\s+you\s+|would\s+you\s+)?"
    r"(?:open|launch|start|run|play|close|quit|switch\s+to|go\s+to|bring\s+up|"
    r"show|pause|resume|minimi[sz]e|maximi[sz]e)\b",
    re.I,
)


def is_desktop_command(text: str) -> bool:
    """True if a spoken sentence should be handled on the desktop, not by the brain.

    A heuristic on purpose: a verb at the START of the sentence. It can be
    wrong both ways, and neither way is a disaster - a mis-routed question wastes
    a few model calls before the loop gives up, a mis-routed command takes the
    slower brain path. It just must not fire on questions ABOUT the desktop,
    which is why it is anchored to the start.
    """
    return bool(_ROUTE.match(text or ""))


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


def app_of(element_name: str) -> str:
    """The stable app identity inside a taskbar button's name.

    MEASURED THE HARD WAY 2026-09-09: taskbar names change with state, so the
    obvious "remember the name" is wrong and silently costs a model call every
    time. All of these are the same button:

        "Spotify pinned"                        (closed)
        "Spotify - 1 running window pinned"     (open)
        "Batman - Chrome - 1 running window pinned"   (open, and the page title
                                                       rides in front)

    Windows puts the app name last, before the state suffixes. Strip those and
    take the final segment, and all three collapse to "Spotify" / "Chrome".
    """
    n = element_name.strip()
    n = re.sub(r"\s*-\s*\d+\s+running\s+windows?", "", n, flags=re.I)
    n = re.sub(r"\s*\bpinned\b\s*$", "", n, flags=re.I)
    n = n.strip(" -")
    if " - " in n:
        n = n.split(" - ")[-1].strip()
    return n


def _remember(target: str, element_name: str) -> None:
    """Store the app identity, not the full name and not coordinates.

    Coordinates go stale the moment anything is pinned or unpinned; full names
    go stale the moment the app opens. The app identity survives both, and
    looking it up again is free.
    """
    m = _memory()
    m[target] = {"app": app_of(element_name), "learned": time.strftime("%Y-%m-%d %H:%M")}
    MEMORY.write_text(json.dumps(m, indent=2), encoding="utf-8")


def target_of(goal: str) -> str:
    """"open YouTube please" -> "youtube". The thing, without the doing."""
    g = goal.strip().lower().rstrip(".!?")
    g = re.sub(_VERBS, "", g, count=1)
    g = re.sub(r"\s+(for me|please|now)$", "", g)
    return g.strip()


# --- the loop ----------------------------------------------------------------


def _numbered(elements: list[screen.Element], limit: int = 70) -> str:
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
        # Compare app identities, not raw names: the same button is called
        # different things depending on whether the app happens to be running.
        want = app_of(known.get("app") or known.get("element", ""))
        hits = [e for e in elements if app_of(e.name) == want]
        if hits:
            e = hits[0]
            log(f"remembered: {want} -> {e.name}")
            act.click(e.x, e.y)
            return Result(True, "remembered", e.name, 1, time.time() - t0, trace=trace)
        log(f"remembered {want!r}, but it is not on screen now")

    # NO STRING-MATCHING TIER. It was here and it was wrong: matching the goal
    # text against element names is guessing without understanding. "open chrome"
    # only matched "Batman - Chrome - 1 running window pinned" by luck; "open my
    # music" finds nothing though Spotify is right there, and "open settings"
    # would happily hit a Settings BUTTON inside the current window instead of
    # the app. Deciding what to click is a judgement, and that is exactly what
    # the model is good at. It just must not be asked where the thing is.

    # --- tier 2: look ---
    calls = tokens = 0
    did: list[str] = []   # what actually happened, for the report
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
            detail = " -> ".join(did) if did else (why or "already done")
            return Result(True, "looked", detail, step,
                          time.time() - t0, calls, tokens, trace)
        if action == "click":
            try:
                e = elements[int(reply["n"])]
            except (KeyError, ValueError, IndexError, TypeError):
                log(f"bad element number: {reply!r}")
                continue
            # Prefer the snapshot token: it invokes the element through the
            # accessibility layer instead of aiming a pointer at a rectangle,
            # so it survives a window that scrolled or moved a pixel since.
            if e.token and e.pid:
                log(f"clicking {e.name} (token)")
                r = act.click_token(e.token, e.pid)
                if str(r.get("effect")) == "refused" or "error" in r:
                    log("token refused, falling back to the point")
                    act.click(e.x, e.y)
            else:
                log(f"clicking {e.name} @ {e.x},{e.y}")
                act.click(e.x, e.y)
            did.append(e.name)
            # Only the FIRST action of a goal is worth remembering: it is the
            # one that reliably repeats ("open Spotify"). Later steps depend on
            # what the app was showing at the time, so caching them would
            # replay a click into whatever happens to be there next time.
            if step == 1:
                _remember(target, e.name)
            time.sleep(SETTLE)
            continue  # a click is rarely the whole job - look again
        if action == "type":
            text = str(reply.get("text", ""))
            log(f"typing {text!r}")
            act.type_text(text)
            did.append(f"typed {text!r}")
            time.sleep(SETTLE)
            continue
        if action == "key":
            k = str(reply.get("key", "return"))
            log(f"pressing {k}")
            act.press(k)
            did.append(f"pressed {k}")
            time.sleep(SETTLE)
            continue
        log(f"unusable reply: {reply!r}")

    detail = f"gave up after {MAX_STEPS} steps"
    if did:
        detail += " (did: " + " -> ".join(did) + ")"
    return Result(False, "failed", detail, MAX_STEPS, time.time() - t0, calls, tokens, trace)


if __name__ == "__main__":
    goal = " ".join(sys.argv[1:]) or "open youtube"
    print(do(goal))
