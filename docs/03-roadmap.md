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
1. `irm https://cua.ai/driver/install.ps1 | iex` — then `cua-driver doctor`.
2. `claude mcp add --transport stdio cua-driver -- cua-driver mcp`
3. Add Playwright MCP. **Plain pages first.**
4. *Then* the logged-in profile — this is a separate, fiddlier step. Playwright
   **cannot** attach to a normally-running Chrome. You must either start Chrome
   with `--remote-debugging-port=9222` and connect over CDP, or point Playwright
   at a copy of your user-data directory. If this fights you, **nothing is
   broken** — it is one launch flag, and it is not a Phase 0 blocker.
5. Add a Gmail MCP server; complete Google OAuth.
6. Commit `.mcp.json`.

**Acceptance**
- [ ] `cua-driver doctor` reports a healthy interactive session.
- [ ] From Claude Code: *"open Notepad and type hello"* — it works, **and your
      mouse pointer never moves.**
- [ ] From Claude Code: *"open wikipedia.org and tell me the featured article"*
      — any public page. This is the real gate.
- [ ] From Claude Code: *"summarise my three most recent emails."*
- [ ] Written down: one thing each limb **cannot** do (you will hit these).

*Stretch, not a gate:* the same browser task against your logged-in profile.

**Value even if you stop here:** a genuinely useful desktop assistant.

---

## Phase 1 — Her voice

**Why before the core:** it is self-contained, it has zero dependency on
anything else, and hearing your own assistant speak is the thing that keeps a
side project alive.

**Steps**
1. Kokoro-82M locally. Audition voices, pick the FRIDAY one.
2. `voice/tts.py` exposing exactly `speak(text)`.
3. whisper.cpp, CPU. `voice/stt.py` exposing `listen() -> str`.
4. openWakeWord on "Divyastra".
5. `voice/personality.md` — who she is. Versioned, separate from the voice.

**Acceptance**
- [ ] `speak("Systems online.")` sounds right to you.
- [ ] Round-trip: say something → text within ~2 s.
- [ ] Wake word runs one hour with **zero** false triggers and near-zero CPU.
- [ ] Swapping the TTS engine would touch **only** `voice/tts.py`.

---

## Phase 2 — The core (first real code)

Now DIVYASTRA becomes a program instead of a config.

**Steps**
1. `Task` object. One definition, used by everything.
2. Persistent queue (JSON file is fine).
3. `core/models.py` — the one adapter. Gemini first.
4. The agent loop, as an MCP client, with **step / time / spend limits**.
5. Facts memory: one Markdown file.
6. Wire the voice channel in.

**Acceptance**
- [ ] Speak a task → she does it on the desktop → she reports back by voice.
- [ ] A deliberately impossible task stops cleanly at the step limit.
- [ ] Kill and restart mid-task: the queue survives.
- [ ] Every model call goes through `models.py`. Grep proves it.
- [ ] **The billing-disabled week.** Turn off GCP billing and use her normally
      for a week on the free Flash tier alone. If she still works, DIVYASTRA
      survives the day the $300 expires. If she doesn't, fix it *now* — this is
      far cheaper to learn in month one than month four. See
      [04-costs-and-limits.md](04-costs-and-limits.md).

---

## Phase 3 — The phone channel

**This is the feature you actually described.** Task from class → done at home.

**Steps**
1. Telegram bot via BotFather. Lock it to your user ID only.
2. Text messages in → Task.
3. Voice notes in → whisper → Task.
4. Replies out as text **and** a Kokoro voice note.
5. Long tasks: acknowledge immediately, notify on completion.

**Acceptance**
- [ ] Send a voice note from your phone; the laptop does it; a voice note comes
      back.
- [ ] Anyone else messaging the bot is refused.
- [ ] Laptop asleep → task waits → runs when it wakes.
- [ ] The core needed **no changes** to gain this channel. *(If it did, the
      layering is wrong — fix that before continuing.)*

---

## Phase 4 — Triggers, schedules, initiative

Turning a tool into an assistant: she acts without being asked.

**Steps**
1. Scheduler: cron-like, plus one-shot ("tomorrow 7 am").
2. Watchers: new mail matching a rule, a file appearing, a deadline nearing.
3. Proactive notification with a spend budget per day.
4. A "quiet hours" setting.

**Acceptance**
- [ ] *"Every day at 8 pm, check the portal for new assignments and tell me."*
- [ ] Idle for 24 h costs **zero** tokens. Verify in the provider console.
- [ ] Daily spend cap is enforced, not just configured.

---

## Phase 5 — Wider reach

**Steps**
1. WhatsApp MCP — **on a secondary number.** Re-read D7 in
   [02-decisions.md](02-decisions.md) before starting.
2. `capabilities/files` — read/write in an allow-listed folder only.
3. `capabilities/college` — timetable, portal, deadlines.

**Acceptance**
- [ ] WhatsApp works and the primary number was never used.
- [ ] The files limb refuses a path outside its allow-list.

---

## Phase 6 — Gestures (stretch)

Only after 0–5 are green.

1. MediaPipe Hands on the webcam, CPU.
2. Pinch → click, at first behind a hotkey so it is never always-on.
3. Two or three gestures maximum.

**Acceptance**
- [ ] Pinch-to-click works at a comfortable distance.
- [ ] **It was added as a channel and the core did not change.** This is the
      real test of the whole architecture.

---

## Deliberately NOT doing

Written down so they stop being tempting:

- A vector database / RAG memory. A Markdown file of facts is enough for one
  person. Revisit only when it demonstrably fails.
- A web dashboard. Telegram is the UI.
- A local LLM. The hardware forbids it. Settled.
- Multi-user support. It is *your* assistant.
- Training a custom model.
- Rewriting a limb someone already maintains.
- A plugin system. You will invent one before you have three plugins. Wait
  until you have three.
