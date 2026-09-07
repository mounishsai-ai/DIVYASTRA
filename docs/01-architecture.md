# 01 — Architecture

## The shape

Five layers. Information flows down, results flow back up. **A layer may only
talk to the one directly below it.** That single restriction is what stops the
spaghetti.

```
        ME
   phone · voice · hotkey · a timer going off
             |
+------------v------------------------------------------+
|  1. CHANNELS            how a task arrives             |
|     telegram · voice · hotkey · scheduler              |
+------------+-------------------------------------------+
             |   every channel emits the SAME object:
             |   Task{ id, text, source, reply_to, urgency }
+------------v-------------------------------------------+
|  2. HUB           <- HERMES PROVIDES THIS              |
|     queue -> router -> agent loop -> memory -> cron    |
+------------+-------------------------------------------+
             |   MCP - one protocol for every capability
+------------v-------------------------------------------+
|  3. CAPABILITIES        the limbs (separate programs)  |
|     cua-driver (desktop + browser) · gmail · ours      |
+--------------------------------------------------------+

+--------------------------------------------------------+
|  4. VOICE I/O    sits beside the stack, not inside it  |
|     wake word -> STT -> text  |  text -> TTS -> speaker|
+--------------------------------------------------------+
+--------------------------------------------------------+
|  5. MODELS       reached only through one adapter      |
|     Gemini Flash (default) · Claude Sonnet (hard)      |
+--------------------------------------------------------+
```

---

## Why this shape and not something else

**The temptation** is to write one big program that listens to the mic, thinks,
clicks the screen, and sends Telegram messages. It works for a week. Then
WhatsApp changes something, and fixing it breaks the microphone — because
everything touches everything. That is the tangle.

**The fix** is that the core knows only three verbs: *receive a task*, *ask a
model*, *call a tool*. It does not know what a mouse is. It has never heard of
Telegram. Every concrete, breakable, vendor-specific thing lives at the edges,
in its own program, behind MCP.

So when WhatsApp breaks, exactly one folder is broken, and everything else keeps
running.

---

## Layer 1 — Channels

A channel's only job: turn something that happened into a `Task`, and know how
to deliver the answer back.

| Channel | Trigger | Reply goes to |
|---|---|---|
| `telegram` | message or voice note from my phone | Telegram, as text + voice note |
| `voice` | wake word "Divyastra" heard | speakers, via TTS |
| `hotkey` | a key combo on the laptop | a small on-screen panel |
| `scheduler` | a time, or a watched event | whichever channel I set |

Because they all produce the same `Task`, adding a fifth channel later (email?
SMS?) requires **zero** changes to the core.

### About "it calls me" — read this carefully

What you described — *assign a task during class, it finishes and calls back* —
is fully buildable, but the word **call** needs honesty:

- Telegram bots **can** send **voice notes** and push notifications. Your phone
  buzzes, you tap, you hear her voice. Free, works today. **This is what we
  build.**
- Telegram bots **cannot place a real phone call.** Only human accounts can.
- A true ringing PSTN call needs Twilio (paid) and, in India, **DLT
  registration** with a telecom operator. Real bureaucracy, real money.

So: voice-note-in, voice-note-out, plus a push notification. Same experience in
practice. We are not shipping a substitute under the word "call" without saying
so.

---

## Layer 2 — Hub → **Hermes provides this**

> Originally this layer was code we would write. It is not any more — see the
> D2 reversal in [02-decisions.md](02-decisions.md). The *shape* below is still
> exactly right; Hermes just already implements it, and implements it better
> than a first attempt would.

**What Hermes gives us:** the persistent task queue, the agent loop, persistent
memory, cron/scheduling, and the channel gateways (Telegram, Twilio, email…) —
all running locally on `127.0.0.1:8642`, no VPS.

**What stays ours:** the FRIDAY voice and personality, our own limbs, and the
cost discipline below.

### The cost discipline (ours to enforce, whoever runs the loop)

**Router** — decides *how much brain* a task deserves, before spending anything:

```
Tier 0   wake word fired?             local, 0 tokens
Tier 1   is this even a task?         rules / tiny local check, 0 tokens
Tier 2   ordinary task                Gemini Flash      <- ~90% land here
Tier 3   hard multi-step desktop work Claude Sonnet     <- capped by budget
```

**This is the answer to "it shouldn't burn tokens 24/7."** The assistant is
awake all day, but the expensive parts only wake for Tier 2 and above. Idle
DIVYASTRA costs nothing.

> **Unverified assumption — check in Phase 1.** Tiering needs Hermes to support
> **per-task or per-agent model overrides**, not just one global default model.
> If it does, the tiers are config. If it does not, we need another way to
> express "cheap by default, expensive only when hard" — find out before
> anything depends on it.
>
> Note the floor is safe regardless: wake word, STT and TTS are all local, so
> **idle genuinely costs zero** whatever the router can or cannot express.

**Agent loop** — the cycle from the glossary. It needs a step limit, a
wall-clock limit, and a spend limit, so a confused model cannot loop forever on
your credits. Non-negotiable — confirm Hermes exposes these, or add them.

**Memory** — three kinds, deliberately separated:
- *Task memory* — scratch notes, dies with the task.
- *Facts* — "my college portal is at X", "mom's number is Y".
- *Episodes* — what it did last time and whether it worked.

Hermes ships persistent memory, so use its facility rather than inventing one.
Do not build a vector database. You will want to. Don't.

---

## Layer 3 — Capabilities

Each is a separate program exposing tools over MCP. Most are third-party — we
write config, not code.

| Limb | What it is | Ours? |
|---|---|---|
| `cua-driver` | clicks, types, reads windows **and drives the browser** | no — installed ✓ |
| `gmail` | read/send mail | no — install it |
| `files` | read/write in allowed folders | **ours**, later |
| `college` | timetable, portal, deadlines | **ours**, later |
| ~~`playwright`~~ | superseded by cua-driver's `browser_*` tools | dropped |
| ~~`whatsapp`~~ | dropped — ToS/ban risk not worth it | dropped |

### Desktop: why `cua-driver`

It reads the Windows **accessibility tree** and delivers input in the
**background** — it paints its own synthetic cursor and leaves your real mouse
alone. You can keep using the laptop while it works. It needs **no admin
rights, no GPU, no Python or Node** — a self-contained binary. It speaks MCP
natively, so it drops into Phase 0 with no code at all.

Its honest limits: some apps misreport their accessibility tree; admin windows
cannot be driven from a normal process (Windows UIPI); and Chromium/Electron
apps need real foreground focus for coordinate clicks.

### Browser: separate tools, same limb

Clicking a web page by screen position is fragile and, in Chromium, steals your
focus. So the browser gets its own **tools** — `browser_navigate`,
`browser_click`, `browser_type`, `get_browser_state` and friends — which talk
to the browser's own automation protocol (CDP) and address real page elements.

These ship *inside* `cua-driver`, so it is one limb, not two. The flag
`--grant existing-profile` lets them attach to your **already logged-in Chrome
or Edge**.

Rule, unchanged: **anything inside a browser uses the `browser_*` tools.
Everything else uses the desktop tools.** Never pixel-click a web page.

---

## Layer 4 — Voice I/O

```
mic ----> openWakeWord ----> whisper.cpp ----> Task
                                                |
speaker <---- Kokoro TTS <---- reply text <-----+
```

All three run **locally on CPU**, which the Intel UHD hardware forces and which
is a gift: zero cost, zero latency to a server, and your microphone audio never
leaves the laptop.

**The FRIDAY voice.** Kokoro-82M ships 54 voices and runs on CPU. Pick one
female voice, put it behind the TTS adapter, and never scatter the choice
across the code. If you later want ElevenLabs or Google Chirp3-HD, one file
changes. Note the personality is *not* the voice — it is the system prompt.
Write that separately and version it.

---

## Layer 5 — Models

One adapter. Two providers. Never call a vendor SDK from anywhere else.

- **Gemini Flash — the default.** A free tier exists permanently; the $300 GCP
  credit covers bursts. Cheap, fast, good at tool calling.
- **Claude Sonnet via Agent SDK — the specialist.** Pro includes a **$20/month
  Agent SDK credit** (does not roll over). Reserve it for genuinely hard
  multi-step desktop work.

**Important and easy to get wrong:** your **Claude Code Pro subscription is the
workshop, not the engine.** It is what you and I use to *build* DIVYASTRA.
Anthropic prohibits using subscription login to power a third-party app. The
engine inside DIVYASTRA is Gemini, plus that separate $20 SDK credit.

---

## Later: gestures

Pinch-to-click via **MediaPipe Hands** — runs on CPU, free, no GPU needed.

It is deliberately last, and it is a **channel**, not a new system: the webcam
becomes another way to emit a Task or a click. If the architecture is right,
adding it touches one folder. **If adding gestures requires changing the core,
the architecture was wrong** — that is the test.

Do not start this until Phases 0–4 work. It is the most fun and the least
useful part of the project, which is exactly how projects die.
