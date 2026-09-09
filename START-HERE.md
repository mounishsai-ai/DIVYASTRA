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

## BROKEN RIGHT NOW: Windows is blocking Hermes

**Smart App Control switched itself on and is blocking her brain.** This is why
nothing happens when you talk to her.

```
[WinError 4551] An Application Control policy has blocked this file
```

Every Hermes binary is blocked -- `hermes.exe`, and its bundled Python too.
Verified: `VerifiedAndReputablePolicyState = 1` (enforcing) and `hermes.exe` is
unsigned. Smart App Control ships in an "evaluation" mode that flips itself to
enforcing without asking, which is why this worked yesterday and not today.

**Not affected:** cua-driver (still running), our own Python, voice, wake word,
Claude Code. Only Hermes.

There is no exclusion list for Smart App Control, and self-signing does not
satisfy it. So there are two real ways out, and the choice is yours:

1. **Turn Smart App Control off.** Windows Security -> App & browser control ->
   Smart App Control -> Off. **This is one-way: it cannot be switched back on
   without resetting or reinstalling Windows.** Everything works again
   immediately.
2. **Stop depending on Hermes binaries.** Call Vertex/Gemini straight from our
   own Python, which Windows is happy to run. Keeps the security setting on.
   Costs the same per question. Loses what Hermes gave us for free: persistent
   memory, cron, and the channel gateways for phone access later.

`brain/claude_cli.py` already works today and needs no decision, but it is the
expensive brain -- about eleven times Gemini per question, out of the $20/month
credit.

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
