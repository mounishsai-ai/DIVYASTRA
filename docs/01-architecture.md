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
|     voice · hotkey · scheduler  (whatsapp: later)      |
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

| Channel | Trigger | Reply goes to | When |
|---|---|---|---|
| `voice` | wake word "Divyastra" heard | speakers, via TTS | **first** |
| `hotkey` | a key combo on the laptop | a small on-screen panel | first |
| `scheduler` | a time, or a watched event | whichever channel I set | soon |
| `whatsapp` | message or voice note from my phone | WhatsApp, text + voice note | **later** |

**Local first, remote later** (decided 2026-09-08). Get her working at the
laptop; reaching her from the phone comes after. Telegram is dropped entirely —
WhatsApp is the one messaging channel, and only later.

Because every channel produces the same `Task`, adding WhatsApp later requires
**zero** changes to anything else. That is the whole point of the layering.

### About "it calls me" — read this carefully

What you described — *assign a task during class, it finishes and calls back* —
is fully buildable, but the word **call** needs honesty:

- **WhatsApp can carry voice notes both ways.** Your phone buzzes, you tap, you
  hear her voice. That covers the experience you described.
- **A messaging bot cannot make your phone ring.** That is a different thing.
- A true ringing call needs **Twilio**, an international number (Indian numbers
  cannot place these), and real money. Details in D6 of
  [02-decisions.md](02-decisions.md).

So there are two separate features: *voice notes* (easy, part of WhatsApp) and
*a ringing call* (Twilio, paid, later). We are not shipping one under the name
of the other.

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

> **RESOLVED 2026-09-08.** Hermes *does* support per-task model overrides
> (`delegation.model`, and `--model` per invocation), so tiering is config.
> Note Hermes recommends the **inverse**: frontier parent, cheap children —
> because children carry most of the tokens. Probably better than our version.
> Not adopted yet; no usage data to justify a choice.

**Agent loop** — the cycle from the glossary. It needs a step limit, a
wall-clock limit, and a spend limit.

> **RESOLVED 2026-09-08 — two out of three.** Hermes has step caps
> (`delegation.max_iterations`) and failure-loop caps
> (`tool_loop_guardrails`), but **no spend cap at all**. That is enforced
> outside Hermes, by a Google Cloud budget alert. See
> [06-phase1-hermes.md](06-phase1-hermes.md).

**Memory — use Hermes's, do not build our own.**

Hermes already ships exactly this, with deliberate hard caps:

```yaml
memory:
  memory_enabled: true        # agent's own notes
  user_profile_enabled: true  # preferences, style
  memory_char_limit: 2200     # ~800 tokens
  user_char_limit: 1375       # ~500 tokens
```

Both are injected into the system prompt every call. So Hermes made the same
architectural choice we would have — a small flat block, always present, hard
capped — and it is already built. **We write facts into it; we do not invent a
facts file.**

### Why a flat file beats RAG here (asked 2026-09-08)

For **one person**, the flat block wins decisively:

- The whole corpus is tiny. Hermes caps it at ~1,300 tokens; a student's facts
  fit easily. RAG exists for corpora too big to fit — that is not this.
- **Prompt caching** makes a *static* block cheap on repeat. A cached read bills
  far below the normal input rate; the Calculator run read 929K cached tokens.
  A block that never changes is the ideal cache candidate.
- RAG costs an **extra embedding API call per query**, plus a vector store to
  run, plus retrieval latency — and it still injects the retrieved text.
- RAG can retrieve the **wrong** chunk. A flat block is deterministic.

The crossover is when facts outgrow what you would pay to send every call —
call it tens of KB. For one student, that day may never come. **Revisit only
when Hermes's own caps start truncating things you needed.**

### The trap: don't let build-time docs into runtime

**Measured 2026-09-08:** Hermes injects `SOUL.md`, `AGENTS.md`, **`CLAUDE.md`**
and `.cursorrules` from its working directory.

| Hermes run from | System prompt |
|---|---|
| a neutral folder | 16,229 B |
| this project folder | **25,237 B** (+7,467 B of CLAUDE.md) |

**That is a 55% larger prompt on every single call, for documentation that
exists to guide Claude Code while building — not to guide DIVYASTRA at run
time.** Keep the two straight:

- **`CLAUDE.md` + `docs/` = build time.** For Claude Code. Never for Hermes.
- **`SOUL.md` + Hermes memory = run time.** For DIVYASTRA. Where FRIDAY lives.

**Rule: do not run Hermes with its working directory set to this repo.** Give
it the folder the task is actually about.

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

### The GUI is the expensive path — use it last

**Asked 2026-09-08: is ~$0.30 and three minutes the limit for agentic desktop
control?** Roughly yes, and the reason is structural:

1. Every UI action needs a model decision — **one API call**.
2. Element-indexed actions need a fresh snapshot first — **a second call**.
3. The whole conversation is re-sent on every call, so tokens grow **roughly
   quadratically** with the number of actions.

So GUI driving costs about `O(actions²)` in tokens. No prompt tweak changes
that; five separate attempts failed to (see
[06-phase1-hermes.md](06-phase1-hermes.md)).

**`cua-driver`'s own MCP server instructions say the same thing:**

> "Before UI work, classify the desired outcome. For non-GUI outcomes, prefer a
> client-provided app API/SDK, headless/background interface, CLI, or filesystem
> operation and read the result back in that semantic domain."

The tool built for driving GUIs tells you not to drive a GUI when you have an
alternative. **Take that seriously.**

**The ladder, cheapest first — measured:**

| Approach | Measured cost | Use when |
|---|---|---|
| API / CLI / file | **~$0** | An interface exists. Gmail has an API — do not click Gmail. |
| Desktop UIA, batched | **$0.12** (14 calls) | Native app, stable UI |
| Desktop UIA, plain | $0.19–0.47 (21–39) | Native app |
| Browser (CDP) | $0.37 (45 calls) | A web page with no API |
| Pixel clicking | worst | Never, unless the tree lies |

> **Desktop and browser are comparable**, once configured correctly. An earlier
> claim that browser was ~2x worse measured a permission bug of ours, not the
> browser — see [06-phase1-hermes.md](06-phase1-hermes.md). What separates the
> rows that matter is **API vs GUI**, not desktop vs browser.
>
> **Browser has one extra cost that does not show up in tokens:** Chrome
> requires a human to click "Allow remote debugging?" and no agent can click it
> for you. Unattended browser work needs that consent already granted.

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
