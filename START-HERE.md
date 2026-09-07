# Good morning — read this first

Written 2026-09-08 while you slept. Two minutes of reading, then one 2-minute
task and DIVYASTRA thinks for the first time.

---

## Where we got to

**Phase 0 is done. Phase 1 is one API key away from done.**

DIVYASTRA can already control your laptop. That is proven, not theoretical:

- **Desktop** — launched Calculator, read its buttons *by name* from Windows'
  accessibility tree, clicked `7 × 6 =`, read back `42`. Your real mouse never
  moved.
- **Browser** — opened Wikipedia in your actual logged-in Chrome and read out
  today's featured article. No Playwright needed; it turned out `cua-driver`
  does browsers too.

**Hermes** (the brain that will run all this without Claude Code) is installed
and pointed at Gemini Flash, with `cua-driver` already plugged into it.

---

## Your one task (2 minutes)

Hermes has no API key, so it can't think yet.

1. Open **[aistudio.google.com/apikey](https://aistudio.google.com/apikey)**
2. Create a key — the **free tier is fine** and is deliberately our default
3. Add one line to `%LOCALAPPDATA%\hermes\.env`:

```
GEMINI_API_KEY=paste-your-key-here
```

Don't paste the key into chat or into this project folder. That `.env` lives in
the Hermes directory, outside the repo, which is where it belongs.

Then tell me and I'll run the Phase 1 test: the same Calculator task, but
driven by Hermes instead of by me.

---

## Three things you should know

**1. Your laptop changed in ways you should be aware of.**
- `cua-driver-serve` now starts at every login (a background process that *can*
  synthesise input, though it does nothing until something connects to it).
- **Chrome `Profile 8` now has remote debugging permanently enabled.** That's
  how the browser attach works, but it means local processes can drive that
  profile.
- Hermes installed its own Python and Node (a few hundred MB). Your system
  Node 24 was left untouched.

All three are reversible, and all three are written down in
[docs/05-phase0-findings.md](docs/05-phase0-findings.md) and
[docs/06-phase1-hermes.md](docs/06-phase1-hermes.md) with the undo commands.

**2. A near-miss worth one sentence.**
When I first tested Notepad, it opened your existing window titled
`*so my clg conduting project exhibit` — the `*` means unsaved work. The next
step would have typed into your coursework notes. I switched to Calculator.
There's now a written rule: read the window title before acting, never type
into a `*`.

**3. Hermes has no spend cap.**
It has step limits and loop-failure limits, but nothing that stops it spending
money. Harmless while we're on the free tier — but a Google Cloud budget alert
has to exist before you ever turn billing on. It's in the roadmap so it can't
be quietly forgotten.

---

## Two things I got wrong, and you were right

**Hermes.** I rejected it as "server-shaped, needs a VPS." You told me to check
the June 2026 release. You were right — it runs entirely locally, Telegram
needs no public URL, and it already implements the hub, scheduler and channels
I'd planned to build by hand. That reversal saved weeks. The wrong reasoning is
kept visible in [docs/02-decisions.md](docs/02-decisions.md) rather than quietly
deleted.

**"Prefer boring tools."** You cut that line. Today proved you right twice:
`cua-driver` and Hermes are both months old and both were the correct choice.

---

## What's next, in order

| Phase | What | Blocked on |
|---|---|---|
| **1** | Hermes runs a desktop task | **your API key** |
| 2 | Telegram — task from class, done at home | a BotFather token + your user ID |
| 3 | FRIDAY's voice (Kokoro + whisper.cpp) | nothing |
| 4 | Twilio — it actually rings your phone | a Twilio trial |

Phase 2 is the one you actually described wanting. It's close.

---

## Where things live

- **[CLAUDE.md](CLAUDE.md)** — the rules and the current phase. Short on purpose.
- **[docs/00-glossary.md](docs/00-glossary.md)** — plain-English terms. Start here
  if any word above was unfamiliar.
- **[docs/02-decisions.md](docs/02-decisions.md)** — what we chose and what we
  rejected, with reasons.
- **[docs/03-roadmap.md](docs/03-roadmap.md)** — phases and their pass/fail tests.
- **[docs/05-phase0-findings.md](docs/05-phase0-findings.md)** — everything that
  tripped us up on your machine, with fixes.
- **[docs/06-phase1-hermes.md](docs/06-phase1-hermes.md)** — the Hermes setup.

Nothing is half-finished. Every change is committed, the tree is clean, and you
can `git log` to see exactly what happened and why.
