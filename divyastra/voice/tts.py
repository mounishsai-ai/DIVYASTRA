"""Turn text into DIVYASTRA's voice. The only file that knows which TTS engine we use.

Rule 4 of CLAUDE.md: every outside dependency sits behind one adapter file.
Swapping Kokoro for ElevenLabs, or changing the voice, should touch this file
and nothing else. `speak()` and `to_wav()` are the whole public surface.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf
from kokoro_onnx import Kokoro

# --- the voice ---------------------------------------------------------------
# Chosen by Mounish 2026-09-08 after auditioning all 15 English female voices.
# `af_` = American, `bf_` = British. Run `python -m divyastra.voice.tts --list`
# to hear the alternatives again.
VOICE = "af_jessica"
LANG = "en-gb" if VOICE.startswith("bf_") else "en-us"
SPEED = 1.0  # 0.8 = slower/calmer, 1.2 = brisker

# --- where the model lives ---------------------------------------------------
# Resolved relative to this file, never the working directory, so DIVYASTRA
# works no matter where it is launched from.
_HERE = Path(__file__).resolve().parent
_MODEL = _HERE / "models" / "kokoro-v1.0.onnx"
_VOICES = _HERE / "models" / "voices-v1.0.bin"

_engine: Kokoro | None = None


def _get_engine() -> Kokoro:
    """Load the model once and reuse it — loading costs ~1s, synthesis does not."""
    global _engine
    if _engine is None:
        if not _MODEL.exists() or not _VOICES.exists():
            raise FileNotFoundError(
                f"Kokoro model files missing under {_HERE / 'models'}.\n"
                "Download them (~340 MB, gitignored):\n"
                "  https://github.com/thewh1teagle/kokoro-onnx/releases/"
                "download/model-files-v1.1/kokoro-v1.0.onnx\n"
                "  https://github.com/thewh1teagle/kokoro-onnx/releases/"
                "download/model-files-v1.1/voices-v1.0.bin"
            )
        _engine = Kokoro(str(_MODEL), str(_VOICES))
    return _engine


def synthesize(text: str, voice: str = VOICE, speed: float = SPEED):
    """Return (audio, sample_rate) for `text`. No playback, no files."""
    lang = "en-gb" if voice.startswith("bf_") else "en-us"
    return _get_engine().create(text, voice=voice, speed=speed, lang=lang)


def speak(text: str, voice: str = VOICE, speed: float = SPEED, block: bool = True) -> None:
    """Say `text` out loud. This is the function the rest of DIVYASTRA calls."""
    audio, rate = synthesize(text, voice, speed)
    sd.play(np.asarray(audio), rate)
    if block:
        sd.wait()


def to_wav(text: str, path: str | Path, voice: str = VOICE, speed: float = SPEED) -> Path:
    """Write `text` to a wav file instead of the speakers — for voice notes later."""
    audio, rate = synthesize(text, voice, speed)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), audio, rate)
    return path


def voices() -> list[str]:
    """Every voice the model ships, for auditioning."""
    return sorted(_get_engine().get_voices())


if __name__ == "__main__":
    import sys

    if "--list" in sys.argv:
        for v in voices():
            print(v)
    else:
        line = " ".join(a for a in sys.argv[1:] if not a.startswith("--")) or (
            "Systems online. Good evening, Mounish."
        )
        print(f"[{VOICE} @ {SPEED}x] {line}")
        speak(line)
