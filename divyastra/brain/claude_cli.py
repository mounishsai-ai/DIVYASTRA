"""Claude Code as DIVYASTRA's brain, invoked non-interactively.

The only file that knows how to reach Claude (rule 4). `think()` is the whole
public surface, and it mirrors the Hermes/Gemini path in `voice/assistant.py`
so the two are interchangeable.

WHY THIS IS ALLOWED, and the earlier note in docs/02-decisions.md was wrong:
Anthropic's Pro plan includes a monthly Agent SDK credit that explicitly covers
**"the `claude -p` command in Claude Code (non-interactive mode)"**. Piping a
raw API key from a subscription would not be allowed; shelling out to `claude
-p` is a documented, supported path.

WHAT IT COSTS: the credit is **$20/month and does not roll over**. Claude is
several times the price of Gemini Flash per token, so this is the *escalation*
brain for hard multi-step work, not the everyday one. See `docs/02-decisions.md`
D4 for the arithmetic.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent.parent

CLAUDE = shutil.which("claude") or str(Path.home() / ".local" / "bin" / "claude")

# Only the limbs DIVYASTRA is meant to have. `--strict-mcp-config` means nothing
# else the machine happens to have configured leaks in.
MCP_CONFIG = _ROOT / "divyastra" / "config" / "claude-brain-mcp.json"

# Her persona, so the CLI brain sounds like the Hermes one. Same source file.
PERSONA = _ROOT / "divyastra" / "voice" / "personality.md"

# Deliberately narrower than "everything cua-driver offers". Matches the 18
# tools Hermes is allowed. No clipboard, no kill_app, no recording.
ALLOWED_TOOLS = [
    "mcp__cua-driver__launch_app",
    "mcp__cua-driver__list_apps",
    "mcp__cua-driver__list_windows",
    "mcp__cua-driver__get_window_state",
    "mcp__cua-driver__click",
    "mcp__cua-driver__double_click",
    "mcp__cua-driver__type_text",
    "mcp__cua-driver__press_key",
    "mcp__cua-driver__hotkey",
    "mcp__cua-driver__set_value",
    "mcp__cua-driver__scroll",
    "mcp__cua-driver__verify_state",
    "mcp__cua-driver__bring_to_front",
    "mcp__cua-driver__browser_prepare",
    "mcp__cua-driver__browser_navigate",
    "mcp__cua-driver__browser_click",
    "mcp__cua-driver__browser_type",
    "mcp__cua-driver__get_browser_state",
]

TIMEOUT = 900  # a real desktop task can take minutes

# Set by the last think() call. MEASURED 2026-09-08 on this machine:
#   trivial reply      $0.097   (Hermes/Gemini: $0.0088  -> 11x)
#   Calculator task    $1.343   (Hermes/Gemini: $0.12    -> 11x)
# The floor is high because Claude Code loads a ~25,000-token system prompt on
# every invocation. At $20/month that is roughly 15 desktop tasks. Escalation
# brain, not the everyday one.
last_cost_usd: float = 0.0
last_turns: int = 0


def _persona_text() -> str:
    """Her persona, minus the build-time header that lives above the --- rule."""
    if not PERSONA.exists():
        return ""
    body = PERSONA.read_text(encoding="utf-8")
    return body.split("\n---\n", 1)[-1].strip() if "\n---\n" in body else body.strip()


def think(task: str, cwd: str | Path | None = None) -> str:
    """Hand one task to Claude Code and return what it says.

    Runs with a neutral working directory by default. Never point this at the
    project repo: Claude Code would load CLAUDE.md and the docs, which are
    build-time instructions, not runtime ones.
    """
    if not MCP_CONFIG.exists():
        return f"Missing MCP config at {MCP_CONFIG}."

    cmd = [
        CLAUDE,
        "-p",
        task,
        "--mcp-config",
        str(MCP_CONFIG),
        "--strict-mcp-config",
        "--allowedTools",
        *ALLOWED_TOOLS,
        "--output-format",
        "json",  # carries total_cost_usd - we cannot budget what we cannot see
    ]
    persona = _persona_text()
    if persona:
        cmd += ["--append-system-prompt", persona]

    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            stdin=subprocess.DEVNULL,  # else the CLI waits 3s for piped input
        )
    except subprocess.TimeoutExpired:
        return "That took too long, so I stopped."
    except FileNotFoundError:
        return "I cannot find the Claude CLI."

    out = (result.stdout or "").strip()
    if not out:
        err = (result.stderr or "").strip().splitlines()
        return "Something went wrong: " + (err[-1] if err else "no output.")

    try:
        payload = json.loads(out)
    except json.JSONDecodeError:
        return out  # not JSON for some reason; hand back whatever came out

    global last_cost_usd, last_turns
    last_cost_usd = float(payload.get("total_cost_usd") or 0.0)
    last_turns = int(payload.get("num_turns") or 0)
    return str(payload.get("result") or "").strip()


if __name__ == "__main__":
    import sys
    import time

    prompt = " ".join(sys.argv[1:]) or "Reply with exactly: SUIT ONLINE"
    print(f"claude : {CLAUDE}")
    print(f"tools  : {len(ALLOWED_TOOLS)} cua-driver tools, strict MCP")
    t0 = time.time()
    print(f"\n{think(prompt)}")
    print(f"\n({time.time() - t0:.1f}s, {last_turns} turns, ${last_cost_usd:.4f})")
