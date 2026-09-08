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
- [x] **Browser verified** — navigated to Wikipedia and read back today's
      featured article (George Krugers), through the **real logged-in Chrome
      profile**. The "stretch" goal was met outright, so Playwright is dropped.
- [~] *"summarise my three most recent emails"* — **deferred by Mounish.**
      Mailbox decided (`mounishsai.ai@`, read-only, revoke later); needs a
      standalone Gmail MCP server, not the claude.ai connector.
- [x] Written down: what each limb cannot do — see
      [05-phase0-findings.md](05-phase0-findings.md).

**Phase 0 is closed** apart from the deferred Gmail limb, which nothing else
depends on.

**Value even if you stop here:** a genuinely useful desktop assistant.

---

## Phase 1 — Hermes as the spine

Hermes replaces what used to be Phases 2, 3 and 4 of this plan. See the D2
reversal in [02-decisions.md](02-decisions.md) for why.

**Steps**
1. Install Hermes natively on Windows. It is **self-contained but not small** —
   it brings its own Python 3.11, Node, MinGit (~45 MB), ripgrep and ffmpeg
   into `%LOCALAPPDATA%\hermes`. Expect a few hundred MB. No WSL, no Docker.
2. Configure **Gemini Flash** as the default model.
3. Register `cua-driver` as an MCP server inside Hermes:
   `cua-driver mcp-config --client hermes`
4. Confirm the same Calculator task works *through Hermes* rather than through
   Claude Code.

**Acceptance** — see [06-phase1-hermes.md](06-phase1-hermes.md)
- [x] Hermes **v0.21.0** installed natively. No admin, no WSL, no Docker.
- [x] The model is Gemini (`gemini-3.8-flash`), set in config, not code.
- [x] `cua-driver` registered as an MCP server inside Hermes.
- [x] **Per-task model overrides: YES** — `delegation.model` / `--model`.
      Tiering is config. (Hermes recommends the *inverse* of our design:
      frontier parent + cheap children. Theirs is probably better. Not changing
      it until there is real usage data.)
- [x] Step + failure-loop caps exist (`tool_loop_guardrails`,
      `delegation.max_iterations`).
- [x] **Spend cap** — Hermes has none, so it is enforced outside: a gross-spend
      GCP budget alert now exists ("DIVYASTRA credit burn").
- [x] **Hermes completed a real desktop task** — launched Calculator, clicked
      `8 x 9 =` through the accessibility tree, read back **72**. Full chain:
      Hermes -> Gemini on Vertex -> cua-driver -> Windows.
- [x] Nothing from Phase 0 had to be rebuilt.

**PHASE 1 IS GREEN.** But see Phase 1b — it cost $0.29 to click four buttons.

---

## Phase 1b — Make repeated tasks free (revised after measurement)

> **The first version of this phase was wrong.** It assumed cost came from
> oversized prompts, and proposed trimming tool schemas and toolsets. Measured:
> **no effect.** Worse, the task cost varies **2.4x run to run**, so single-run
> A/B testing cannot detect anything. Full log in
> [06-phase1-hermes.md](06-phase1-hermes.md). Cost of finding out: ~$2.30.

**What the measurement actually showed:** 77% of spend is *uncached input* — the
conversation tail re-sent on every call. Cost scales with **number of turns**,
not prompt size. The static prefix was already cached at a tenth the rate.

**So: don't make turns cheaper. Have fewer turns.**

For a personal assistant this is very winnable, because the same tasks repeat
daily. The agent loop should be for *figuring something out the first time*;
after that it should be a recipe.

> **Second correction, same day.** The step below originally said "record a
> trajectory and replay it for free". Reading `RECORDING.md` properly kills
> that: **`replay_trajectory` cannot replay accessibility-tree actions.**
> `element_index` is assigned fresh per snapshot and keyed on `(pid,
> window_id)`, both of which change between sessions, and read-only tools like
> `get_window_state` are not recorded so replay cannot re-emit the snapshot.
> Only **pixel clicks and keyboard input** replay — and pixel-clicking is
> precisely the brittle approach rejected in D1. The docs say it plainly: use
> it "as a regression artifact rather than a re-driving script."

**So the honest answer is a three-way split by how often a task runs:**

| How often | Approach | Model cost |
|---|---|---|
| Once / rarely | agent loop, let it figure things out | ~$0.30–0.70 |
| Occasionally, varying | **Hermes skill** — a written procedure so it doesn't re-explore | reduced, not zero |
| **Daily, identical** | **write a real limb** — deterministic code, no LLM | **$0** |

The third row is the actual answer to "it costs too much", and it is what
`capabilities/` was always for. **If you do a task every single morning, the
right fix is code, not a cheaper prompt.** Checking a portal on a schedule
should not involve a language model re-deriving how to click a login button.

**Steps**
1. **Write one Hermes skill** for a task you actually repeat, and measure
   whether it shortens the run. This is the cheapest thing to try.
2. **Pick one genuinely daily task** and write it as a deterministic limb —
   a small MCP server, plain code, no model in the loop.
3. **Set expectations honestly:** the agentic path costs what it costs. Budget
   for roughly $0.30–0.70 per novel desktop task and do not build habits that
   run it in a loop.
4. Revisit per-turn tuning **only** with 5+ runs per condition, given the 2.4x
   variance — **and only counting runs that produced the correct result.** A
   failed run is shorter and cheaper; comparing it to a successful one produced
   a bogus "3-5x win" once already (see the keyboard retraction in
   [06-phase1-hermes.md](06-phase1-hermes.md)).
5. **Assume the agentic path costs $0.30–0.50 per novel desktop task.** Nothing
   tried has beaten the plain accessibility-tree clicking baseline.

**Acceptance**
- [ ] One repeated task runs with **no model calls at all**.
- [ ] A written rule for which of the three rows a new task belongs in.
- [ ] The agentic path still works for novel tasks.

**Already banked from attempt 1 (keep, even though cost-neutral):**
- `mcp_servers.cua-driver.tools.include` — 57 tools cut to 18. No cost change,
  but the agent can no longer reach `clipboard_read`, `kill_app`, `drag` or the
  recording tools by accident. Safety win, so it stays.
- Don't run Hermes with its cwd inside this repo.

---

## Phase 1c — Browser profile enforcement (before any real browser use)

**Open flaw** (see [05-phase0-findings.md](05-phase0-findings.md)): the browser
limb binds to whatever Chrome is running, so the deliberate choice of
`Profile 8` is documented but unenforced. On a laptop with nine profiles, most
belonging to other people, that is a privacy bug, not a nicety.

- [ ] Launch Chrome with `--profile-directory=Profile 8` and track that pid.
- [ ] Verify the attached profile after `browser_prepare`; refuse on mismatch.
- [ ] Fail closed — never fall back to an arbitrary browser.

Also note: Chrome's **"Allow remote debugging?"** dialog needs a human click and
no agent can click it. Unattended browser work requires consent pre-granted.

---

## Phase 2 — Her voice (FRIDAY)

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

## Phase 3 — Twilio: it actually calls you

**Read the India rules in [02-decisions.md](02-decisions.md) D6 first.** Short
version: rent an **international** number (Indian numbers cannot place these
calls), keep the volume low, and only ever call your own verified number.

**Steps**
1. Twilio trial; verify your own mobile as a caller ID.
2. Configure Hermes's built-in Twilio gateway.
3. Call only on tasks you explicitly mark as call-worthy — everything else
   reports back through whatever channel asked.

**Acceptance**
- [ ] A finished task triggers a real ringing call, and you hear the result.
- [ ] Only your verified number is ever dialled — enforced, not intended.
- [ ] A per-day call cap exists and is enforced.
- [ ] Cost per call is measured and written down.

---

## Phase 4 — Scheduling and initiative

Much of this is Hermes cron; the work is deciding *policy*, not building it.

**Steps**
1. Recurring tasks via Hermes cron.
2. Watchers: new mail matching a rule, a deadline nearing.
3. Quiet hours.
4. **The spend cap Hermes doesn't provide** — a Google Cloud budget alert plus
   quotas on the API key, and lower `delegation.max_iterations` from its
   default 250 once a normal task's cost is known.

**Acceptance**
- [ ] *"Every day at 8 pm, check the portal for new assignments and tell me."*
- [ ] Idle for 24 h costs **zero** tokens. Verify in the provider console.
- [ ] **No scheduled task invokes the agent loop.** A cron job that fires every
      morning is by definition the daily-identical row from Phase 1b — it should
      be a deterministic limb, not an LLM re-deriving the same clicks at
      $0.30–0.70 a time. Treat "cron calls the agent" as a design error.
- [ ] **The billing-disabled week.** Turn off GCP billing and use her normally
      for a week on the free Flash tier alone. If she still works, DIVYASTRA
      survives the day the $300 expires. If not, fix it now — far cheaper to
      learn in month one than month four.

---

## Phase 5 — Custom limbs

Only now, when the assistant already works, do we write our own code.

1. `capabilities/files` — read/write inside an allow-listed folder only.
2. `capabilities/college` — timetable, portal, deadlines.

**Acceptance**
- [ ] The files limb refuses a path outside its allow-list.
- [ ] Each limb works from Claude Code's MCP client *before* Hermes uses it.

---

## Phase 6 — WhatsApp (remote access)

**Deliberately last of the useful phases.** Local first: get her working at the
laptop, then make her reachable from the phone.

Re-read D7 in [02-decisions.md](02-decisions.md) before starting — unofficial
WhatsApp Web bridges violate WhatsApp's Terms of Service and accounts get
banned. Hermes ships both an unofficial `whatsapp` gateway and an official
`whatsapp-cloud` one; prefer the official route, and never use the primary
number on the unofficial one.

**Acceptance**
- [ ] A voice note from the phone runs a task on the laptop and replies.
- [ ] Only your number is accepted.
- [ ] Nothing else in the system changed to add it.

---

## Phase 7 — Gestures (stretch)

Only after everything above is green.

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
- A web dashboard. Voice and the terminal are the UI.
- **Telegram.** Dropped 2026-09-08 — WhatsApp is the only messaging channel,
  and only later. Do not re-add it "because it is easier".
- A local LLM. The hardware forbids it. Settled.
- Our own task queue, scheduler, or channel gateway. Hermes has these. Writing
  them again is the exact tangle this project is organised to avoid.
- Multi-user support. It is *your* assistant.
- Training a custom model.
- Rewriting a limb someone already maintains.
- A plugin system. You will invent one before you have three plugins. Wait
  until you have three.
