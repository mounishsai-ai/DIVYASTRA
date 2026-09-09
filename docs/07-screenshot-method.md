# Phase 1d — the screenshot method, and what it actually costs

Measured 2026-09-09, after a real task ("open YouTube in Chrome") took **238
seconds** through the GUI agent loop while YouTube was already pinned to the
taskbar.

---

## The headline: a screenshot can cost nothing

`get_desktop_state` takes a `screenshot_out_file`. **Write the PNG to disk and
the capture costs zero context tokens.** You pay only for the parts you choose
to look at.

This inverts the Phase 1 lesson without contradicting it. Back then, suppressing
screenshots cost 14 calls -> 75 calls, because the image is a correctness input.
The fix was never *fewer* screenshots. It is:

> **Capture always. Look selectively.**

---

## Token cost is dimensional, not byte-based

Measured on a real 1920x1080 capture of this laptop:

| variant | pixels | file | Claude tok | Gemini tok |
|---|---|---|---|---|
| full PNG | 1920x1080 | 192 KB | 2765 | 1548 |
| full WebP q80 | 1920x1080 | **91 KB** | **2765** | **1548** |
| 75% JPEG | 1440x810 | 113 KB | 1555 | 1032 |
| 50% JPEG | 960x540 | 56 KB | 691 | 516 |
| 33% JPEG | 633x356 | 25 KB | 300 | 258 |
| **taskbar crop, full res** | **1920x50** | 62 KB | **128** | 258 |

**Compression is a trap.** WebP cut the file to a third and saved *nothing* —
the model is billed for pixels, not bytes. Only resizing or cropping saves money.

**Legibility floor:** 50% is comfortably readable, including taskbar icons. At
33% the text survives but taskbar icons become unidentifiable blobs.

**Cropping beats shrinking.** A full-resolution strip of just the taskbar is
128 tokens — a fifth of the 50% whole-screen shot — and it is *sharper*, not
blurrier. Shrinking loses the detail you need; cropping loses only the area you
do not.

So the pattern is two-tier:

1. **Orient** with a 50% overview when you do not know where things are (691).
2. **Act** from a full-res crop of the region you care about (~128).

---

## The run

Opening YouTube from the taskbar, with me as the brain:

`get_desktop_state` (to file, 0 tok) -> read taskbar crop (128 tok) -> `click`
-> verify. **4 calls, ~820 image tokens including verification.**

**This is NOT a like-for-like win over the 238 s run** and must not be reported
as one. I had a fresh screenshot, knew what the YouTube icon looks like, and
picked coordinates by eye in one pass. Hermes/Gemini ran cold through an agent
loop. Also: the click returned `"effect":"unverifiable"` — it worked, but the
driver did not confirm it, so a cold agent would need a verify step and possibly
a retry. Treat 4 calls as the *floor* the method allows, not the number an
autonomous run will hit.

---

## What everyone else does (checked, not assumed)

**browser-use 0.13.10** — already installed at
`%APPDATA%\uv\tools\browser-use`, shipped with Hermes. Reading its code:

- `use_vision` has three modes, and **`"auto"` includes the screenshot only when
  an action explicitly requests it.** Same conclusion as ours, arrived at
  independently.
- `llm_screenshot_size` auto-sets to **1400x850 for Claude Sonnet** — they
  resize for the model too (~1587 tokens by our formula).
- The *primary* channel is a serialized element tree with click indices. The
  screenshot is supplementary.

**Microsoft UFO2** — a hybrid detection pipeline that *fuses* Windows UI
Automation with vision-based parsing, rather than choosing one.

**UI-TARS** — reported strongest for Windows in 2026, but it is a local vision
model and needs a GPU. Ruled out by our hardware (Intel UHD), same as before.

The consensus is consistent and matches what cua-driver already gives us:

> **The tree is the action channel. Pixels are for disambiguation.**

Which is why `element_index` is preferred over pixel clicks, and why the answer
to "is loading the only solution" is no — the knowledge belongs in tools, not in
the prompt.

---

## Claude's built-in "computer use" — cannot be a limb

The Claude Code desktop app has a Computer use beta ("let Claude take control of
your screen, mouse, and keyboard"). Checked: **no such tool is exposed to this
session** — only cua-driver.

It is Claude driving the desktop with a human watching, not an API DIVYASTRA's
code can call. So it cannot be one of her limbs, whatever its quality. Useful
for *him*, irrelevant as architecture.

---

## Still open

- The 43.8 s command path and the 4-call vision path both beat 238 s, but both
  still pay agent-loop latency. A **reflex layer** — common intents matched
  locally, before any model call — is the only route to ~1 s and $0.
- She cannot talk while working. The loop is strictly blocking.

---

## The Gemini attempt: it pressed Win+Shift+S

Two attempts to have Hermes/Gemini drive the screenshot method. Neither
produced a usable number, and the second failed in a way worth keeping.

**Attempt 1 — void.** Mounish was using the voice assistant at the same time.
Two agents on one desktop make each other incoherent. Killed at 8 minutes.
Note: `hermes.exe` SURVIVED the kill of its Python parent and kept running
orphaned. Killing the caller does not stop the agent - that needs a real
cleanup path before anything runs unattended.

**Attempt 2 — the real finding.** Told to "take a screenshot of the desktop,
look at it, and click", Gemini pressed **Win+Shift+S** - the human way to take
a screenshot - instead of calling `get_desktop_state`. Then it stalled, because
a snip goes to the CLIPBOARD, not into the model's context. Two minutes, zero
clicks, two SnippingTool processes left on screen.

Partly my prompt's fault: "take a screenshot" invites the human reading. But
the structural lesson is bigger than the wording.

### Perception must not be a tool the model chooses to call

Every serious computer-use system attaches the observation **automatically on
every step**. browser-use builds the state message for the model; UFO2 fuses
UIA and vision into a provided control list; UI-TARS is trained on
screenshot-in/action-out. In none of them does the model decide *whether to
look*.

Our setup makes looking optional, and a weak model got it wrong in the most
basic way available to it. No amount of prompt text fixes a capability the
model can simply fail to invoke - it just moves the failure.

**The fix is structural:** a loop that always hands the model the current
screen and asks only for the next action. That is a small agent loop of our
own, not a Hermes prompt.

Second-order lesson: over-constraining a weak model makes it improvise worse.
Forbidding `launch_app`, terminal and browser tools left it reaching for
keyboard tricks. Constraints narrow the good paths as well as the bad ones.

**Still unmeasured:** the cost and speed of the screenshot method under Gemini.
Two attempts, two different failures, no number. Not claimed either way.
