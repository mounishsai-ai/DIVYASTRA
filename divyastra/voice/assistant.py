"""The always-on loop: wake -> listen -> think -> speak.

This is the only file that ties the voice pieces together. Each piece stays
ignorant of the others — `wake.py` does not know what happens after a wake,
`stt.py` does not know who reads the text, `tts.py` does not know who wrote it.

Cost shape, which is the whole point of the design:

    waiting for the wake word   0 tokens, 0 money, ~7% of one core
    woken but you said nothing  0 tokens, 0 money
    you actually asked something  one Hermes run (~$0.01 to talk, more to act)

Nothing expensive happens until there are real words to act on.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import sounddevice as sd

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

import stt  # noqa: E402
import tts  # noqa: E402
import wake  # noqa: E402

# --- how she reaches her brain ----------------------------------------------
HERMES = Path.home() / "AppData" / "Local" / "hermes" / "bin" / "hermes.exe"
# Hermes ingests CLAUDE.md/AGENTS.md from its working directory, so it must NOT
# run inside this repo — that would inject ~7 KB of build-time docs into every
# call. See docs/01-architecture.md.
WORK_DIR = Path(tempfile.gettempdir()) / "divyastra-work"
THINK_TIMEOUT = 600  # a desktop task can genuinely take minutes

# --- feedback ----------------------------------------------------------------
CHIME_HZ = 880
CHIME_SECONDS = 0.12


def chime(freq: int = CHIME_HZ) -> None:
    """Instant 'I'm listening' cue. Faster than speaking, so it feels responsive."""
    t = np.arange(0, CHIME_SECONDS, 1 / stt.SAMPLE_RATE)
    tone = (np.sin(2 * np.pi * freq * t) * 0.3).astype(np.float32)
    sd.play(tone, stt.SAMPLE_RATE)
    sd.wait()


def ask_hermes(prompt: str) -> str:
    """Send one instruction to Hermes and return what she says back."""
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    try:
        result = subprocess.run(
            [str(HERMES), "-z", prompt],
            cwd=str(WORK_DIR),
            capture_output=True,
            text=True,
            timeout=THINK_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return "That took too long, so I stopped."
    except FileNotFoundError:
        return "I cannot find Hermes. Check that it is installed."
    out = (result.stdout or "").strip()
    if not out:
        err = (result.stderr or "").strip().splitlines()
        return "Something went wrong: " + (err[-1] if err else "no output.")
    return out


# What she says when woken. A chime is faster, but a spoken cue is unmistakable
# - tested with a chime first and it was too subtle to act on.
ACK = "Yes?"


def handle_one_turn() -> None:
    """One complete interaction, from the acknowledgement to her answer."""
    tts.speak(ACK)
    heard = stt.listen(max_seconds=20)
    if not heard:
        # False wake, or you changed your mind. Costs nothing. Go back to sleep.
        print("  (nothing said - back to sleep)")
        return

    print(f"  you : {heard}")
    t0 = time.time()
    reply = ask_hermes(heard)
    print(f"  her : {reply}")
    print(f"  ({time.time() - t0:.1f}s)")
    tts.speak(reply)


def main() -> None:
    print("DIVYASTRA - loading models...")
    tts._get_engine()
    stt._get_model()
    wake.load()
    print(f"ready. wake word: '{wake.WAKE_WORD}' (threshold {wake.threshold()})")
    print("listening. Ctrl+C to stop.\n")
    tts.speak("Systems online.")

    try:
        for score in wake.listen_for_wake():
            print(f"[{time.strftime('%H:%M:%S')}] wake  score={score:.2f}")
            try:
                handle_one_turn()
            except Exception as exc:  # never let one bad turn kill the loop
                print(f"  !! {exc}")
                tts.speak("Something went wrong on my side.")
            print()
    except KeyboardInterrupt:
        print("stopped")


if __name__ == "__main__":
    main()
