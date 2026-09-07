# 06 — Phase 1: Hermes (findings)

Installed and configured 2026-09-08. **One thing is blocked on you** — see the
end.

---

## What's installed

**Hermes Agent v0.21.0** (2026.8.31) — note this is *newer* than the v0.15.2
we researched, so the local-mode findings in [02-decisions.md](02-decisions.md)
hold with room to spare.

- Location: `%LOCALAPPDATA%\hermes\`
- Config: `%LOCALAPPDATA%\hermes\config.yaml`
- Secrets: `%LOCALAPPDATA%\hermes\.env`
- Personality: `%LOCALAPPDATA%\hermes\SOUL.md`
- No admin rights were needed.

It brought its own **Python 3.11.16** and its own **Node 22** — your system
Node 24 ships npm 11.12.1, which Hermes rejects, so it installed a portable
copy instead of touching yours. It also installed **ripgrep** via winget.

---

## What's configured

```yaml
model:
  default: "gemini-3.8-flash"    # the workhorse
  provider: "gemini"             # Google AI Studio direct
  # base_url:                    # unset — the gemini provider supplies its own

mcp_servers:
  cua-driver:
    command: "C:/Users/mouni/AppData/Local/Programs/Cua/cua-driver/bin/cua-driver.exe"
    args: ["mcp", "--grant", "existing-profile"]
    timeout: 180
```

`gemini-3.8-flash` is the newest Flash in Hermes's model registry, and matches
the pricing research ($0.75/$3.75 per 1M tokens, introductory through Dec 2026).

Verified two ways. `hermes config get` reads it all back correctly, and the
original was backed up to `config.yaml.divyastra-backup` first.

**Unsetting `base_url` was checked against the source, not assumed.** Hermes's
provider registry (`hermes_cli/auth.py`) supplies the endpoint for `gemini`:

```
("gemini", "Google AI Studio", "https://generativelanguage.googleapis.com/v1beta",
 ("GOOGLE_API_KEY", "GEMINI_API_KEY"), "GEMINI_BASE_URL")
```

That URL satisfies `is_native_gemini_base_url()`, so requests route through
`GeminiNativeClient` rather than the generic OpenAI wire. Leaving the old
OpenRouter `base_url` in place would have **broken** it — commenting it out was
required, not merely tidy.

Accepted key names: **`GEMINI_API_KEY`** or `GOOGLE_API_KEY`.

---

## The two open questions from the roadmap — answered

### 1. Per-task model overrides: **YES**

This was the mechanism the whole "don't burn tokens 24/7" requirement depends
on. Hermes supports it under `delegation`:

```yaml
delegation:
  model: "..."      # override model for subagents (empty = inherit parent)
  provider: "..."
  max_iterations: 250
```

Plus a `--model` flag for any single invocation.

**Interesting: Hermes recommends the inverse of what we designed.** Our plan
was *cheap by default, escalate to expensive for hard tasks*. Hermes's own
config says:

> "keep the parent on a frontier model and pin `delegation.model` to an
> inexpensive one — children carry the vast majority of tokens, so this is
> where spend is cut while planning quality stays with the frontier parent."

**Theirs is probably better**, and the reasoning is worth understanding: the
parent makes few calls but decides direction; the children do the grinding and
burn most of the tokens. Paying for good judgement once and cheap labour many
times beats the reverse.

**Not changing it yet.** We have no usage data, and guessing at tiering before
seeing real behaviour is exactly the premature complexity the rules forbid.
Revisit once there is a week of actual use.

### 2. Step / time / spend caps: **two out of three**

| Cap | Status |
|---|---|
| Failure loops | ✅ `tool_loop_guardrails` — warns after 2–3 repeats, hard-stops after 5–8 |
| Step count | ✅ `delegation.max_iterations: 250` (high, but real) |
| **Spend (money)** | ❌ **Nothing. No spend or budget cap exists in Hermes.** |

Note `hard_stop_enabled: false` but `non_interactive_hard_stop_enabled: true` —
so scheduled and gateway runs (the unattended ones, where it matters most) *do*
hard-stop. Sensible default.

**The spend gap is real** and [01-architecture.md](01-architecture.md) calls
spend caps non-negotiable. Since Hermes won't enforce it, it has to be enforced
**outside** Hermes:

1. A **Google Cloud budget alert** on the billing account (belt).
2. **Per-model rate limits / quotas** on the API key itself (braces).
3. Lower `delegation.max_iterations` from 250 to something like 40 once we know
   what a normal task costs.

None of that is urgent while running on the free Flash tier — but it must
happen before billing is ever enabled. **Added to the roadmap, not forgotten.**

---

## A safety lever worth knowing about

`platform_toolsets` restricts which tools each channel gets:

```yaml
platform_toolsets:
  cli: [hermes-cli]
  telegram: [hermes-telegram]
```

This matters for Phase 2. A task arriving from your phone — where you can't see
what's happening — should probably **not** have the same power as one you type
while watching the screen. Decide the Telegram toolset deliberately rather than
accepting the default.

---

## Personality lives in SOUL.md

`%LOCALAPPDATA%\hermes\SOUL.md` currently holds Hermes's own default persona
(be direct, no filler, match reply length to the ask — genuinely good advice).

**This is where FRIDAY goes in Phase 3.** Note the split we planned holds
exactly: `SOUL.md` is *who she is*, Kokoro is *what she sounds like*. Two
different files, changed independently. Keep the Hermes original as a reference
before overwriting.

---

## BLOCKED: needs your Google API key

Hermes has **no API key configured** — `.env` contains only default settings,
no credentials. It cannot think until it has one.

**What to do (2 minutes):**

1. Go to [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
2. Create an API key (free tier is fine — that is deliberately the default path)
3. Add one line to `%LOCALAPPDATA%\hermes\.env`:

```
GEMINI_API_KEY=your-key-here
```

Then `hermes` should start and think. Do **not** paste the key into chat, a
commit, or any file inside the project folder — `.env` in the Hermes directory
is the right home for it, and it is outside this git repo.

---

## Left undone deliberately

- **Telegram (Phase 2)** — needs a BotFather token and your numeric user ID.
  Both are yours to create; nothing useful can be done without them.
- **Gmail** — deferred at your request.
- **The Calculator-through-Hermes test** — the Phase 1 acceptance gate. It
  needs the API key, so it is the first thing to run tomorrow.
