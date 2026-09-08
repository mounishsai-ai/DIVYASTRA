"""Train the 'hey divya' wake word on Kaggle's free GPU.

Runs as a Kaggle script kernel. Pushed with:
    kaggle kernels push -p divyastra/voice/training/kaggle

Why Kaggle and not Colab: Kaggle officially supports programmatic use via its
CLI, so no clicking and no terms-of-service grey area. Colab is browser-only and
Google's terms prohibit automated access.

Locally this run takes 8-12 hours on an Intel UHD CPU. Here it should be ~1 hour.
Output lands in /kaggle/working and is fetched with `kaggle kernels output`.
"""

import json
import os
import subprocess
import sys
import time

T0 = time.time()


def sh(cmd: str, check: bool = True) -> None:
    print(f"\n$ {cmd}", flush=True)
    r = subprocess.run(cmd, shell=True)
    if check and r.returncode != 0:
        raise SystemExit(f"failed ({r.returncode}): {cmd}")


def stamp(msg: str) -> None:
    print(f"\n=== [{time.time() - T0:7.1f}s] {msg} ===", flush=True)


stamp("environment")
sh("nvidia-smi --query-gpu=name,memory.total --format=csv || echo 'NO GPU'", check=False)
print("python:", sys.version.split()[0], flush=True)

# espeak-ng is required by the Piper phonemiser and is NOT preinstalled.
# On Windows this needed winget; here it is one apt call.
stamp("installing espeak-ng")
sh("apt-get -qq update && apt-get -qq install -y espeak-ng", check=False)
sh("espeak-ng --version", check=False)

stamp("installing livekit-wakeword")
sh(f"{sys.executable} -m pip install -q 'livekit-wakeword[train,export,eval]'")

# --- the config -------------------------------------------------------------
# Same phrase and negatives as the local calibration run, but at full size.
# Calibration (1,500 samples / 6,000 steps) gave recall 78.3% at 16.4 false
# wakes/hour - unusable. These are the library defaults.
CONFIG = {
    "model_name": "hey_divya",
    "tts_backend": "piper_vits",
    "target_phrases": ["hey divya", "hey deevya"],
    "custom_negative_phrases": [
        "hey deeya", "hey diya", "hey dia", "hey diana",
        "divya", "video", "hey there", "hey siri", "hey google", "okay",
    ],
    "n_samples": 10000,
    "n_samples_val": 2000,
    "n_background_samples": 200,
    "n_background_samples_val": 40,
    "steps": 50000,
    "learning_rate": 0.0001,
    "data_dir": "/kaggle/temp/data",
    "output_dir": "/kaggle/working/output",
}

os.makedirs("/kaggle/temp", exist_ok=True)
cfg_path = "/kaggle/working/hey_divya.yaml"
try:
    import yaml

    with open(cfg_path, "w") as f:
        yaml.safe_dump(CONFIG, f, sort_keys=False)
except ImportError:
    with open(cfg_path, "w") as f:
        json.dump(CONFIG, f, indent=2)  # the loader accepts JSON too
print(open(cfg_path).read(), flush=True)

# --skip-acav avoids a ~16 GB download we do not need.
stamp("setup: piper weights, RIRs, background noise")
sh(f"livekit-wakeword setup --config {cfg_path} --skip-acav")

stamp("full pipeline: generate -> augment -> train -> export")
sh(f"livekit-wakeword run {cfg_path}")

stamp("results")
sh("find /kaggle/working/output -name '*.onnx' -o -name '*.json' -o -name '*.png' | head -20", check=False)
for root, _dirs, files in os.walk("/kaggle/working/output"):
    for name in files:
        if name.endswith("_eval.json"):
            print(f"\n{name}:", flush=True)
            print(json.dumps(json.load(open(os.path.join(root, name))), indent=2), flush=True)

stamp(f"done in {(time.time() - T0) / 60:.1f} minutes")
