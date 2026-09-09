# Start here

Last updated 2026-09-09. If you have been away, read this and nothing else.

---

## She works

DIVYASTRA is a working voice assistant. One continuous loop, verified live:

```
you: "hey divya"           -> wake fires locally.        free
her: "Yes?"                -> her own voice.             free
you: "what can you do?"    -> transcribed locally.       free
                           -> Hermes thinks (~10s).      about a cent
her: answers aloud                                        free
```

**To run her:**

```
divyastra\voice\.venv\Scripts\python.exe divyastra\voice\assistant.py
```

Models take ~20 s to load, then she says "Systems online." Say **"hey divya"**,
wait for "Yes?", then talk. Ctrl+C stops her.

**She is not started automatically.** That would mean an always-on microphone
listener at every logon, so it is your call, not an assumption. Say the word and
it is a five-minute job.

---

## Fixed: Windows was blocking her brain

**Smart App Control had switched itself on** and was blocking every Hermes
binary (`WinError 4551`). It ships in an "evaluation" mode that flips to
enforcing without asking, which is why she worked one day and not the next.

You turned it off on 2026-09-09 and restarted. Verified: policy state is now 0,
`hermes.exe` runs, and she answers again. **That setting cannot be turned back
on without reinstalling Windows** - you still have normal Defender protection,
which is what nearly every Windows PC runs.

**If she ever goes silent again, check this first:**

```
(Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\CI\Policy').VerifiedAndReputablePolicyState
```

0 is off and correct. And run her with `--debug`, which prints the mic and
speaker she is using plus a live meter of what she is hearing.

**The other half of that day's confusion:** her voice goes to the SYSTEM
DEFAULT speaker, which on this laptop is the Boult Bluetooth headset. Paired
but not on your head sounds exactly like a crash. She now prints which speaker
she is using at startup.

---

## Where we got to on 9 Sep (desktop control)

**She can drive the desktop now, and it is ~40x faster than it was.**
`divyastra/desktop/` - run it by hand:

```
divyastraoice\.venv\Scripts\python.exe divyastra\desktop\loop.py "open spotify"
```

| | time |
|---|---|
| old GUI agent loop | 238 s |
| new, first time | 6-30 s (one model call) |
| new, once learned | **~1 s, no model call, free** |

The idea in one line: **the model decides WHAT to click, Windows says WHERE.**
Vision models read screens well and point badly (Gemini answered y=971 for a
540px-tall image), so it picks a number from a list and the coordinates come
from UI Automation.

**Works:** opening and switching to apps. **Not finished:** multi-step jobs
inside an app - "play Shape of You in Spotify" got Spotify open then could not
find the search box. Four bugs from that run are fixed; it has NOT been re-run.

**Not wired into her voice yet** - deliberately. It runs from the command line
only until it is trusted.

Also settled: UI-TARS is ruled out on this laptop (79 s to prefill one
screenshot). Full numbers in [docs/07](docs/07-screenshot-method.md).

---

## Her name is "hey divya"

She answers to her own name now. You tested it with `--compare` on your own
voice across two sessions and picked **0.5**, which is what ships.

```
you: "hey divya"  ->  "Yes?"  ->  talk
```

The model was trained on Kaggle's GPU and lives at
`voice/models/hey_divya.onnx` (161 KB, committed). It is not openWakeWord's -
it needed its own streaming detector, because openWakeWord assembles the audio
features differently and loading it there made it fire on everything.

**If she starts waking on nothing**, the room is tripping her: this model idles
around 0.15-0.21 in silence and noise alone hit 0.54 in my test. Raise
`THRESHOLDS["hey_divya"]` in `voice/wake.py`. **If she misses you**, lower it.
One number, and `--compare` shows you what your voice actually scores.

`hey_jarvis` is still there and still works - `WAKE_WORD = "hey_jarvis"` puts
it back, no other change needed.

---

## What everything costs

| State | Cost |
|---|---|
| Waiting for the wake word | **nothing** — 7.1% of one core, no network |
| Woken, but you said nothing | **nothing** — no speech, no model call |
| A spoken question | ~$0.01 |
| A desktop task (clicking things) | **$0.12 – $0.47**, 2.5–8 minutes |

The voice half is free and fast forever, because it runs on your CPU and never
leaves the laptop. The *thinking* half is the only thing that costs.

**~$290 of Google Cloud credit left, expiring around 6 Dec 2026.** A budget
alert exists that actually tracks credit burn (your two original ones would have
stayed silent until the credit was gone).

---

## The hard lesson from the cost work

**A desktop task costs what it costs.** Nine attempts to make it cheaper: one
worked (batching clicks, 21–39 calls down to a fixed 14), and **none made it
faster**. About 5 seconds per UI action is network plus inference latency, not
something to tune away.

So the rule that came out of it:

| Approach | Cost | Use when |
|---|---|---|
| An API / CLI / script | **~$0** | Whenever one exists. Gmail has an API — don't click Gmail. |
| Desktop control | $0.12+ | Native app, no other way in |
| Browser control | $0.37 | Web page, no API |

**The GUI is the last resort, not the default.** Anything you do daily should
become code, where it costs nothing. That is what `capabilities/` is for, and it
is the most valuable thing left to build.

Full working in [docs/06-phase1-hermes.md](docs/06-phase1-hermes.md).

---

## Things running on your laptop now

- **`cua-driver-serve`** — desktop control daemon, starts at logon. Now carries
  `--grant existing-profile` (you ran the admin command).
- **Chrome `Profile 8`** has remote debugging enabled and you granted consent.
  Revocable in Chrome settings.
- **Hermes** in `%LOCALAPPDATA%\hermes` — its own Python, Node, ffmpeg.
- **A service-account key** at `%LOCALAPPDATA%\hermes\divyastra-vertex-key.json`.
  Revoke command is in [docs/06-phase1-hermes.md](docs/06-phase1-hermes.md).

---

## Two open items

**Phase 1c — a privacy bug, not cosmetic.** The browser limb binds to *whatever
Chrome is running*, so the deliberate choice of `Profile 8` is documented but
unenforced. This laptop has nine Chrome profiles, most belonging to other
people. **Fix before any unattended browser use.**

**The wake word is "hey divya".** Trained, tested on his voice, live at
threshold 0.5.

---

## Where to look

- **[CLAUDE.md](CLAUDE.md)** — the rules and current phase. Deliberately short.
- **[docs/03-roadmap.md](docs/03-roadmap.md)** — phases and their pass/fail tests.
- **[docs/02-decisions.md](docs/02-decisions.md)** — what was chosen, what was
  rejected, and the four decisions that had to be reversed after measurement.
- **[docs/00-glossary.md](docs/00-glossary.md)** — plain English, if a word here
  was unfamiliar.

Every step is a separate commit with its reasoning. `git log` is the story.
