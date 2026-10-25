"""The release gate for gouji's guardrails, run in CI after both evaluations.

    python scripts/eval_gate.py                fail if B3 lets more attacks through, or interrupts more normal
                                               payments, than eval/baseline.json allows
    python scripts/eval_gate.py --verify-seal  fail if any file of the sealed held-out set changed

A maintainer can accept a worse result on purpose by adding the label accept-eval-change to the merge
request (GitLab passes it in CI_MERGE_REQUEST_LABELS); the gate then passes and says so.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OVERRIDE = "accept-eval-change"


def verify_seal() -> int:
    manifest = json.loads((ROOT / "data/heldout/manifest.json").read_text(encoding="utf-8"))
    bad = [name for name, digest in manifest["sha256"].items()
           if hashlib.sha256((ROOT / "data/heldout" / name).read_bytes()).hexdigest() != digest]
    for name in bad:
        print(f"CHANGED  data/heldout/{name} no longer matches its SHA-256 in manifest.json")
    print(f"held-out seal: {len(manifest['sha256']) - len(bad)} / {len(manifest['sha256'])} files intact")
    return 1 if bad else 0


def gate() -> int:
    baseline = json.loads((ROOT / "eval/baseline.json").read_text(encoding="utf-8"))
    labels = {x.strip() for x in os.environ.get("CI_MERGE_REQUEST_LABELS", "").split(",") if x.strip()}
    failures = []
    print(f"{'set':<8} {'measure':<34} {'baseline':>8} {'now':>6}")
    for name, want in baseline["sets"].items():
        s = json.loads((ROOT / want["report"]).read_text(encoding="utf-8"))["summary"]
        for key, label in (("attacks_auto_released", f"attacks paid without a human (/{s['attacks']})"),
                           ("normal_interrupted", f"normal payments interrupted (/{s['normal']})")):
            now, allowed = s["b3"][key], want[f"b3_{key}"]
            mark = "WORSE" if now > allowed else ("better" if now < allowed else "")
            print(f"{name:<8} {label:<34} {allowed:>8} {now:>6}  {mark}")
            if now > allowed:
                failures.append(f"{name}: {label} rose from {allowed} to {now}")
        changed = {k: v["b3_allow"] for k, v in s["by_kind"].items()}
        print(f"{name:<8} paid by kind: " + ", ".join(f"{k} {v}/{s['by_kind'][k]['n']}" for k, v in changed.items()))
    if not failures:
        print("gate: pass")
        return 0
    for f in failures:
        print(f"gate: {f}")
    if OVERRIDE in labels:
        print(f"gate: pass, because a maintainer added the label '{OVERRIDE}'")
        return 0
    print(f"gate: fail. Fix the regression, or have a maintainer add the label '{OVERRIDE}' to accept it.")
    return 1


if __name__ == "__main__":
    sys.exit(verify_seal() if "--verify-seal" in sys.argv else gate())
