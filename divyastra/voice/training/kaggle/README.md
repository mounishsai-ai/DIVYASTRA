# Kaggle training kernel

Trains the `hey divya` wake word on Kaggle's free GPU instead of 8-12 hours on
a CPU-only laptop.

```
kaggle kernels push -p divyastra/voice/training/kaggle --accelerator NvidiaTeslaT4
kaggle kernels status mounishsai7/hey-divya-wakeword
kaggle kernels output mounishsai7/hey-divya-wakeword -p <dir>
```

## Three gotchas, each of which cost time

**0. The account must be PHONE VERIFIED, or you silently get a CPU worker.**
This is the one that actually cost the time. Kaggle requires SMS verification
before it will hand out GPU or TPU accelerators - and an unverified account does
not get an error, it just runs on CPU. Worse, the signals all look fine:
`kernel-metadata.json` comes back from the server with `enable_gpu: True`, and
`quota_view()` reports the full 6 hours available with none used. **Neither of
those proves the account is verified.** Verify at:
notebook -> left sidebar -> Settings -> "Get phone verified".

**1. `"enable_gpu": true` in `kernel-metadata.json` is NOT enough.** The first
push ran on CPU regardless - the log said `nvidia-smi: not found` / `NO GPU`.
You must pass **`--accelerator NvidiaTeslaT4`** (or `NvidiaTeslaP100`) on the
push command; it overrides the metadata boolean, and the metadata alone is
silently ignored. On a CPU worker this job would have hit Kaggle's runtime
limit and died with nothing to show.

**2. Auth changed.** Kaggle now uses a single bearer token at
`~/.kaggle/access_token` (or `KAGGLE_API_TOKEN`), not the old `kaggle.json`
with username+key. `kaggle config view` should report
`auth_method: ACCESS_TOKEN`.

**3. Quota is 6 hours of GPU per week**, checked with the API's `quota_view()`
(there is no `kernels quota` CLI subcommand despite the method existing).
This run should use about one of those hours.

## Why Kaggle and not Colab

Colab has no CLI - it is browser-only - and Google's terms prohibit automated
access, so driving it with browser automation would put the Google account at
risk. Kaggle officially supports programmatic use.
