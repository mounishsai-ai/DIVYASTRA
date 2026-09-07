# 03 — Roadmap

Each phase ends with **acceptance tests**. A phase is not finished because it
feels finished — it is finished when its tests pass. Do not start phase N+1
with phase N red.

Each phase is also *useful on its own*. There is no point in this plan where
you have three weeks of work and nothing that runs.

---

## Phase 0 — Claude Code is the brain (zero custom code)

**The idea:** before writing any DIVYASTRA code, wire the limbs into Claude
Code and drive them by hand. You get a working assistant immediately, and a
permanent test bench for every limb you ever add.

This directly attacks the failure mode you described: months of glue before
anything works.

**Steps**
1. ~~`irm https://cua.ai/driver/install.ps1 | iex`, then `cua-driver doctor`~~
   **done 2026-09-08** — 0.24.0, all probes green.
2. ~~Write `.mcp.json`~~ **done** — includes `--grant existing-profile` so the
   browser tools can attach to logged-in Chrome/Edge.
3. **Restart Claude Code** so the `cua-*` MCP tools load.
4. Exercise the `browser_*` tools (they replace Playwright — see D3).
5. Add a Gmail MCP server; complete Google OAuth. Decide **which mailbox**
   first: professional or personal.

**Acceptance**
- [x] `cua-driver doctor` reports a healthy interactive session.
- [x] A real app driven end-to-end: Calculator launched, UIA tree read, four
      buttons clicked **by name**, `Display is 42` read back — **and the real
      mouse pointer never moved.**
- [ ] From Claude Code (after restart): *"open wikipedia.org and tell me the
      featured article"* — via `browser_navigate` / `get_browser_state`.
- [ ] From Claude Code: *"summarise my three most recent emails."*
- [x] Written down: what each limb cannot do — see
      [05-phase0-findings.md](05-phase0-findings.md).

*Stretch, not a gate:* the same browser task against your logged-in profile.

**Value even if you stop here:** a genuinely useful desktop assistant.

---

## Phase 1 — Hermes as the spine

Hermes replaces what used to be Phases 2, 3 and 4 of this plan. See the D2
reversal in [02-decisions.md](02-decisions.md) for why.

**Steps**
1. Install Hermes natively on Windows (self-contained — brings its own Python,
   Node, git, ffmpeg into `%LOCALAPPDATA%\hermes`). No WSL, no Docker.
2. Configure **Gemini Flash** as the default model.
3. Register `cua-driver` as an MCP server inside Hermes:
   `cua-driver mcp-config --client hermes`
4. Confirm the same Calculator task works *through Hermes* rather than through
   Claude Code.

**Acceptance**
- [ ] Hermes runs locally (`127.0.0.1:8642`), no remote host configured.
- [ ] A desktop task issued to Hermes completes using `cua-driver`.
- [ ] The model is Gemini, and the model choice lives in config, not in code.
- [ ] Nothing from Phase 0 had to be rebuilt.

---

## Phase 2 — Telegram

The feature you actually described: task from class, done at home.

**Steps**
1. BotFather → token. `@userinfobot` → your numeric user ID.
2. `hermes gateway setup`, then `hermes gateway install` (registers a Windows
   Scheduled Task at logon, non-elevated).
3. Lock the allow-list to **your user ID only**.
4. Voice notes in; text and voice replies out.

**Acceptance**
- [ ] Send a task from your phone; the laptop does it; a reply comes back.
- [ ] Anyone else messaging the bot is refused.
- [ ] Laptop asleep → task waits → runs on wake.
- [ ] No public URL, no tunnel, no VPS anywhere in the setup.

---

## Phase 3 — Her voice (FRIDAY)

Hermes has a voice mode, but the *personality and voice* are ours — this is the
part that makes it DIVYASTRA and not a generic agent.

**Steps**
1. Kokoro-82M locally. Audition voices, pick the FRIDAY one.
2. `voice/tts.py` exposing exactly `speak(text)`.
3. whisper.cpp on CPU. `voice/stt.py` exposing `listen() -> str`.
4. openWakeWord on "Divyastra".
5. `voice/personality.md` — who she is. Versioned, separate from the voice.

**Acceptance**
- [ ] `speak("Systems online.")` sounds right to you.
- [ ] Round-trip: say something → text within ~2 s.
- [ ] Wake word runs one hour with **zero** false triggers, near-zero CPU.
- [ ] Swapping the TTS engine touches **only** `voice/tts.py`.

---

## Phase 4 — Twilio: it actually calls you

**Read the India rules in [02-decisions.md](02-decisions.md) D6 first.** Short
version: rent an **international** number (Indian numbers cannot place these
calls), keep the volume low, and only ever call your own verified number.

**Steps**
1. Twilio trial; verify your own mobile as a caller ID.
2. Configure Hermes's built-in Twilio gateway.
3. Call only on tasks you explicitly mark as call-worthy — everything else
   stays on Telegram.

**Acceptance**
- [ ] A finished task triggers a real ringing call, and you hear the result.
- [ ] Only your verified number is ever dialled — enforced, not intended.
- [ ] A per-day call cap exists and is enforced.
- [ ] Cost per call is measured and written down.

---

## Phase 5 — Scheduling and initiative

Much of this is Hermes cron; the work is deciding *policy*, not building it.

**Steps**
1. Recurring tasks via Hermes cron.
2. Watchers: new mail matching a rule, a deadline nearing.
3. Quiet hours, and a daily spend budget.

**Acceptance**
- [ ] *"Every day at 8 pm, check the portal for new assignments and tell me."*
- [ ] Idle for 24 h costs **zero** tokens. Verify in the provider console.
- [ ] **The billing-disabled week.** Turn off GCP billing and use her normally
      for a week on the free Flash tier alone. If she still works, DIVYASTRA
      survives the day the $300 expires. If not, fix it now — far cheaper to
      learn in month one than month four.

---

## Phase 6 — Custom limbs

Only now, when the assistant already works, do we write our own code.

1. `capabilities/files` — read/write inside an allow-listed folder only.
2. `capabilities/college` — timetable, portal, deadlines.

**Acceptance**
- [ ] The files limb refuses a path outside its allow-list.
- [ ] Each limb works from Claude Code's MCP client *before* Hermes uses it.

---

## Phase 7 — Gestures (stretch)

Only after 0–6 are green.

1. MediaPipe Hands on the webcam, CPU.
2. Pinch → click, behind a hotkey so it is never always-on.
3. Two or three gestures maximum.

**Acceptance**
- [ ] Pinch-to-click works at a comfortable distance.
- [ ] **It was added as a limb/channel and nothing else changed.** This is the
      real test of the whole architecture.

---

## Deliberately NOT doing

Written down so they stop being tempting:

- A vector database / RAG memory. A Markdown file of facts is enough for one
  person. Revisit only when it demonstrably fails.
- A web dashboard. Telegram is the UI.
- A local LLM. The hardware forbids it. Settled.
- Our own task queue, scheduler, or channel gateway. Hermes has these. Writing
  them again is the exact tangle this project is organised to avoid.
- Multi-user support. It is *your* assistant.
- Training a custom model.
- Rewriting a limb someone already maintains.
- A plugin system. You will invent one before you have three plugins. Wait
  until you have three.
