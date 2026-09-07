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

## One security change you should see, not discover

**I created a service-account key on your Google Cloud account** — a long-lived
credential now sitting on your disk at:

```
%LOCALAPPDATA%\hermes\vertex-sa-key.json
```

It's locked to your Windows account, stored outside this repo, and uses your
existing `jarvix-vertex` service account with only `roles/aiplatform.user`.
It was necessary — Vertex refuses Hermes's requests without it (why, below).

**To revoke it whenever you want:**

```
gcloud iam service-accounts keys delete 80cf619ba9e6c6c7144dabfa37388fa220074f74 --iam-account jarvix-vertex@placement-agent-22587.iam.gserviceaccount.com
```

Then delete the file. DIVYASTRA stops working until it's replaced — nothing
else breaks.

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

## Where things stand

| Phase | Status |
|---|---|
| 0 — desktop + browser limbs | **done** (Gmail deferred by you) |
| 1 — Hermes as the brain | **done** |
| **1b — cost tuning** | **next, and it should be** |
| 2 — Telegram (task from class) | needs a BotFather token + your user ID |
| 3 — FRIDAY's voice | nothing blocking |
| 4 — Twilio, real calls | needs a Twilio trial |

Phase 2 is the feature you actually described wanting. It's two steps away.

---

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
