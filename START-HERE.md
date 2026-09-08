# Start here

Last updated 2026-09-09. If you have been away, read this and nothing else.

---

## She works

DIVYASTRA is a working voice assistant. One continuous loop, verified live:

```
you: "hey jarvis"          -> wake fires locally.        free
her: "Yes?"                -> her own voice.             free
you: "what can you do?"    -> transcribed locally.       free
                           -> Hermes thinks (~10s).      about a cent
her: answers aloud                                        free
```

**To run her:**

```
divyastra\voice\.venv\Scripts\python.exe divyastra\voice\assistant.py
```

Models take ~20 s to load, then she says "Systems online." Say **"hey jarvis"**,
wait for "Yes?", then talk. Ctrl+C stops her.

**She is not started automatically.** That would mean an always-on microphone
listener at every logon, so it is your call, not an assumption. Say the word and
it is a five-minute job.

---

## The wake word: trained, built in, but NOT switched on yet

The Kaggle run finished. `hey_divya.onnx` is trained, committed, and wired into
`voice/wake.py` -- but **`hey_jarvis` is still the wake word**, on purpose.

**One command settles it, and it needs your voice:**

```
divyastra\voice\.venv\Scripts\python.exe divyastra\voice\wake.py --compare
```

It scores both models live, side by side. Say "hey jarvis" a few times, then
"hey divya" a few times, at your **normal speaking volume** -- then stay quiet a
minute so we can see what silence scores. Ctrl+C prints the peaks.

Then we pick a threshold below your quietest "hey divya" and above whatever
ordinary talking reached, put it in `THRESHOLDS`, and change one line.

**Why I did not just switch it over.** The training report looks excellent --
89% recall at 0.17 false wakes an hour. In its own test set it is excellent: of
232 negative clips, *zero* scored above 0.5. But two things are true that the
report does not show:

- That 0.17/hour is measured one clip at a time, at the one perfect alignment.
  A real listener scores every 80 ms and gets far more chances to fire, so the
  real number will be worse.
- The model is **very sensitive to alignment**. "Can you open the calculator"
  scores 0.006 at the clean alignment and **0.879** when I slide it past every
  offset. Same audio. Against phrases like "hey diana" it stops discriminating
  altogether.

- On a real microphone it never fully goes quiet: it idles around 0.15-0.21 in
  a silent room and ambient noise alone reached 0.54, where "hey jarvis" reads
  0.000. So the compare tool measures your room's floor first.

None of that is a flaw in the code I wrote -- I checked it by sliding livekit's
own scorer over the same audio and getting the same collapse (0.934 for "hey
divya" against 0.939 for "hey diana"). It is the model's behaviour, reproduced
faithfully.

But every one of those numbers came from synthetic speech, which is no more like
your voice than the synthetic speech it trained on. So it is a reason to test,
not a reason to reject. **Your voice is the only test that counts.**

If it does not work out, `hey_jarvis` keeps working and nothing is blocked. The
detector, the threshold table and the compare tool all stay useful either way.

**Expire the Kaggle token** -- the model is downloaded and committed, so it has
done its job.

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

**The wake word is still "hey jarvis".** A trained "hey divya" model now
exists and is wired in -- it just needs one minute of your voice to choose a
threshold. See the section above.

---

## Where to look

- **[CLAUDE.md](CLAUDE.md)** — the rules and current phase. Deliberately short.
- **[docs/03-roadmap.md](docs/03-roadmap.md)** — phases and their pass/fail tests.
- **[docs/02-decisions.md](docs/02-decisions.md)** — what was chosen, what was
  rejected, and the four decisions that had to be reversed after measurement.
- **[docs/00-glossary.md](docs/00-glossary.md)** — plain English, if a word here
  was unfamiliar.

Every step is a separate commit with its reasoning. `git log` is the story.
