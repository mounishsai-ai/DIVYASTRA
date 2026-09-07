# 02 — Decisions & Rejected Alternatives

Why each choice was made, and — more usefully — what was *rejected*. When you
are tempted by a shiny alternative in three months, read the rejection first.

Researched 2026-09-07.

---

## D1. Desktop control → **cua-driver** (trycua/cua, MIT)

**Chosen because** it is the only option that satisfies all four hard
constraints at once: no GPU, no admin rights, native Windows, and it speaks MCP
out of the box. It uses Windows UI Automation with MSAA fallback, delivers
input via `PostMessage` where possible (background) and `SendInput` only when
forced, and paints a *synthetic* cursor so your real mouse is untouched.

Install is one line, user-scoped, no runtime dependencies.

**Rejected:**

- **UI-TARS (ByteDance)** — needs a 16 GB+ VRAM GPU to run its own vision
  model. You have Intel UHD integrated graphics. Physically impossible. Their
  hosted API would work but is another paid dependency.
- **Microsoft UFO2** — genuinely excellent and Windows-native, with the best
  research behind it (hybrid UIA + OmniParser detection). Rejected as a
  *starting point* because it is a full multi-agent research framework, not a
  library — adopting it means adopting its whole worldview, and OmniParser-v2
  wants a GPU. **Revisit for ideas**, not as a dependency.
- **Agent-S3 (Simular)** — strong, cross-platform, but framework-shaped like
  UFO2. Same objection.
- **Raw pyautogui** — clicks by pixel coordinate, steals your mouse, breaks on
  any resolution or theme change. This is the naive path; it is why people
  think desktop agents are unreliable.

---

## D2. Overall spine → **our own thin core**, with Hermes as a *reference*

**Hermes Agent (Nous Research, MIT)** was the strongest candidate to adopt
wholesale. It already has persistent memory, cron, voice, profiles, skills, and
a desktop app. It is genuinely impressive and worth reading.

**Rejected as the spine because** its design centre is *"an agent that lives on
your server."* Concretely: its messaging/channel integrations require a
separate long-running **gateway process on a remote host**, and its cron is
backend-managed. DIVYASTRA's whole premise is the opposite — *an assistant that
drives my own laptop, offline-capable, no VPS, no monthly hosting bill.*
Adopting a server-shaped system for a laptop-shaped problem is precisely the
kind of mismatch that produces months of untangling.

**But we take its best idea directly:** Hermes drives the desktop through
`cua-driver`. We use that same driver, without inheriting the server.

**Reconsider if** you ever get a VPS and want DIVYASTRA reachable when the
laptop is off.

---

## D3. Browser → **Playwright MCP**, separate from the desktop limb

**Chosen because** the browser is where most real tasks live and it is the one
app with a *better* interface than the accessibility tree. Playwright addresses
real page elements, survives layout changes, and can attach to your **existing
Chrome profile with your logins already in it**.

**The deciding fact:** `cua-driver` documents that Chromium coordinate clicks
require foreground focus-stealing. Routing the browser through the desktop limb
would break the "keep using your laptop while it works" property. Two limbs it
is.

**Rejected:** Chrome DevTools MCP (aimed at debugging and performance, not
driving); browser-use (excellent, but it is a whole agent with its own model
loop — we already have a brain, we want hands).

---

## D4. Everyday brain → **Gemini Flash**; hard tasks → **Claude Sonnet**

Forced by two facts discovered in research:

1. **Anthropic prohibits subscription auth for third-party apps** (policy
   effective Feb 2026). Your Claude Code Pro login cannot legally power
   DIVYASTRA.
2. **Pro does include a $20/month Agent SDK credit** (from 15 Jun 2026, no
   rollover). That is real, legitimate Claude budget — enough for occasional
   hard reasoning, not enough to be the default.

So Gemini Flash is the workhorse (permanent free tier + your $300 GCP credit),
Claude is the specialist. Both behind one adapter, so the split can be retuned
by changing a threshold rather than rewriting anything.

**Rejected:** a local LLM. With Intel UHD and 15.7 GB RAM, any model good
enough for reliable tool-calling would be unusably slow. Settled — do not
revisit without different hardware.

---

## D5. Voice → **whisper.cpp** in, **Kokoro-82M** out, **openWakeWord** trigger

All local, all CPU, all free. Chosen over cloud voice because it costs nothing
per use, has no network latency, works offline, and keeps your microphone audio
on your own machine.

- **Kokoro-82M** (Apache-2.0): 82M params, ~327 MB, 54 voices, runs on CPU.
  The female voice for FRIDAY comes from here.
- **whisper.cpp**: CPU-first, supports streaming partial results. Chosen over
  faster-whisper, whose main advantage is NVIDIA int8 acceleration you cannot
  use.
- **openWakeWord**: free and offline. *Note:* code is Apache-2.0 but the
  **pretrained models are CC-BY-NC-SA 4.0 — non-commercial.** Fine for personal
  use; if DIVYASTRA ever ships to others, retrain or switch.

**Rejected:** ElevenLabs (quality is great, free tier too small for daily use);
Gemini Live API (superb for real-time conversation, ~$0.12/min — that is a
*conversation* budget, not an *assistant-that-runs-all-day* budget).
**Reconsider Gemini Live** specifically for a "talk to her like a person" mode
later; it is the right tool for that one job.

---

## D6. Phone channel → **Telegram bot**

Free, excellent API, handles voice notes both directions, works from any
device, no phone number for the bot, no ToS problem. The single highest
value-per-hour component in the project.

**Rejected:** Twilio/PSTN (paid + India DLT registration); SMS (no audio);
email as a control channel (too slow, no push).

---

## D7. WhatsApp → **build it, but late, and with eyes open**

Technically fine: mature MCP servers exist (e.g. `lharries/whatsapp-mcp`), and
they work by bridging WhatsApp Web.

**The real risk, stated plainly:** unofficial WhatsApp Web bridges **violate
WhatsApp's Terms of Service**, and accounts using them **can be banned**. It is
your account and your call, but losing your primary WhatsApp as a student is a
genuinely bad day.

**If we build it:** use a secondary number, never the primary. Alternatively
the official WhatsApp Cloud API is ToS-safe but requires a Meta Business
account and is clumsy for personal messaging.

Scheduled for Phase 5 — after everything that carries no account risk works.

---

## D8. Documentation lives in `docs/`, not `CLAUDE.md`

`CLAUDE.md` is loaded into context *every single session*. A 2000-line document
there wastes budget on every message and silently drifts from reality. So
`CLAUDE.md` holds only invariants, rules, and the current phase; everything
else is here and read on demand.

---

## Open questions (decide when reached)

- Which Gmail MCP server? Several viable. Pick at Phase 0 by trying two.
- Which mailbox — professional or personal? Probably professional only, at
  first read-only.
- SQLite or a JSON file for the task queue? Start with JSON; move only if it
  actually hurts.
- Does DIVYASTRA get its own Windows user account for safety? Would neatly
  contain the blast radius. Costs convenience.
