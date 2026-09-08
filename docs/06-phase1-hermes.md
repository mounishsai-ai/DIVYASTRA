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

**Vertex AI, not AI Studio** — decided by Mounish 2026-09-08 to use the $300
Google Cloud credit. See D4 in [02-decisions.md](02-decisions.md).

```yaml
model:
  default: "google/gemini-3.8-flash"   # Vertex needs the publisher prefix
  provider: "vertex"
  # base_url:                          # unset — the adapter builds it
```

`.env` (in the Hermes directory, outside this repo):

```
VERTEX_CREDENTIALS_PATH=C:\Users\mouni\AppData\Local\hermes\divyastra-vertex-key.json
VERTEX_PROJECT_ID=divyastra-agent-37057
VERTEX_REGION=global
```

### Dedicated GCP project (migrated 2026-09-08)

DIVYASTRA got its **own** Google Cloud project at Mounish's instruction — no
sharing with `placement-agent` or anything else.

| | |
|---|---|
| Project | `divyastra-agent-37057` ("DIVYASTRA"), number `65127856755` |
| Service account | `divyastra-vertex@divyastra-agent-37057.iam.gserviceaccount.com` |
| Role | `roles/aiplatform.user` only |
| Key | `%LOCALAPPDATA%\hermes\divyastra-vertex-key.json`, id `13adbcacd231a134c92f60e4dbecdc9b81622bd5` |

**The billing quota fight.** The billing account allows only **3 projects**, and
all 3 were taken. Mounish chose to free the slot from `placement-agent-22587`.
**Billing was unlinked, not deleted** — that frees the quota, is reversible in
one command, and destroys nothing:

```
gcloud billing projects link placement-agent-22587 --billing-account=01573C-ED4F11-44CBC4
```

(Relinking would need a slot free again.)

**Cleanup done.** The key previously created on `jarvix-vertex` was **revoked**
and its local file deleted; that service account has no user-managed keys again.
The budget alert was repointed at the new project.

> **To revoke DIVYASTRA's access:**
> ```
> gcloud iam service-accounts keys delete 13adbcacd231a134c92f60e4dbecdc9b81622bd5 --iam-account divyastra-vertex@divyastra-agent-37057.iam.gserviceaccount.com
> ```

**One gotcha:** a new IAM binding takes ~20–40 s to propagate. The first call
after granting a role returns `403 aiplatform.endpoints.predict denied`. That is
not a misconfiguration — wait and retry. Verified working immediately after.

`mcp_servers.cua-driver` unchanged from Phase 0.

### Three things that had to be got right

**1. The model name needs a `google/` prefix on Vertex.**
Plain `gemini-3.8-flash` is rejected: *"Malformed publisher model … expected
`<publisher>/<model>`"*. This differs from AI Studio, where the bare name works.

**2. `global` region, not a regional one.** Gemini 3.x is global-only, and
`global` uses the bare `aiplatform.googleapis.com` host rather than
`<region>-aiplatform...`. Already Hermes's default.

**3. A service account is required — user ADC will NOT work.**
Subtle, and would have cost hours. Vertex with *user* credentials requires an
`x-goog-user-project` header, and **Hermes does not send one** — it passes a
bare bearer token to a standard OpenAI client. Proven directly:

- ADC token alone → `403 PERMISSION_DENIED … requires a quota project`
- Same token + `x-goog-user-project` header → works
- `gcloud auth application-default set-quota-project` does **not** fix it — the
  raw token doesn't carry the quota project

Service accounts belong to the project, so they need no such header. Key is
stored outside this repo with permissions restricted to your Windows account —
see the dedicated-project table above for the current identity.

---

## PHASE 1 PASSED — the whole stack works

```
hermes -z "…open Calculator and compute 8 x 9 via the accessibility tree…"
```

Hermes replied:

> The final number shown on the Calculator display is **72**.
> Invoked buttons via the UIA accessibility tree in the background:
> Eight, Multiply by, Nine, Equals. Verified display text: `Display is 72`.

That is the full chain, with no help from Claude Code:
**Hermes (hub) → Gemini 3.8 Flash on Vertex (thinking) → cua-driver over MCP
(hands) → Windows.**

Useful discovery: **`hermes -z "prompt"`** is one-shot mode, and
`--usage-file PATH` writes exact token and cost accounting. That is how every
cost figure below was measured rather than guessed.

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

## THE REAL PROBLEM: cost per task

Measured, not estimated:

| Run | API calls | Cost |
|---|---|---|
| Trivial reply ("say DIVYASTRA ONLINE") | 1 | **$0.0092** |
| Calculator: 8 x 9 via accessibility tree | 33 | **$0.29** |

**Twenty-nine cents to click four buttons.** At that rate the ~$290 credit is
roughly **1,000 tasks** — a real day of use would drain it in weeks, not months.

> **Caveat: these are Hermes's own estimates**, computed from a bundled pricing
> snapshot (`cost_source: official_docs_snapshot`), not from the billing
> console. The run reported 929K *cache-read* tokens, which bill far below the
> normal input rate — if Hermes priced those at full rate, the true cost is
> lower. A rough check against billed tokens alone (289K in x $0.75/1M + 1.5K
> out x $3.75/1M ≈ $0.22) lands close, so the order of magnitude holds and the
> fix below is right either way. **Confirm against the GCP billing console in a
> day or two before quoting $0.29 as fact.**

### Why

`hermes prompt-size` shows a **25 KB system prompt + 35 KB of tool schemas for
the 20 built-in tools alone** — before cua-driver, which adds **~57 more tools**.
That whole payload is re-sent on every one of the 33 calls. Prompt caching is
working (929K cached tokens read) and it still cost $0.29.

So the cost driver is not thinking. It is **tool-schema bloat, plus
accessibility trees accumulating in context**.

### Fixes, by expected payoff

1. **Narrow cua-driver's tools with a capability manifest**
   (`--permission-mode bounded --capability-manifest ...`). We use maybe 10 of
   its 57 tools. This cuts cost *and* shrinks the blast radius — one change,
   both benefits.
2. **Drop unused toolsets per run** with `-t`. `file`, `delegation`,
   `code_execution`, `browser-use`, `tts`, `vision` are ~20 KB of schema a
   desktop task never touches.
3. **Bound accessibility snapshots** — `max_elements`, `query`. The same lesson
   already learned on the browser side in
   [05-phase0-findings.md](05-phase0-findings.md).
4. **`--reasoning` level.** Gemini 3.x spends real tokens thinking — 3,139
   reasoning tokens in the Calculator run.

### Phase 1b attempt 1 — FAILED, and the failure is the finding

Five runs of the *identical* Calculator task, one variable changed at a time:

| # | Condition | Cost | API calls |
|---|---|---|---|
| 1 | baseline | $0.290 | 33 |
| 2 | tool filtering (−84 KB) + neutral cwd (−7.5 KB) | $0.290 | 30 |
| 3 | + `compression.threshold_tokens: 40000` | $0.503 | 54 |
| 4 | + prompt telling it to skip screenshots | $0.706 | 60 |
| 5 | **control: identical config and prompt to #2** | **$0.472** | 39 |

**Run 5 is the important one.** Same config, same prompt as run 2, and the cost
went from $0.290 to $0.472. Nothing changed but the dice.

**The task cost varies 2.4x run to run.** Every "result" above is inside the
noise. The A/B method was invalid — you cannot detect a 20% improvement when the
noise is 140%. Published work saw the same thing: *"runs on the same task varied
by as much as 30x in total token use."*

**Cost of learning this: about $2.30 of credit.** Cheap for the lesson.

### What each attempt actually taught

- **Tool-schema filtering (57 -> 18 tools, −84 KB/call): no measurable cost
  effect.** The schemas were being prompt-cached at $0.075/1M — a tenth of the
  input rate. **Kept anyway**, because it is a genuine safety win: the agent can
  no longer reach `clipboard_read`, `kill_app`, `drag`, or the recording tools.
  Cost-neutral, blast-radius-positive.
- **Not running Hermes in the repo (−7.5 KB/call): no measurable effect**, same
  caching reason. **Still correct** — build-time docs do not belong in runtime.
- **Aggressive compaction: actively harmful.** It paid a summarisation call each
  time it fired, then dropped context the agent still needed, so it re-snapshotted
  and looped. Reverted.
- **Telling it to skip screenshots: harmful.** The extra instructions appear to
  have made it more cautious, not less.

### Where the money actually goes

The pricing tuple in Hermes's registry is `("0.75", "3.75", "0.075")` —
input / output / **cached** per 1M. Applying it to run 2:

| | tokens | cost | share |
|---|---|---|---|
| uncached input | 299,537 | $0.225 | **77%** |
| cached input | 807,658 | $0.061 | 21% |
| output | 1,480 | $0.006 | 2% |

*(This also resolves the earlier caveat: the estimate is arithmetically correct,
and cached reads are billed at the discounted rate.)*

**77% is uncached input — the conversation tail.** Every call re-sends the whole
history, so cost grows quadratically with turns. That is why shrinking the
*static* prefix did nothing: the prefix was already cached; the growing tail is
not. Published analysis agrees — in one study **63% of tokens came from tool
results**, not schemas.

### So the fix is architectural, not configuration

Since cost scales with **number of turns**, the answer is not cheaper turns. It
is **fewer turns** — and for a personal assistant, most tasks repeat.

**Two mechanisms we already have and have not used:**

1. ~~`cua-driver`'s `start_recording` / `replay_trajectory`.~~ **Checked the
   docs: this does not work for our case.** `element_index` is assigned fresh
   per snapshot and keyed on `(pid, window_id)` — both change between sessions —
   and read-only tools like `get_window_state` are not recorded, so replay
   cannot re-emit the snapshot it would need. Only pixel and keyboard actions
   replay, and pixel-clicking is the brittle approach rejected in D1. It is a
   regression-testing artifact, not a recipe engine.
2. **Hermes `skills`** — a written procedure so the agent does not re-explore.
   Reduces turns; does not eliminate them.
3. **Deterministic limbs — the real answer for daily tasks.** Code, no model.
   Similar in spirit to published work on compiling proven agent traces into
   fixed recipes, though that was only seen second-hand in a search summary and
   its mechanism is not verified here. For us the recipe is simply a small MCP
   server — which is what `capabilities/` was always for.

**The principle:** the agent loop is for figuring something out *the first time*.
Once it works, it should become a recipe. Paying an LLM to re-derive "click 8,
click ×, click 9, click =" every single morning is the actual waste — not the
tool schemas.

That reframes Phase 1b entirely, and it is now the plan in
[03-roadmap.md](03-roadmap.md).

### Budget guard added

Both pre-existing budgets use `INCLUDE_ALL_CREDITS` — they track spend *after*
credits apply, so while the $300 lasts they read ~0 and **would never warn you
as the credit drained**.

Added **"DIVYASTRA credit burn (gross, excl credits)"**: 8,000 INR/month, scoped
to this project, alerting at 50/80/100%. That rate is roughly what spreads $300
across the credit's ~90-day life, so an alert means burning too fast.

Alert-only; it cannot block anything. Delete with:

```
gcloud billing budgets delete 471af866-574f-41d7-8ef8-a1dc954d06da --billing-account=01573C-ED4F11-44CBC4
```

---

## Left undone deliberately

- **Telegram (Phase 2)** — needs a BotFather token and your numeric user ID.
  Both are yours to create; nothing useful can be done without them.
- **Gmail** — deferred at your request.
- **Cost tuning** — the capability manifest and toolset narrowing above. The
  highest-value next task, but it needs measurement, not guesswork.
- **`hermes setup`** was never run (it needs a real console). Everything was
  configured by editing `config.yaml` and `.env` directly, which works fine.
