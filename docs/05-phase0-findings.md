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

- [ ] The `browser_*` tools attaching to the real logged-in Chrome profile.
- [ ] Whether typing into a normal (non-UWP) app is as smooth as Calculator was.
- [ ] Gmail — not yet installed.
