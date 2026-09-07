# 05 — Phase 0 Findings (live, on this machine)

What actually happened when `cua-driver` was installed and driven for real on
2026-09-08. Written down because guessing at this stuff is what wastes weeks.

---

## Result: it works

`cua-driver-rs 0.24.0`, installed to `%LOCALAPPDATA%\Programs\Cua\cua-driver\bin`.

```
[ok] binary: cua-driver 0.24.0 (x86_64-windows)
[ok] interactive session: session 2 has an attached interactive desktop
[ok] UI Automation: CoCreateInstance(CUIAutomation) succeeded
[ok] EnumWindows visible: 6 windows
```

**Proof it drives real apps:** launched Calculator, read its 39-element UIA
tree, clicked `Seven` → `Multiply by` → `Six` → `Equals` **by accessibility
label**, then read back `Display is 42`.

Note what that is *not*: no screenshots, no pixel guessing, no vision model. It
addressed buttons by their names. That is why it costs almost no tokens and
does not break when the window moves.

---

## Answering "will it take over my main screen?"

You said taking over the screen was acceptable. The actual behaviour is better
than that, and you get both:

- **A visible agent cursor is ON by default.** Every session gets its own
  overlay cursor showing where the agent is acting — so you can watch it work.
- **Your real mouse is never moved.** You can keep using the laptop.
- **`bring_to_front`** raises a window to the foreground when you *want* it
  visible, or when an app refuses background input.

One wrinkle worth knowing: a pure accessibility action makes the overlay cursor
**pulse briefly** rather than glide, so it is easy to miss. For a visible demo,
do a pixel click or `move_cursor` first.

---

## Things that tripped us up (and the fix)

**1. Windows 11 built-in apps are UWP packages.**
`notepad.exe` in System32 is a ~7 KB stub that exits immediately. Launch them
by AUMID instead:

```
Microsoft.WindowsNotepad_8wekyb3d8bbwe!App
Microsoft.WindowsCalculator_8wekyb3d8bbwe!App
```

**2. Typing into UWP/XAML apps needs the tree, not keystrokes.**
`type_text(pid, text)` silently fails on modern Notepad/Calculator/Settings —
their input dispatcher ignores posted `WM_CHAR`. You must call
`get_window_state` first and pass `element_index` + `window_id`, which routes
through UIA `ValuePattern.SetValue`. Legacy Win32 apps still take the simple
path.

**3. One pid can own several windows.**
`bring_to_front` on pid alone was refused with `ambiguous_window_target` —
Calculator and Settings are both hosted by `ApplicationFrameHost.exe`. Always
pass `window_id`.

**4. Snapshot tokens expire.**
`element_token` values (`s00000002:22`) are bound to one snapshot. Re-snapshot
before each action. The driver fails closed rather than clicking the wrong
thing — good behaviour, but plan for it.

**5. `health_report` is blocked in standard permission mode**
("no reviewed risk classification"). `doctor` gives you what you need. Only
loosen the permission mode if something real requires it.

**6. CLI JSON must be piped, not passed as an argument.**
PowerShell mangles inline JSON. The working form:

```powershell
'{"pid":19476,"window_id":1048766}' | & cua-driver call get_window_state
```

---

## The near-miss — read this one

`launch_app` for Notepad **returned an already-running window** titled:

```
*so my clg conduting project exhibit - Notepad
```

The leading `*` means **unsaved changes**. The next step in the test would have
typed into it and corrupted real coursework notes. The test was switched to
Calculator instead.

**This is risk #2 from [04-costs-and-limits.md](04-costs-and-limits.md)
happening within ten minutes of install, in the most boring way possible** —
not a rogue AI, just a tool opening a document that already had your work in it.

**Rules adopted as a result:**
- `launch_app` may hand back an **existing** window with existing state. Always
  read the title before acting.
- A title beginning with `*` means unsaved work. **Never type into it.**
- Test on stateless apps (Calculator) or on a scratch file you created.
- Never demo on a document you did not open yourself.

---

## Housekeeping on this machine

- **Autostart:** `cua-driver-serve` is registered as a Scheduled Task at
  `RunLevel=Highest` and runs at every logon. `cua-driver autostart status` /
  `disable` / `kick`. It needed one UAC prompt to register; it runs silently
  after.
- **Telemetry is ENABLED by default.** Pseudonymous install ID and content-free
  usage metadata — no prompts, arguments, screen contents, or file paths.
  Benign, but it is on unless you turn it off:
  `cua-driver telemetry disable`
- **Skill pack installed** and linked into Claude Code at
  `~/.claude/skills/cua-driver`, so Claude Code knows the correct usage
  patterns without being told each time.

---

## Config that resulted

`.mcp.json`, committed:

```json
{
  "mcpServers": {
    "cua-driver": {
      "command": "C:/Users/mouni/AppData/Local/Programs/Cua/cua-driver/bin/cua-driver.exe",
      "args": ["mcp", "--grant", "existing-profile"]
    }
  }
}
```

MCP servers load at session start, so Claude Code must be **restarted** before
the `cua-*` tools appear.

---

## Still unverified

- [x] ~~The `browser_*` tools attaching to the real logged-in Chrome profile.~~
      **Verified** — see the browser section below.
- [ ] Whether typing into a normal (non-UWP) app is as smooth as Calculator was.
- [ ] Gmail — decided but not installed. Needs a standalone MCP server.

---

## Browser limb — verified 2026-09-08

Navigated to Wikipedia through the real logged-in Chrome and read the page
back: **"From today's featured article — George Krugers (1890–1964), a
filmmaker active in the Dutch East Indies."** No Playwright involved. D3 holds.

### Getting there took three real obstacles

**1. The Chrome profile picker blocks attachment.**
`browser_prepare` refused with `browser_wrong_target_refused: did not expose a
stable native tab topology`. Cause: Chrome opened `chrome://profile-picker/`,
which has no tabs to bind to. "Show on startup" is ON, so **every** plain
Chrome launch hits this.

**Fix — launch straight into a profile, skipping the picker:**

```
C:\Program Files\Google\Chrome\Application\chrome.exe --profile-directory=Profile 8
```

Note: if Chrome is **already running**, a new launch is swallowed by the
existing instance and the argument is ignored. Close Chrome first.

**2. Clicking the picker didn't work.** A background click on a Chromium
surface returned `effect: unverifiable` and nothing happened — Chromium content
drops synthetic background events, exactly as the tool docs warn. Not worth
fighting; the launch flag above is the right answer.

**3. The first `browser_prepare` failed, the second succeeded.** The driver
automates Chrome's remote-debugging setup page; on a cold-started Chrome it
reported `the exact Google Chrome remote-debugging setup page did not become
ready`. **Retrying once after the browser settled worked.** Treat a first
failure as a timing issue, not a dead end.

**A stray tab may appear.** After setup, Profile 8 had an extra tab open at
`http://0.0.0.8/` — an artifact of the driver typing into the address bar while
enabling remote debugging. Harmless; just close it. Worth knowing so it isn't
mistaken for something sinister.

### Which profile — and the privacy call

This laptop has **nine** Chrome profiles, most belonging to other people
(Devineni Akhil, Durgi Suvarna rani, Irfan khan Pathan, Jaison Reddy, Madara
Uchiha). Attaching a DevTools endpoint gives the agent whatever that profile is
logged into, so this is not a detail to guess at.

**Decision: `Profile 8` — "Mounish Sai".** Chosen by Mounish. Note there are
two Mounish profiles and the picker is misleading: `Profile 4` is *named*
"Batman" with the account "Mounish sai", while `Profile 8` is named "Mounish
Sai". `Profile 8` sits at the **bottom of the picker and needs scrolling**,
which is why it wasn't in the first screenshot.

Map profile directories to names any time with:
`%LOCALAPPDATA%\Google\Chrome\User Data\Local State` → `profile.info_cache`.

**Never attach to a profile that isn't Mounish's.**

### Cleanup owed

`browser_prepare` reported `changed_preferences: true` and
`enabled_remote_debugging: true` on Profile 8. That setting **persists**. If
DIVYASTRA is ever abandoned, turn it back off — a profile with remote debugging
enabled is a profile any local process can drive.

---

## The expensive mistake — bounding snapshots

An **unscoped** `get_browser_state(semantic_v2)` on the Wikipedia main page
returned ~25,000 tokens and was truncated. One call. The page has 1,095 nodes
and the response enumerates every ref.

**Rule: never take an unscoped semantic snapshot of a content-heavy page.**
Always bound it:

- `query: "..."` — projects to matching nodes plus ancestors. Cheapest.
- `scope_ref: "p1:0"` — one subtree only.
- `continuation` — page through a large snapshot deliberately.

Beware: a *too-narrow* query is also wrong. `query: "From today's featured
article"` matched only the heading, not the article body, costing a second
call. Aim at a distinctive phrase **inside** the content you want.

This matters far beyond tidiness — it is the difference between a task costing
a fraction of a cent and costing several cents, every time. It is the single
biggest token lever in the whole browser limb.

---

## Gmail — decided, not yet built

**Mailbox: `mounishsai.ai@gmail.com`** (professional). Mounish's call.

> **Privacy note, recorded at his request: remove this access later.**
> When DIVYASTRA is no longer being actively used, revoke the OAuth grant at
> [myaccount.google.com/permissions](https://myaccount.google.com/permissions)
> and delete the stored token. Do not leave a standing mail grant behind.

**Start read-only.** Add send only when there is a real reason, and require
confirmation before anything leaves the outbox.

**Important:** the `claude.ai Gmail` connector in Claude Code is **not** the
right limb for DIVYASTRA. It works only inside Claude — Hermes cannot use it.
DIVYASTRA needs a **standalone Gmail MCP server** with its own Google Cloud
OAuth client. The connector can satisfy the Phase 0 checkbox, but the real limb
is separate work.
