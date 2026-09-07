# 04 — Costs, Limits & Risks

The honest version. Read before building anything that assumes money exists.

---

## What you actually have

| Resource | Reality | Expires |
|---|---|---|
| Claude Code Pro | **the workshop** — builds DIVYASTRA, cannot run inside it | ongoing |
| Claude Agent SDK credit | **$20/month**, included with Pro, **no rollover** | monthly |
| Google Cloud credit | **$300**, but **only 90 days** | ~2026-12-06 |
| Gemini free tier | Flash / Flash-Lite, rate-limited, **permanent** | never |
| Local CPU | whisper.cpp, Kokoro, openWakeWord, MediaPipe | free forever |
| Hardware | Intel UHD graphics, 15.7 GB RAM, **no NVIDIA GPU** | — |

### The trap in that table

**The $300 is a 90-day runway, not a budget.** Note the expiry date above. If
DIVYASTRA is designed around it, DIVYASTRA dies on day 91.

**Therefore, the design rule:** the **free Gemini Flash tier is the default
path**, and it must remain sufficient for everyday use. Credits are for bursts,
experiments, and heavy days — never for baseline operation.

Test this deliberately: at some point, run a full week with billing disabled
and see whether she still works. If she doesn't, the design is wrong, and you
would rather learn that in month one than in month four.

**The $20/month Claude credit is the more durable resource.** It does not
expire and it renews. It is small, so spend it only on Tier 3 — genuinely hard
multi-step desktop reasoning where Flash visibly fails.

---

## Rules that keep spend near zero

1. **Idle costs nothing.** Wake word, STT, TTS, and clicking are all local.
   If an idle day ever shows tokens, something is wrong — investigate.
2. **Every agent loop has three caps**: max steps, max wall-clock, max spend.
   Not configurable-in-theory — actually enforced.
3. **A daily budget ceiling.** When hit, she says so and stops.
4. **Screenshots are expensive.** Images cost far more than text. Prefer the
   accessibility tree; take a screenshot only when the tree genuinely fails.
   This is a cost decision as much as a reliability one.
5. **Log every call's token count** from day one. You cannot control what you
   cannot see, and adding this later is annoying.

---

## Risks, ranked by how much they would actually hurt

### 1. WhatsApp account ban — HIGH impact
Unofficial WhatsApp Web bridges violate WhatsApp's Terms of Service. Accounts
using them can be banned. Losing your primary WhatsApp as a student is a real,
material loss.

*Mitigation:* secondary number only, and it is scheduled for Phase 5 so nothing
else depends on it. Your account, your call — but decide it knowingly.

### 2. An agent doing something destructive — HIGH impact
It can click anything you can click. A confused model can delete files, send a
half-written email, or click "confirm" on something that matters.

*Mitigation:* require confirmation for anything irreversible — sending,
deleting, paying, posting. Allow-list folders for the files limb. Consider a
separate Windows user account. Never run it elevated: Windows UIPI already
blocks admin windows from a normal process, and that is a **feature** — do not
"fix" it by running as administrator.

### 3. Credentials leaking — HIGH impact
The bot has your mail, your browser session, your messages.

*Mitigation:* `.env`, never committed. `.gitignore` before the first commit.
Lock the Telegram bot to your user ID alone. Do not let the model type
passwords — `cua-driver` already blocks some of this; use browser autofill.

### 4. Free-tier rate limits mid-task — MEDIUM
Flash free tier is rate-limited per minute and per day.

*Mitigation:* retry with backoff, then fall back to paid Flash, then tell you.
Never fail silently.

### 5. Silent breakage — MEDIUM
Windows updates, Chrome updates, WhatsApp changes. Something will break.

*Mitigation:* this is what the one-limb-per-folder rule buys you — breakage
stays local. Keep the Phase 0 acceptance tests runnable forever as a smoke test.

### 6. Scope creep — the most likely killer
Not a technical risk, but the one that actually ends projects like this.

*Mitigation:* the phase gates, and the "Deliberately NOT doing" list in
[03-roadmap.md](03-roadmap.md). When you want to build something not in the
current phase, write it in the roadmap instead. That is the whole discipline.

---

## Licence notes

- `cua-driver` (trycua/cua) — MIT. Fine.
- Hermes Agent — MIT. Fine (reference only).
- Kokoro-82M — Apache-2.0. Fine.
- whisper.cpp / Whisper weights — MIT. Fine.
- **openWakeWord — code Apache-2.0, but pretrained models are CC-BY-NC-SA 4.0:
  non-commercial.** Fine for personal use. If DIVYASTRA is ever distributed,
  retrain or replace.
- OmniParser — CC-BY-4.0 (not used for now; noted in case UFO2 is revisited).

---

## Things to verify, not assume

Written here because assuming any of these would waste days:

- [ ] `cua-driver` actually works on **Windows 11 Home** with your apps —
      Phase 0 proves this before anything is built on it.
- [ ] Chrome can be driven by Playwright **while using your logged-in profile**
      (may need Chrome started with a debugging flag).
- [ ] Gemini free-tier limits are enough for a realistic day.
- [ ] Kokoro latency on **your** CPU is short enough to feel conversational.
- [ ] Telegram voice notes arrive in a format whisper.cpp reads directly
      (likely OGG/Opus — may need ffmpeg).
