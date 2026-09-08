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
- **Microsoft UFO2** — rejected as a *dependency* because it is a full
  multi-agent research framework rather than a library, and OmniParser-v2 wants
  a GPU. **That call still stands. The reasoning was lazy, and it cost us.**

  > **Second thoughts, 2026-09-08.** The line "revisit for ideas" was written
  > and then never acted on — while $6 and eight failed experiments went into
  > problems UFO2 had already solved. Its two central ideas are precisely our
  > two hardest problems:
  >
  > **1. "Unified GUI–API action layer"** — use the application's native API
  > when one exists, fall back to the GUI otherwise. That is exactly the
  > cheapest-first ladder we rediscovered the expensive way and wrote into
  > [01-architecture.md](01-architecture.md).
  >
  > **2. "Speculative multi-action execution"** — one LLM query predicts
  > *several* actions; each is validated against the Windows UIA
  > (`is_enabled()`, `is_visible()`) **without a model call**; they execute in
  > order and halt on the first failed precondition. Microsoft measured **up to
  > 51.5% fewer completion steps** at comparable success rates. Their statement
  > of the problem is verbatim the wall we hit: *"each automation step requires
  > a full LLM inference for every single GUI action."*
  >
  > **We tested the idea and it works on our stack** — see
  > [06-phase1-hermes.md](06-phase1-hermes.md). Batching clicks into one model
  > turn cut calls from 21–39 to a **deterministic 14**.
  >
  > **Lesson:** "reject as a dependency" and "ignore the research" are different
  > decisions. Read the paper of the thing you turn down, especially when it
  > targets your hardest constraint.
- **Agent-S3 (Simular)** — strong, cross-platform, but framework-shaped like
  UFO2. Same objection.
- **Raw pyautogui** — clicks by pixel coordinate, steals your mouse, breaks on
  any resolution or theme change. This is the naive path; it is why people
  think desktop agents are unreliable.

---

## D2. Overall spine → **Hermes Agent** ~~our own thin core~~

> **REVERSED 2026-09-08.** The original decision rejected Hermes as
> "server-shaped." **That was wrong**, and it was based on incomplete docs.
> Mounish pushed back and asked me to check the June 2026 desktop release.
> He was right. The corrected decision follows. The original reasoning is kept
> below so the mistake stays visible.

### What the recheck found (Hermes v0.15.2+, June 2026)

- There is a **native Windows guide**. The installer is self-contained —
  it brings its own Python 3.11, Node, git, ripgrep and ffmpeg into
  `%LOCALAPPDATA%\hermes`. No WSL, no Docker.
- **The gateway runs locally.** `hermes gateway install` registers a normal
  **Windows Scheduled Task**, non-elevated, started at login — the same
  mechanism `cua-driver` already uses.
- **Telegram uses long polling.** No public URL, no webhook, no tunnel, no
  VPS. The gateway reaches out to Telegram, so a laptop behind a router works.
- Local mode serves on `127.0.0.1:8642`. Remote is *optional*, not required.
- 30+ channels including Telegram, **SMS/voice via Twilio**, Email, Signal.
- MIT licensed, model-agnostic, MCP-capable, persistent memory, cron, skills.
- Its GPU requirement applies **only to local inference**, which we are not
  doing — our brain is Gemini in the cloud.

### Why this is now the right call

Hermes already implements what Phases 2, 3 and 4 of our roadmap describe: the
task hub, the channels, the scheduler, and persistent memory. Writing those
ourselves would be exactly the "months of glue before anything works" failure
this project is organised to avoid. **The anti-tangle principle argues for
adopting it, not against.**

Critically, **our Phase 0 work carries over unchanged** — Hermes drives the
desktop through `cua-driver`, the very thing we installed and verified. The
`cua-driver` installer even prints a `mcp-config --client hermes` option. We
are not throwing anything away.

### What stays ours

- The **FRIDAY voice and personality** (Kokoro + our own system prompt).
- **Custom limbs** as MCP servers: college portal, files, anything Hermes has
  no reason to ship.
- The **cost discipline** — model routing and spend caps.
- Gestures, later.

### What we accept

- Coupling to Hermes's direction. Mitigated by MIT licence and by the fact
  that every limb is an MCP server that would survive a move.
- Learning someone else's config model instead of our own code. For an
  assistant that should exist and work, this is a good trade.

### Original (incorrect) reasoning, kept deliberately

> Rejected as the spine because its design centre is "an agent that lives on
> your server" — messaging integrations require a gateway on a remote host and
> cron is backend-managed.

**The lesson:** that came from a docs page that did not mention Windows or
local mode. Verify a blocking claim against the primary source *for the
current version* before letting it decide an architecture.

---

## D3. Browser → **cua-driver's built-in browser tools** ~~Playwright MCP~~

> **REVISED 2026-09-08**, after actually installing the driver. Playwright is
> probably unnecessary.

The reasoning for a separate browser limb was right, but the assumption that we
needed *Playwright* for it was wrong. `cua-driver` 0.24.0 already ships a full
CDP-based browser surface as its own tools:

```
browser_navigate  browser_click   browser_type    browser_pointer
browser_dialog    browser_download browser_prepare browser_set_input_files
get_browser_state
```

These drive the browser through Chrome DevTools Protocol — real page elements,
not pixels — which is exactly what Playwright was wanted for. And the flag
`--grant existing-profile` pre-authorises attaching to your **already
logged-in Chrome or Edge profile**, which was the fiddliest open problem in the
original Phase 0 plan. It is now one flag in `.mcp.json`.

**So the architectural rule is unchanged** — browser work goes through browser
tools, desktop work through desktop tools — but it is one limb, not two, and
one less thing to install, configure and keep working.

**VERIFIED 2026-09-08.** The tools attached to the real logged-in Chrome
(`Profile 8`) and read Wikipedia's featured article. Playwright is dropped for
good. See [05-phase0-findings.md](05-phase0-findings.md) for the three
obstacles hit on the way.

**Rejected:** Chrome DevTools MCP (aimed at debugging, not driving);
browser-use (a whole agent with its own model loop — we want hands, not another
brain).

---

## D4. Everyday brain → **Gemini Flash**; hard tasks → **Claude Sonnet**

Forced by two facts discovered in research:

1. **Anthropic prohibits subscription auth for third-party apps** (policy
   effective Feb 2026). Your Claude Code Pro login cannot legally power
   DIVYASTRA.
2. **Pro does include a $20/month Agent SDK credit** (from 15 Jun 2026, no
   rollover). That is real, legitimate Claude budget — enough for occasional
   hard reasoning, not enough to be the default.

So Gemini Flash is the workhorse, Claude is the specialist.

**REVISED 2026-09-08 — Vertex AI, not AI Studio.** Mounish chose to spend the
$300 Google Cloud credit (~$290 left) rather than sit on the AI Studio free
tier. Hermes has native Vertex support, including refresh of the 1-hour OAuth
token, so this is config rather than code.

Consequences, all verified live:

- Model name gains a publisher prefix: **`google/gemini-3.8-flash`**.
- Region must be **`global`** (Gemini 3.x is global-only).
- **A service account is mandatory.** Hermes sends a bare bearer token with no
  `x-goog-user-project` header, which user ADC requires — so ADC 403s. Details
  and the revoke command are in [06-phase1-hermes.md](06-phase1-hermes.md).

**The free tier remains the fallback, not a dead path.** The credit expires
around 2026-12-06. Switching back is two lines: `provider: "gemini"` and a bare
model name. Keep that reversibility — do not let anything depend on Vertex
specifically.

### Could we use Claude instead of Gemini? (asked 2026-09-08)

Two different questions hide in this, and they have opposite answers.

**1. Should we use Anthropic's Computer Use tool? No.**
Claude's Computer Use is a **screenshot + mouse/keyboard** surface — it looks at
pixels and moves a pointer. `cua-driver` reads the **Windows accessibility
tree** and clicks elements *by name*. Ours is strictly better here: no image
tokens, no coordinate drift, and it survives the window moving. Adopting
screenshot-driving would be a downgrade, and it is the same pixel approach
rejected in D1.

**2. Should we use a Claude model as the brain, still driving `cua-driver`? Blocked on cost.**
It would be a **model swap, not a tool swap** — one line of Hermes config. But
see below: it cannot be paid for with the GCP credit.

**WRONG on first check — Mounish caught it.** An HTTP 200 on the *model
metadata* endpoint looked like availability. It is not. The actual generation
call fails:

```
429 RESOURCE_EXHAUSTED
Quota exceeded for global_online_prediction_requests_per_base_model
with base model: anthropic-claude-haiku-4-5
```

Quota for Anthropic partner models on this project is **zero**, and Google's own
free-trial documentation closes the loop:

> "The $300 credit cannot be used for generative AI partner models that are
> offered as managed APIs (model as a service)."

The same page notes the trial **cannot request a quota increase**. So it is
blocked three ways at once: no quota, credits explicitly exclude partner models,
and the one escape hatch is unavailable on a trial account.

**Therefore Claude on Vertex is not an option today.** Not "expensive" —
unavailable.

**The only real Claude path is the Anthropic API directly, paid out of pocket.**
The $20/month Agent SDK credit does **not** apply (it covers the Agent SDK and
`claude -p`; Hermes calls the API directly). Against `gemini-3.8-flash` at
$0.75 / $3.75 per 1M:

| Model | Input | Output | vs Flash |
|---|---|---|---|
| `claude-haiku-4-5` | $1.00 | $5.00 | 1.3x |
| `claude-sonnet-5` | $2.00 | $10.00 | 2.7x |
| `claude-opus-5` | $5.00 | $25.00 | 6.7x |

**Decision: stay on Gemini 3.8 Flash.** Not a preference — economics. It is
covered by ~$290 of credit that is otherwise unspendable, while any Claude route
is real money from a student's pocket. Revisit only if the credit runs out or a
task genuinely fails on Flash.

**The lesson (second time today):** a 200 on a metadata endpoint is not proof of
access. Test the call that actually costs money.

**If it ever is revisited:** do not decide on one run. The same task varies
**2.4x** run to run, so any model comparison needs 5+ runs each, judged on **API
call count** — far less noisy than cost.

---

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

## D6. ~~Telegram~~ → **local first**, WhatsApp later, Twilio for real calls

> **REVISED 2026-09-08.** Telegram is dropped entirely at Mounish's decision.
> The order is now **local first, remote later**: get her working at the laptop
> (voice, hotkey), and add phone access afterwards — as **WhatsApp**, not
> Telegram, because that is what he actually uses.

Consequence: the "task from class" feature moves later in the plan. That is the
right trade — an assistant you can talk to at your desk is worth more than one
you can message but that cannot do anything yet.

Twilio's role is unchanged: **real ringing calls**, which no messaging channel
can do.

**Twilio is added for actual ringing calls** — decided by Mounish 2026-09-08.
Also a built-in Hermes gateway, so it is config rather than code.

### Twilio in India — the rules that actually apply

Checked against Twilio's own India voice guidelines:

- **Outbound calls to Indian numbers can only be placed from an international
  (non-Indian) number.** So you rent a US number and it calls your Indian
  mobile. This works, but the call will show a foreign caller ID — it may look
  like spam to you at first, and may be filtered by your carrier or phone.
- **Consent is required** for commercial communications. You are calling
  *yourself*, so this is satisfied by definition — this is not telemarketing.
- **Voice OTP/2FA is not permitted** and is blocked. We are not doing that.
- **High volumes of short calls trigger automatic carrier blocks.** A handful
  of personal calls a day is fine; do not build anything that dials in a loop.
- Trial accounts can only call **verified** numbers — which is exactly your own
  number, so the free trial is enough to build and test the whole thing.

**Cost:** roughly $1–2/month for a US number, plus about $0.0075–0.02/minute to
Indian mobiles. Small, but **not free** — the first genuinely paid component in
DIVYASTRA. Budget it consciously.

**Note:** Twilio is *not* a TRAI-registered telemarketer in India. That matters
for commercial campaigns, not for an assistant calling its owner — but it is
why you should never point this at anyone else's number.

**Rejected:** Plivo/Exotel — genuinely cheaper for India and worth a look if
Twilio's foreign caller ID becomes annoying, but Twilio is already a Hermes
gateway and that integration is worth more than the price difference here.

---

## D7. WhatsApp → **skipped**

Dropped 2026-09-08 at Mounish's decision. Good call — it was the only component
carrying account-ban risk, and Telegram plus Twilio already covers reaching
your phone.

Kept for the record: unofficial WhatsApp Web bridges violate WhatsApp's Terms
of Service and accounts using them can be banned. If this is ever revisited,
use a secondary number, never the primary. Hermes does ship a WhatsApp gateway,
so it would be config — but the ToS risk is unchanged by that convenience.

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
