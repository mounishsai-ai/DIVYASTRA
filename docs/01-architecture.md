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
|  2. CORE                the hub                        |
|     queue -> router -> agent loop -> memory            |
+------------+-------------------------------------------+
             |   MCP - one protocol for every capability
+------------v-------------------------------------------+
|  3. CAPABILITIES        the limbs (separate programs)  |
|     cua-driver · playwright · gmail · whatsapp · files |
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

## Layer 2 — Core

Four small pieces. This is the only code that is truly *ours*.

**Queue** — tasks land here. Survives restart (a file or SQLite, not memory).
Lets a task from class sit until the laptop is awake.

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

**Agent loop** — the cycle from the glossary. Add: a step limit, a wall-clock
limit, and a spend limit, so a confused model cannot loop forever on your
credits. Non-negotiable.

**Memory** — three kinds, deliberately separated:
- *Task memory* — scratch notes, dies with the task.
- *Facts* — "my college portal is at X", "mom's number is Y". A plain file.
- *Episodes* — what it did last time and whether it worked.

Start with only *facts*, in one Markdown file. Do not build a vector database.
You will want to. Don't.

---

## Layer 3 — Capabilities

Each is a separate program exposing tools over MCP. Most are third-party — we
write config, not code.

| Limb | What it is | Ours? |
|---|---|---|
| `cua-driver` | clicks, types, reads windows on Windows | no — install it |
| `playwright` | drives the real browser | no — install it |
| `gmail` | read/send mail | no — install it |
| `whatsapp` | messages (see risk note in 04) | no — install it |
| `files` | read/write in allowed folders | **ours**, later |
| `college` | timetable, portal, deadlines | **ours**, later |

### Desktop: why `cua-driver`

It reads the Windows **accessibility tree** and delivers input in the
**background** — it paints its own synthetic cursor and leaves your real mouse
alone. You can keep using the laptop while it works. It needs **no admin
rights, no GPU, no Python or Node** — a self-contained binary. It speaks MCP
natively, so it drops into Phase 0 with no code at all.

Its honest limits: some apps misreport their accessibility tree; admin windows
cannot be driven from a normal process (Windows UIPI); and Chromium/Electron
apps need real foreground focus for coordinate clicks.

### Browser: why a separate limb at all

That last limitation is exactly why **the browser does not go through the
desktop limb.** Clicking a web page by screen position is fragile and, in
Chromium, steals your focus. Playwright talks to the browser's own automation
protocol — it addresses real page elements, survives layout changes, and runs
against your **normal Chrome profile with your existing logins**.

Rule: **anything inside a browser goes to the browser limb. Everything else
goes to the desktop limb.**

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
