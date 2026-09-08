# DIVYASTRA

A personal AI assistant that runs on my Windows 11 laptop. I give it a task
(by voice, or from my phone), it does the work on the real desktop, and it
reports back in its own voice.

Owner: Mounish (student, learning as this is built — explain, don't assume).
Started: 2026-09-07

**Accounts** (they are different — don't mix them up):
- `mounishsai.ai@gmail.com` — professional, linked to GitHub. Git commits use this.
- `mounishsai71@gmail.com` — personal, no GitHub.
- Decide per-limb which mailbox DIVYASTRA is allowed to touch. Default: ask first.

---

## The one-paragraph version

DIVYASTRA is a **hub with swappable limbs**. Every capability (control the
desktop, drive the browser, read mail) is a **separate small program** that
speaks one shared protocol called **MCP**. A small **core** receives tasks from
**channels** (phone, voice, hotkey, timer), decides which model should think
about it, and lets that model call the limbs. Nothing in the core knows *how*
the desktop is clicked — it only knows a limb exists that can click.

**Returning after a break? Read [START-HERE.md](START-HERE.md) first.**

New to these words? Read [docs/00-glossary.md](docs/00-glossary.md).
Full picture: [docs/01-architecture.md](docs/01-architecture.md).

---

## THE RULES (this is the anti-tangle contract)

The stated risk on this project is getting lost in tangles. These rules exist
to make that structurally impossible. Do not break them for convenience.

1. **One capability = one MCP server = one folder = one job.**
   If a folder does two things, split it. No exceptions.

2. **A capability is not "done" until it works from Claude Code's own MCP
   client.** Wire it into `.mcp.json`, drive it by hand, prove it works. Only
   then may DIVYASTRA's own code call it. This means every limb is tested
   before it is integrated — never both at once.

3. **Build only what the current phase asks for.** The phase is named below.
   Ideas for later phases go to [docs/03-roadmap.md](docs/03-roadmap.md), not
   into the code.

4. **Every outside dependency sits behind one adapter file.** Model providers,
   TTS, STT, channels. Swapping ElevenLabs for Kokoro should touch one file.
   Assume every vendor choice here will be wrong within a year.

5. **If a file's job can't be said in one sentence, it's doing too much.**

6. **Commit at every green step.** Version control is the untangle button.
   A working state you can return to is worth more than a clever abstraction.

7. **Secrets live in `.env`, never in code, never in git.**

---

## Current phase

> **Phase 2 — FRIDAY's voice.** *(in progress)*
>
> Phases 0, 1 and 1b are done. Desktop control works and is tuned; the cost
> question is settled and written up in
> [docs/06-phase1-hermes.md](docs/06-phase1-hermes.md).
>
> - [x] **Kokoro-82M installed** — local, CPU-only, no GPU, no network, no cost.
> - [x] **Voice chosen: `af_jessica`**, after auditioning all 15 English female
>       voices on a long realistic status line.
> - [x] **`divyastra/voice/tts.py`** — the TTS adapter. `speak(text)` is the
>       whole surface. Model load 1.3 s once; synthesis **3.2x faster than real
>       time**.
> - [ ] `voice/stt.py` — whisper.cpp, listening.
> - [ ] Wake word on "Divyastra" (openWakeWord).
> - [ ] `SOUL.md` — who she is, separate from what she sounds like.
>
> **Voice is the first fast thing in this project.** Everything else waits on a
> cloud model; this does not.
>
> Open, not blocking: **Phase 1c** — the browser limb binds to whatever Chrome
> is running instead of enforcing `Profile 8`. Privacy bug, must be fixed before
> unattended browser use.

---

## The stack (decided — see docs/02-decisions.md for why)

| Layer | Choice | Cost |
|---|---|---|
| Spine (hub, memory, cron, channels) | **Hermes Agent** (MIT, local mode) | free |
| Desktop control | **cua-driver** 0.24.0 — installed & verified | free |
| Browser control | **cua-driver `browser_*` tools** (CDP) | free |
| Mail | **Gmail MCP server** + Google OAuth | free |
| Everyday brain | **Gemini 3.8 Flash on Vertex** (own GCP project) | ~$0.12/task batched |
| Hard-task brain | **Claude Sonnet via Agent SDK** | $20/mo credit incl. in Pro |
| Voice out (FRIDAY) | **Kokoro-82M**, voice `af_jessica`, local CPU | free |
| Voice in | **whisper.cpp** local CPU | free |
| Wake word | **openWakeWord** | free (non-commercial models) |
| Phone channel | **WhatsApp** (later) + **Twilio** (real calls) | free / ~$2/mo |
| Telegram | **dropped** — WhatsApp is the only messaging channel | — |
| Custom limbs | our own MCP servers | free |

**Hardware reality:** Intel UHD integrated graphics, 15.7 GB RAM, no NVIDIA
GPU. This is load-bearing. No local LLM, no UI-TARS, no OmniParser. The brain
is always in the cloud; only small audio models run locally.

---

## Layout

```
divyastra/
  capabilities/  our own MCP servers (third-party ones are just config)
  voice/         FRIDAY: wake word, speech-to-text, text-to-speech, persona
  config/        Hermes config, gateway setup, model routing
  docs/          architecture, decisions, roadmap, costs, findings
  .mcp.json      which MCP servers exist  (committed)
  .env           secrets                  (never committed)

Note: core/ and channels/ are gone — Hermes provides the hub, the
scheduler and the channels. We write limbs and personality, not plumbing.
```

---

## Working agreement with Claude Code

- I am a student, not an experienced developer. Explain the *why* in plain
  words before the *how*. Never assume I know a framework or a pattern.
- Show me the whole picture before changing a part of it.
- When there's a choice, give me a recommendation and the tradeoff — not a
  menu of five options.
- Tell me plainly when something won't work, is against a service's rules, or
  costs money. Do not quietly work around it.

