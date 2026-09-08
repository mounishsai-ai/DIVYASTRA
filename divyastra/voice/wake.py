"""Listen for the wake word, and only then wake anything expensive.

The only file that knows which wake-word engine we use (rule 4).

This is what makes "idle costs nothing" literally true: a ~1 MB model scores
80 ms of audio at a time, entirely on the CPU. No network, no model calls, no
money — until you actually say her name.

It also **pauses while the laptop is locked**. A logon-started process keeps
running when you lock the screen, so without this it would sit listening to the
microphone on the lock screen. It does not.
"""

from __future__ import annotations

import ctypes
import time
from typing import Callable, Iterator

import numpy as np
import sounddevice as sd
from openwakeword.model import Model

# --- the wake word -----------------------------------------------------------
# Pretrained options that ship with openWakeWord: alexa, hey_jarvis, hey_mycroft,
# hey_rhasspy. "Divyastra" is not one of them — see docs/03-roadmap.md for the
# two ways to get a custom word.
WAKE_WORD = "hey_jarvis"
THRESHOLD = 0.25
# Measured on Mounish's voice, 2026-09-08:
#   projected/test voice : 0.83
#   NATURAL volume       : 0.49, 0.29, 0.42, and one miss at 0.05
# A 0.5 threshold caught none of the natural ones. 0.25 catches three of four.
#
# Being generous here is deliberate and cheap: a false wake costs NOTHING. She
# just listens; if no speech follows, transcription returns "" and she sleeps
# again. No model call, no money. A missed wake is the expensive failure -
# you have to say it twice - so bias towards over-triggering.
COOLDOWN_SECONDS = 1.5  # ignore repeats right after a hit

SAMPLE_RATE = 16000
CHUNK = 1280  # 80 ms — the frame size openWakeWord expects

# NOTE: openWakeWord's pretrained models are CC-BY-NC-SA 4.0 (non-commercial).
# Fine for personal use; retrain or replace before distributing DIVYASTRA.

_model: Model | None = None


def _get_model() -> Model:
    global _model
    if _model is None:
        _model = Model(wakeword_models=[WAKE_WORD], inference_framework="onnx")
    return _model


def is_locked() -> bool:
    """True when the Windows session is locked (or the screensaver is up).

    Checked by asking whether the input desktop can be opened — when the machine
    is locked, the secure desktop owns it and this fails.
    """
    try:
        user32 = ctypes.windll.User32
        hdesk = user32.OpenInputDesktop(0, False, 0x0100)  # DESKTOP_SWITCHDESKTOP
        if hdesk == 0:
            return True
        user32.CloseDesktop(hdesk)
        return False
    except Exception:
        return False  # fail open rather than deafen her on a bad API call


def listen_for_wake(
    on_wake: Callable[[], None] | None = None,
    pause_when_locked: bool = True,
) -> Iterator[float]:
    """Yield a confidence score every time the wake word is heard. Runs forever.

    Pass `on_wake` for a callback, or iterate the generator — whichever suits.
    """
    model = _get_model()
    last_hit = 0.0
    with sd.InputStream(
        samplerate=SAMPLE_RATE, channels=1, dtype="int16", blocksize=CHUNK
    ) as stream:
        while True:
            if pause_when_locked and is_locked():
                # Stop scoring audio while the screen is locked. Poll cheaply
                # until it comes back, and forget anything heard mid-lock.
                time.sleep(2.0)
                model.reset()
                stream.read(stream.read_available or CHUNK)  # drop stale audio
                continue

            data, _overflowed = stream.read(CHUNK)
            scores = model.predict(data.flatten())
            best = max(scores.values()) if scores else 0.0
            now = time.time()
            if best > THRESHOLD and (now - last_hit) > COOLDOWN_SECONDS:
                last_hit = now
                model.reset()
                if on_wake:
                    on_wake()
                yield best


if __name__ == "__main__":
    print(f"[{WAKE_WORD}] threshold {THRESHOLD} — listening. Ctrl+C to stop.")
    print(f"locked right now: {is_locked()}")
    try:
        for score in listen_for_wake():
            print(f"  wake  score={score:.2f}  at {time.strftime('%H:%M:%S')}")
    except KeyboardInterrupt:
        print("stopped")
