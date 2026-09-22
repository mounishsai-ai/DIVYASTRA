# DIVYASTRA

A voice-driven AI assistant that runs on a normal Windows 11 laptop — **no GPU** —
and controls the real desktop. You say *"hey divya, open Spotify"*; it wakes on
the local CPU, transcribes locally, decides what to do, clicks the real thing,
and answers back in its own voice.

Built by a student as a learning project, with one rule above all others:
**measure before believing.** The most useful output of this repo is not the
assistant — it is the [decision log](docs/02-decisions.md) and
[findings](docs/07-screenshot-method.md), where several confident assumptions
were killed by real numbers and the retractions were left visible.

---

## The one result that matters

Opening an app through a naive GUI-agent loop took **238 seconds**. The same
task now takes **~1 second** once learned, and one model call (~6–30 s) the
first time.

The idea that got it there, in one line:

> **The model decides *what* to click. Windows says *where* it is.**

General vision models read a screen well and **point badly** — asked to locate an
icon in a 960×540 screenshot, Gemini returned a y-coordinate *outside the image*,
and on a retry missed by 24 px. So the model never supplies a coordinate. It
picks an item by number from a list; the exact pixel comes from Windows UI
Automation, which is free and exact. This is the same architecture
[browser-use](https://github.com/browser-use/browser-use) and Microsoft's
[UFO2](https://arxiv.org/abs/2504.14603) converged on — verified by reading their
code, not their READMEs.

---

## What works, and what doesn't

**Works, verified live:**
- **Voice loop, end to end** — wake → listen → think → speak, one continuous loop.
- **Custom wake word** — "hey divya", trained from scratch on a free Kaggle GPU,
  runs locally at ~4% of one CPU core. Idle costs nothing: no words, no tokens.
- **Local speech** — [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
  in, [Kokoro](https://github.com/hexgrad/kokoro) TTS out. Both on CPU, both free,
  audio never leaves the laptop.
- **Desktop control** — opening and switching apps, learned-then-free.

**In progress / not done (stated honestly):**
- **Multi-step tasks inside an app** — "play a specific song in Spotify" opens
  Spotify then can't yet reliably drive its search. Four bugs from that run are
  fixed but not re-tested.
- **Phone (Twilio), email, WhatsApp** — designed, not built.

This is roughly a third of the original vision — but the **hardest** third
(cheap, reliable desktop control on GPU-less hardware) is the part that works.

---

## Architecture

A **hub with swappable limbs.** Every capability is a small program speaking one
protocol (**MCP**). A local agent ([Hermes](https://github.com/NousResearch/Hermes))
is the hub — memory, scheduling, channels. The limbs are ours.

| Layer | Choice | Cost |
|---|---|---|
| Everyday brain | Gemini 3.8 Flash on Vertex (own GCP project) | ~cents/task |
| Desktop / browser control | [cua-driver](https://github.com/trycua) (UI Automation + CDP) | free |
| Voice out | Kokoro-82M, local CPU | free |
| Voice in | faster-whisper `base.en`, local CPU | free |
| Wake word | our own `hey_divya`, trained on Kaggle GPU | free |

**Hardware reality — the forcing function behind every decision:** Intel UHD
integrated graphics, 15.7 GB RAM, no NVIDIA GPU. No local LLM, no UI-TARS. The
brain is always in the cloud; only small audio models run locally. This
constraint is *why* the design is what it is — it's documented, not hidden.
(UI-TARS, the obvious "just use a pointing model" answer, was
[ruled out with a real 79-second-per-click measurement](docs/07-screenshot-method.md),
not an assumption.)

```
divyastra/
  voice/      wake word, speech-to-text, text-to-speech, persona, the always-on loop
  desktop/    the "model decides what, Windows says where" control loop
  brain/      Claude Code as an escalation brain (claude -p)
  config/     model routing, MCP setup
docs/         architecture, decisions (with reversals), roadmap, costs, findings
```

Every outside dependency sits behind **one adapter file**, so swapping a vendor
touches one place. Full picture in [docs/01-architecture.md](docs/01-architecture.md).

---

## The engineering, honestly

If you read one thing, read these two — they are the real work:

- **[docs/02-decisions.md](docs/02-decisions.md)** — what was chosen, what was
  rejected, and **four decisions reversed after measurement**, kept visible with
  the reasoning. Being wrong in public, on purpose.
- **[docs/07-screenshot-method.md](docs/07-screenshot-method.md)** — the cost and
  latency findings. Sample: *compression saves bytes, not tokens — you are billed
  for pixels, not file size.* And *nine configuration experiments changed nothing;
  two trace-reads cut a task 20×. Instrument first, tune second.*

---

## Running it

Windows 11. Each dependency has its own virtual environment (git-ignored).

```powershell
# the desktop control loop, standalone:
divyastra\desktop\loop.py "open spotify"

# the full voice assistant (needs a microphone):
divyastra\voice\.venv\Scripts\python.exe divyastra\voice\assistant.py --debug
```

`--debug` prints the mic/speaker in use and a live meter of what she is hearing.
Say **"hey divya"**, wait for *"Yes?"*, then talk.

---

## Status

Active learning project, built and measured across September 2026. Secrets live
in `.env` (never committed); the trained wake-word model is included, the audio
runtimes are downloaded on setup. Not production software — a working proof that a
laptop with no GPU can be talked to and can talk back.
