"""Turn speech into text. The only file that knows which STT engine we use.

Mirror of tts.py, per rule 4 of CLAUDE.md. `listen()` and `transcribe()` are the
whole public surface — swapping faster-whisper for whisper.cpp, Deepgram, or
anything else should touch this file and nothing else.

Everything here runs locally on the CPU. Microphone audio never leaves the
laptop and costs nothing per use.
"""

from __future__ import annotations

import queue
import time
from pathlib import Path

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

# --- the model ---------------------------------------------------------------
# "base.en" is the speed/accuracy sweet spot on a CPU for short English commands.
# "small.en" is noticeably better on accents and noise but ~3x slower.
MODEL_SIZE = "base.en"
COMPUTE = "int8"  # int8 is the CPU-friendly quantisation; float32 is slower

# --- listening behaviour -----------------------------------------------------
SAMPLE_RATE = 16000  # what Whisper expects; sounddevice resamples for us
SILENCE_RMS = 0.012  # below this counts as silence — raise it in a noisy room
SILENCE_SECONDS = 1.2  # how long a pause must be before she stops listening
MAX_SECONDS = 30.0  # hard ceiling so a stuck mic cannot record forever
MIN_SPEECH_SECONDS = 0.4  # ignore a cough or a door slam

_HERE = Path(__file__).resolve().parent
_CACHE = _HERE / "models" / "whisper"

_model: WhisperModel | None = None


def _get_model() -> WhisperModel:
    """Load once and reuse — loading costs seconds, transcribing does not."""
    global _model
    if _model is None:
        _CACHE.mkdir(parents=True, exist_ok=True)
        _model = WhisperModel(
            MODEL_SIZE, device="cpu", compute_type=COMPUTE, download_root=str(_CACHE)
        )
    return _model


def _rms(block: np.ndarray) -> float:
    """Loudness of one chunk of audio, 0.0 = silence."""
    return float(np.sqrt(np.mean(np.square(block))))


def record_until_silence(
    max_seconds: float = MAX_SECONDS, silence_seconds: float = SILENCE_SECONDS
) -> np.ndarray:
    """Record from the mic until the speaker stops. Returns mono float32 audio."""
    chunks: list[np.ndarray] = []
    q: queue.Queue = queue.Queue()
    block = int(SAMPLE_RATE * 0.05)  # 50 ms blocks

    def cb(indata, _frames, _t, _status):
        q.put(indata.copy())

    started = time.time()
    last_sound = None
    heard_anything = False

    with sd.InputStream(
        samplerate=SAMPLE_RATE, channels=1, dtype="float32", blocksize=block, callback=cb
    ):
        while True:
            try:
                data = q.get(timeout=0.5)
            except queue.Empty:
                if time.time() - started > max_seconds:
                    break
                continue
            chunks.append(data)
            loud = _rms(data) > SILENCE_RMS
            now = time.time()
            if loud:
                heard_anything = True
                last_sound = now
            # stop once there has been speech followed by a long enough pause
            if heard_anything and last_sound and (now - last_sound) > silence_seconds:
                break
            if now - started > max_seconds:
                break

    if not chunks:
        return np.zeros(0, dtype=np.float32)
    return np.concatenate(chunks, axis=0).flatten().astype(np.float32)


# Whisper HALLUCINATES on noise. Measured 2026-09-09: a false wake on an empty
# room produced "Carver, turn around, change your game." out of nothing. That is
# not harmless - non-empty text goes to the brain, costs a real API call, and
# makes her answer out loud for no reason. The "a false wake costs nothing"
# assumption held only while the brain was broken.
#
# So trust the model's own confidence rather than guessing from the text.
# faster-whisper reports both per segment:
MAX_NO_SPEECH_PROB = 0.60  # its own estimate that the audio is not speech
MIN_AVG_LOGPROB = -1.00  # how confident it is in the words it chose


def transcribe_audio(audio: np.ndarray) -> str:
    """Text for a mono 16 kHz float32 array. Empty string if nothing intelligible."""
    if audio.size < int(SAMPLE_RATE * MIN_SPEECH_SECONDS):
        return ""
    segments, _info = _get_model().transcribe(
        audio, language="en", vad_filter=True, beam_size=1
    )
    return _join_confident(segments)


def _join_confident(segments) -> str:
    """Keep only segments the model itself believes are speech."""
    kept = []
    for s in segments:
        no_speech = getattr(s, "no_speech_prob", 0.0)
        logprob = getattr(s, "avg_logprob", 0.0)
        if no_speech > MAX_NO_SPEECH_PROB or logprob < MIN_AVG_LOGPROB:
            print(
                f"  (discarded '{s.text.strip()[:40]}' - "
                f"no_speech={no_speech:.2f} logprob={logprob:.2f})"
            )
            continue
        kept.append(s.text.strip())
    return " ".join(kept).strip()


def transcribe(path: str | Path) -> str:
    """Text for an audio file — used later for voice notes arriving from a phone."""
    segments, _info = _get_model().transcribe(
        str(path), language="en", vad_filter=True, beam_size=1
    )
    return _join_confident(segments)


def listen(max_seconds: float = MAX_SECONDS) -> str:
    """Record until you stop talking, then return what you said.

    This is the function the rest of DIVYASTRA calls.
    """
    return transcribe_audio(record_until_silence(max_seconds=max_seconds))


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        print(transcribe(sys.argv[1]))
    else:
        print(f"[{MODEL_SIZE}/{COMPUTE}] loading...")
        _get_model()
        print("speak now (stops after a pause)...")
        t0 = time.time()
        text = listen()
        print(f"\n  heard: {text!r}")
        print(f"  took : {time.time() - t0:.1f}s")
