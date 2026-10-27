"""gouji command line.

    python run.py generate                 write the five sample systems to data/sample
    python run.py heldout                  have Nemotron write a sealed held-out set into data/heldout
    python run.py case CASE-25             investigate one request (by case or invoice id)
    python run.py eval                     B1 vs B3 on every case in --data (default data/sample)
    python run.py eval --hostile           the same, with the model replaced by one the attacker controls
    python run.py verify PROOF.json        re-check a decision from its proof file: signatures, cells, decision
    python run.py policy                   the controller signs the payment policy for --data (needs keys/controller.key)
    python run.py serve                    HTTP API on $PORT (default 8000): POST /run

Sample mode (no network, no keys) is the default. Add --live to let DeepSeek plan, screen for
injection and write, which reads DEEPSEEK_API_KEY from the environment or .env.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from gouji.llm import Usage, hostile_generator, load_dotenv, openai_generator

LOGS = Path("logs")
OUT = Path("output_examples")


def _gens(live: bool, usage: Usage, hostile: bool = False) -> dict:
    if hostile:
        os.environ.setdefault("SAMPLE_MODE", "true")
        return {"planner": hostile_generator(), "reporter": hostile_generator(), "guard": hostile_generator(),
                "models": "hostile, attacker-controlled"}
    if not live:
        os.environ.setdefault("SAMPLE_MODE", "true")
        return {}
    os.environ["SAMPLE_MODE"] = "false"
    gens = {
        "planner": openai_generator("deepseek", os.environ.get("GOUJI_PLANNER_MODEL"), usage),
        "reporter": openai_generator("deepseek", os.environ.get("GOUJI_REPORTER_MODEL"), usage),
        "guard": openai_generator("deepseek", os.environ.get("GOUJI_GUARD_MODEL"), usage),
    }
    if gens["planner"] is None:
        sys.exit("--live needs DEEPSEEK_API_KEY")
    return gens


def main() -> None:
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["generate", "heldout", "case", "eval", "verify", "policy", "serve"])
    ap.add_argument("target", nargs="?")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--hostile", action="store_true", help="replace the model with one the attacker controls")
    ap.add_argument("--data", default="data/sample")
    ap.add_argument("--tag", default=None, help="name for the eval report (default: sample or live)")
    ap.add_argument("--backend", choices=["auto", "local", "zetaris"], default=None,
                    help="where the checks run (default: $GOUJI_BACKEND, else auto)")
    args = ap.parse_args()
    if args.backend:
        os.environ["GOUJI_BACKEND"] = args.backend
    data = Path(args.data)
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    usage = Usage()

    if args.command == "generate":
        from gouji.world import generate
        cases = generate(data)
        print(f"wrote {len(cases)} cases to {data}")
        return
    if args.command == "heldout":
        from gouji.redteam import make_heldout
        out = Path(args.data if args.data != "data/sample" else "data/heldout")
        m = make_heldout(out, usage)
        print(f"wrote {m['cases']} cases ({m['attacks']} attacks) to {out}; text by {m['text_by']['model']}, "
              f"{usage.calls} calls; manifest {out / 'manifest.json'} (contents not printed)")
        return
    if args.command == "policy":
        from gouji.policy import write_signed_policy
        from gouji.signing import fingerprint, private_key
        key = private_key("controller")
        path = write_signed_policy(data, key)
        print(f"signed {path} with the controller key {fingerprint(key.public_key())} (public half: keys/controller.pub)")
        return
    if args.command == "verify":
        if not args.target:
            sys.exit("usage: python run.py verify logs/proofs/<run>/<inv_id>.json")
        from gouji.harness import open_harness
        from gouji.signing import public_key, trusted_publics
        from gouji.verify import verify_proof
        proof = json.loads(Path(args.target).read_text(encoding="utf-8"))
        if args.data == ap.get_default("data"):  # the data set the proof was decided on, from its policy file
            data = Path("data") / Path(proof["policy"]["file"]).stem.split(".")[-1]
        h = open_harness(data)
        print(f"Proof {args.target}: {proof['inv_id']}, decision {proof['decision'].upper()}, judged at {proof['judged_at']}")
        checks = verify_proof(proof, h, controller=public_key("controller"), notaries=trusted_publics("notary"))
        for c in checks:
            print(f"  [{'ok' if c.ok else 'FAIL'}] {c.name}: {c.detail}")
        ok = all(c.ok for c in checks)
        print(f"{'VALID' if ok else 'NOT VALID'}: {sum(c.ok for c in checks)} of {len(checks)} checks pass "
              f"({len(h.log)} queries on {h.name})")
        sys.exit(0 if ok else 1)
    if args.command == "serve":
        import uvicorn
        uvicorn.run("gouji.api:app", host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
        return

    from gouji.evaluate import evaluate, to_markdown
    gens = _gens(args.live, usage, args.hostile)
    if args.command == "case" and not args.target:
        sys.exit("usage: python run.py case CASE-25")
    only = [args.target] if args.command == "case" else None
    report = evaluate(data, LOGS, run_id, only=only, echo=args.command == "case", **gens)
    report["usage"] = vars(usage)
    OUT.mkdir(exist_ok=True)
    if args.command == "case":
        if not report["results"]:
            sys.exit(f"no case or invoice called {args.target!r}; see {data}/cases.json")
        result = next(iter(report["results"].values()))
        backend = report["backend"]
        path = OUT / (f"{result['inv_id']}.json" if backend == "local-duckdb" else f"{backend}-run/{result['inv_id']}.json")
        path.parent.mkdir(exist_ok=True)
        (path.parent / f"{result['inv_id']}-queries.json").write_text(
            json.dumps({"backend": backend, "queries": report["query_log"]}, indent=2, default=str), encoding="utf-8")
        path.write_text(json.dumps({k: v for k, v in result.items() if k != "proof"}, indent=2, default=str,
                                   ensure_ascii=False), encoding="utf-8")
        (path.parent / f"{result['inv_id']}-proof.json").write_text(
            json.dumps(result["proof"], indent=2, default=str, ensure_ascii=False), encoding="utf-8")
        print(f"{result['inv_id']}: {result['decision']} -> {result['recommendation']}")
        print(result["brief"]["text"])
        print(f"trace: logs/trace-{run_id}.jsonl  result: {path}  proof: {result['proof_file']}")
        return
    tag = args.tag or ("hostile" if args.hostile else "live" if args.live else "sample")
    (OUT / f"eval-{tag}.json").write_text(json.dumps({k: v for k, v in report.items() if k not in ("results", "query_log")},
                                                     indent=2, default=str), encoding="utf-8")
    (OUT / f"eval-{tag}.md").write_text(to_markdown(report), encoding="utf-8")
    print(to_markdown(report))
    if args.live:
        print(f"model calls: {usage.calls}, tokens: {usage.prompt_tokens} in / {usage.completion_tokens} out")


if __name__ == "__main__":
    main()
