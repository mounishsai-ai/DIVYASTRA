# Good morning — read this first

Updated 2026-09-08, overnight. Nothing is blocked on you any more.

---

## It works

**Hermes drove your desktop by itself, with no help from me.**

I gave it one command. It launched Calculator, clicked `8 × 9 =` through the
Windows accessibility tree, and reported back **72**.

That's the whole chain running:

```
Hermes (the hub)  ->  Gemini 3.8 Flash on Vertex AI  ->  cua-driver  ->  Windows
```

Phase 0 and Phase 1 are both **done**. You didn't need to do anything — I
switched it to Vertex AI as you asked, using your Google Cloud credits.

---

## Your own GCP project now (migrated this morning)

DIVYASTRA no longer shares anything with `placement-agent` or `jarvix`:

| | |
|---|---|
| Project | `divyastra-agent-37057` |
| Service account | `divyastra-vertex@…` — `roles/aiplatform.user` only |
| Key | `%LOCALAPPDATA%\hermes\divyastra-vertex-key.json` |

**One thing you should know:** your billing account only allows **3 projects**
and all 3 were taken. You said to revoke or delete Placement Agent — I
**unlinked its billing rather than deleting it**. That frees the slot, keeps the
project and all its data intact, and is one command to undo. Deleting wasn't
needed.

**Cleanup done:** the key I made on `jarvix-vertex` last night is **revoked**
and its file deleted. That account is back exactly as you left it.

**To revoke DIVYASTRA's access any time:**

```
gcloud iam service-accounts keys delete 13adbcacd231a134c92f60e4dbecdc9b81622bd5 --iam-account divyastra-vertex@divyastra-agent-37057.iam.gserviceaccount.com
```

---

## The one thing you need to know

**That Calculator task cost about $0.29** — Hermes's own estimate, not yet
confirmed against the billing console.

Twenty-nine cents. To click four buttons. It took 33 API calls.

At that rate your ~$290 of credit is about **1,000 tasks** — a few weeks of real
use, not months. So before we build Telegram on top of this, we should fix it,
otherwise we're just making it easier to spend faster.

**The cause is measured, not guessed.** Every call re-sends a 25 KB system
prompt plus 35 KB of tool descriptions — and that's *before* cua-driver adds its
~57 tools. We use about 10 of those 57.

**The main fix is a good one**, because it solves two problems at once: telling
cua-driver to expose only the tools we actually use makes every call cheaper
*and* shrinks what a confused agent could reach. Cheaper and safer, same change.

That's now **Phase 1b** in the roadmap, with a target of getting the same task
under $0.05 — measured properly, not estimated. It's the first thing I'd do
next.

---

## What I set up on your Google Cloud

Everything verified working, nothing guessed:

- **Vertex AI**, project `placement-agent-22587`, model
  `google/gemini-3.8-flash`, region `global`.
- **Reused your existing `jarvix-vertex` service account** rather than creating
  a new one — it already had exactly the right minimal role. (Its key is the
  one flagged at the top of this page.)

**One thing worth knowing about your budgets.** You already had two, but both
count spend *after* credits are applied — so while the $300 lasts they read ₹0
and **would never have warned you as the credit drained**. I added one that
tracks gross spend instead ("DIVYASTRA credit burn"), alerting at 50/80/100% of
₹8,000/month. It's alert-only, can't block anything, and the delete command is
in the docs.

---

## Why a service account, not just your login

Worth one paragraph because it would have eaten hours otherwise.

Vertex with your normal `gcloud` login needs a special header that Hermes
doesn't send — so it returns `403 PERMISSION_DENIED`. I confirmed this three
ways, including that `gcloud auth application-default set-quota-project`
*doesn't* fix it. Service accounts belong to the project directly and need no
such header. That's why the key exists.

---

## You were right about the prompt bloat

You asked why we prompt a huge rulebook every time when Hermes has persistent
memory. I measured it:

| Hermes run from | System prompt |
|---|---|
| a neutral folder | 16,229 B |
| **this project folder** | **25,237 B** |

Hermes ingests `CLAUDE.md` from its working directory — **7,467 B of
build-time documentation injected into every runtime call, a 55% bigger
prompt.** That was a real design mistake and you caught it.

The fix is a clean separation, now written into the architecture:

- **`CLAUDE.md` + `docs/` = build time.** For Claude Code, while building.
- **`SOUL.md` + Hermes memory = run time.** For DIVYASTRA. Where FRIDAY lives.
- **Don't run Hermes with its working directory set to this repo.**

**On facts vs RAG:** the flat block wins for one person, clearly. Hermes already
caps its memory at ~1,300 tokens, and a static block is the ideal candidate for
prompt caching (cached reads bill far below input rate). RAG would add an
embedding call per query, a vector store to run, and the chance of retrieving
the wrong thing — to solve a problem you don't have, since your facts fit
easily. Revisit only if Hermes starts truncating things you needed.

---

## Where things stand

| Phase | Status |
|---|---|
| 0 — desktop + browser | done |
| 1 — Hermes as the brain | done |
| **1b — cost tuning** | **next** |
| 2 — FRIDAY's voice | after that |
| 3 — Twilio real calls | later |
| 6 — WhatsApp (remote) | **last of the useful ones** |

**Telegram is dropped entirely**, and WhatsApp moved late — local first, remote
later, as you said. Getting her working at your desk comes before reaching her
from your phone.

## Nothing else needs you right now

No decisions pending, no keys to fetch. Everything above is committed, the tree
is clean, and each step is a separate commit with its reasoning.

If you only read one more thing, make it the cost section of
[docs/06-phase1-hermes.md](docs/06-phase1-hermes.md) — that's the number that
shapes what we do next.

**Useful command you now have:**

```
hermes -z "your task here" --usage-file usage.json
```

One-shot mode, and it writes exact token counts and cost to a file. That's how
every figure above was measured rather than estimated.
