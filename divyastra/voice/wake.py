"""Listen for the wake word, and only then wake anything expensive.

The only file that knows which wake-word engine we use (rule 4).

This is what makes "idle costs nothing" literally true: a ~1 MB model scores
80 ms of audio at a time, entirely on the CPU. No network, no model calls, no
money -- until you actually say her name.

It also **pauses while the laptop is locked**. A logon-started process keeps
running when you lock the screen, so without this it would sit listening to the
microphone on the lock screen. It does not.

TWO ENGINES LIVE HERE, chosen by WAKE_WORD:

  "hey_jarvis"  -> openWakeWord's pretrained model.  DEFAULT, proven, in use.
  "hey_divya"   -> our own model, trained on Kaggle. See _LivekitDetector.

They are not interchangeable at the file level even though both are ONNX and
both take a [batch, 16, 96] embedding tensor. Measured 2026-09-09: loading our
model through openWakeWord's `Model()` makes it fire on *everything* (0.94 on
"hey jarvis", 0.86 on "what is the weather today"), because openWakeWord and
livekit-wakeword assemble the embedding sequence differently. The mel and
embedding ONNX files are byte-identical between the two packages (same md5);
only the windowing differs. Hence a separate detector rather than a path swap.
"""

from __future__ import annotations

import ctypes
import time
from collections import deque
from pathlib import Path
from typing import Callable, Iterator

import numpy as np

_HERE = Path(__file__).resolve().parent
_MODELS = _HERE / "models"

# --- the wake word -----------------------------------------------------------
# Pretrained options that ship with openWakeWord: alexa, hey_jarvis, hey_mycroft,
# hey_rhasspy. Our own "hey_divya" is the other option -- see below for why it
# is not yet the default.
WAKE_WORD = "hey_jarvis"

# Per-engine thresholds. They are NOT on the same scale, so they cannot share a
# constant: openWakeWord's hey_jarvis and our livekit model score differently
# on identical audio.
THRESHOLDS = {
    "hey_jarvis": 0.25,
    # Placeholder ONLY -- must be measured on Mounish's real voice before use.
    # eval.json's "optimal_threshold" is 0.88, but that was found against piper
    # synthetic speech, and this project has already been bitten once by taking
    # a synthetic number at face value. Run `python wake.py --compare`.
    "hey_divya": 0.70,
}
# Measured on Mounish's voice, 2026-09-08 (hey_jarvis):
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
CHUNK = 1280  # 80 ms -- the frame size both engines expect

# NOTE: openWakeWord's pretrained models are CC-BY-NC-SA 4.0 (non-commercial).
# Fine for personal use; retrain or replace before distributing DIVYASTRA.
# Our own hey_divya model carries no such restriction.


def threshold() -> float:
    """The firing threshold for whichever engine is selected."""
    return THRESHOLDS.get(WAKE_WORD, 0.5)


# --- engine 2: our own model -------------------------------------------------


class _LivekitDetector:
    """Streaming detector for a livekit-wakeword classifier.

    livekit ships a *stateless* API: hand it 2 seconds of audio, get one score.
    That is wrong for an always-on listener, which must score continuously. So
    this reproduces the same maths incrementally.

    The pipeline is three ONNX models in series:
        audio -> melspectrogram.onnx -> (/10 + 2) -> embedding.onnx -> classifier
    Every 80 ms of audio produces exactly 8 new mel frames, which is exactly one
    new 96-d embedding (window 76, stride 8). We keep the last 16 embeddings and
    run only the classifier each frame, rather than redoing all 16.

    Needs only numpy + onnxruntime, both already in voice/.venv.
    """

    EMB_WINDOW = 76  # mel frames per embedding
    EMB_STRIDE = 8  # mel frames between embeddings == 80 ms
    N_EMB = 16  # embeddings the classifier expects
    _MEL_AUDIO = 24000  # 1.5 s of audio is ample to yield the last 76 mel frames
    _EDGE_TRIM = 2  # drop mel frames touched by right-edge padding

    def __init__(self, classifier: Path):
        import onnxruntime as ort

        mel_path, emb_path = _preprocessor_paths()
        opts = ort.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 1
        mk = lambda p: ort.InferenceSession(
            str(p), sess_options=opts, providers=["CPUExecutionProvider"]
        )
        self._mel, self._emb, self._clf = mk(mel_path), mk(emb_path), mk(classifier)
        self._mel_in = self._mel.get_inputs()[0].name
        self._emb_in = self._emb.get_inputs()[0].name
        self._clf_in = self._clf.get_inputs()[0].name

        self._audio = np.zeros(self._MEL_AUDIO, dtype=np.float32)
        self._embs: deque[np.ndarray] = deque(maxlen=self.N_EMB)

    def reset(self) -> None:
        self._audio[:] = 0.0
        self._embs.clear()

    def _melspec(self, audio: np.ndarray) -> np.ndarray:
        out = self._mel.run(None, {self._mel_in: audio[np.newaxis, :]})[0]
        if out.ndim == 4:  # (batch, 1, frames, 32)
            out = out[:, 0, :, :]
        return out[0] / 10.0 + 2.0  # openWakeWord's melspec_transform

    def predict(self, frame: np.ndarray) -> float:
        """Feed one 80 ms frame (int16 or float32); get the current score."""
        if frame.dtype == np.int16:
            frame = frame.astype(np.float32) / 32768.0
        frame = frame.flatten().astype(np.float32)

        self._audio = np.concatenate([self._audio[len(frame) :], frame])

        mel = self._melspec(self._audio)
        end = len(mel) - self._EDGE_TRIM
        if end < self.EMB_WINDOW:
            return 0.0
        window = mel[end - self.EMB_WINDOW : end]  # (76, 32)
        emb = self._emb.run(None, {self._emb_in: window[np.newaxis, :, :, np.newaxis]})[0]
        self._embs.append(np.asarray(emb).reshape(-1))  # (96,)

        if len(self._embs) < self.N_EMB:
            return 0.0
        seq = np.stack(self._embs, axis=0)[np.newaxis, :, :].astype(np.float32)
        return float(self._clf.run(None, {self._clf_in: seq})[0][0, 0])


def _preprocessor_paths() -> tuple[Path, Path]:
    """Find melspectrogram.onnx and embedding_model.onnx.

    openWakeWord and livekit-wakeword ship byte-identical copies (verified by
    md5), so whichever package is installed will do.
    """
    for pkg, sub in (
        ("openwakeword", ("resources", "models")),
        ("livekit.wakeword", ("resources",)),
    ):
        try:
            mod = __import__(pkg, fromlist=["__file__"])
            base = Path(mod.__file__).resolve().parent.joinpath(*sub)
            mel, emb = base / "melspectrogram.onnx", base / "embedding_model.onnx"
            if mel.exists() and emb.exists():
                return mel, emb
        except Exception:
            continue
    raise FileNotFoundError(
        "No melspectrogram.onnx / embedding_model.onnx found. Install "
        "openwakeword or livekit-wakeword into this environment."
    )


# --- one interface over both engines -----------------------------------------

_engine = None
_engine_for: str | None = None


def _get_engine(word: str | None = None):
    """Load (once) whichever engine WAKE_WORD names."""
    global _engine, _engine_for
    word = word or WAKE_WORD
    if _engine is not None and _engine_for == word:
        return _engine

    custom = _MODELS / f"{word}.onnx"
    if custom.exists():
        _engine = _LivekitDetector(custom)
    else:
        from openwakeword.model import Model

        inner = Model(wakeword_models=[word], inference_framework="onnx")

        class _OWW:  # same two methods, so callers never branch
            def predict(self, frame):
                s = inner.predict(frame)
                return max(s.values()) if s else 0.0

            def reset(self):
                inner.reset()

        _engine = _OWW()
    _engine_for = word
    return _engine


def load():
    """Load the wake engine now, so the first spoken word is not missed.

    Callers use this to pay the model-loading cost at startup rather than on
    the first frame of audio.
    """
    return _get_engine()


def is_locked() -> bool:
    """True when the Windows session is locked (or the screensaver is up).

    Checked by asking whether the input desktop can be opened -- when the machine
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

    Pass `on_wake` for a callback, or iterate the generator -- whichever suits.
    """
    import sounddevice as sd  # imported here so offline scoring can use this file

    model = _get_engine()
    thresh = threshold()
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
            best = model.predict(data.flatten())
            now = time.time()
            if best > thresh and (now - last_hit) > COOLDOWN_SECONDS:
                last_hit = now
                model.reset()
                if on_wake:
                    on_wake()
                yield best


def _compare() -> None:
    """Score both engines live, side by side, so a threshold can be chosen.

    This is the only way to settle which model to ship: every number measured so
    far came from synthetic speech, and synthetic thresholds have already misled
    this project once.
    """
    import sounddevice as sd

    # Both engines are held at once, so _get_engine's single-engine cache is no
    # use here; build them directly.
    engines: list[list] = []
    for word in ("hey_jarvis", "hey_divya"):
        custom = _MODELS / f"{word}.onnx"
        try:
            if custom.exists():
                engine = _LivekitDetector(custom)
            else:
                from openwakeword.model import Model

                engine = Model(wakeword_models=[word], inference_framework="onnx")
        except Exception as exc:
            print(f"  ({word} unavailable: {exc})")
            continue
        engines.append([word, engine, THRESHOLDS.get(word, 0.5), 0.0])

    print("\n  Say 'hey jarvis' a few times, then 'hey divya' a few times.")
    print("  Speak at your NORMAL volume - not projected. Then stay quiet a")
    print("  minute so we can see what silence and ordinary noise score.")
    print("  Ctrl+C when done.\n")
    print(f"  {'hey_jarvis':>12}  {'hey_divya':>12}")

    peaks = {e[0]: 0.0 for e in engines}
    try:
        with sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1, dtype="int16", blocksize=CHUNK
        ) as stream:
            while True:
                data, _ = stream.read(CHUNK)
                frame = data.flatten()
                row = []
                for e in engines:
                    if isinstance(e[1], _LivekitDetector):
                        s = e[1].predict(frame)
                    else:
                        d = e[1].predict(frame)
                        s = max(d.values()) if d else 0.0
                    e[3] = s
                    peaks[e[0]] = max(peaks[e[0]], s)
                    row.append(s)
                if max(row) > 0.15:  # only print when something is happening
                    cells = "  ".join(
                        f"{s:>12.3f}{'*' if s > e[2] else ' '}" for s, e in zip(row, engines)
                    )
                    print(f"  {cells}")
    except KeyboardInterrupt:
        print("\n  peak scores this session:")
        for name, p in peaks.items():
            print(f"    {name:<12} {p:.3f}")
        print("\n  Pick a threshold BELOW your lowest 'hey divya' peak, and")
        print("  ABOVE anything ordinary speech reached. Put it in THRESHOLDS.")


if __name__ == "__main__":
    import sys

    if "--compare" in sys.argv:
        _compare()
        raise SystemExit(0)

    print(f"[{WAKE_WORD}] threshold {threshold()} -- listening. Ctrl+C to stop.")
    print(f"locked right now: {is_locked()}")
    try:
        for score in listen_for_wake():
            print(f"  wake  score={score:.2f}  at {time.strftime('%H:%M:%S')}")
    except KeyboardInterrupt:
        print("stopped")
