"""gouji command line.

    python run.py generate                 write the five sample systems to data/sample
    python run.py case CASE-25             investigate one request (by case or invoice id)
    python run.py eval                     B1 vs B3 on every case in --data (default data/sample)
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

from gouji.llm import Usage, load_dotenv, openai_generator

LOGS = Path("logs")
OUT = Path("output_examples")


def _gens(live: bool, usage: Usage) -> dict:
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
    ap.add_argument("command", choices=["generate", "case", "eval", "serve"])
    ap.add_argument("target", nargs="?")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--data", default="data/sample")
    ap.add_argument("--tag", default=None, help="name for the eval report (default: sample or live)")
    args = ap.parse_args()
    data = Path(args.data)
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    usage = Usage()

    if args.command == "generate":
        from gouji.world import generate
        cases = generate(data)
        print(f"wrote {len(cases)} cases to {data}")
        return
    if args.command == "serve":
        import uvicorn
        uvicorn.run("gouji.api:app", host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
        return

    from gouji.evaluate import evaluate, to_markdown
    gens = _gens(args.live, usage)
    if args.command == "case" and not args.target:
        sys.exit("usage: python run.py case CASE-25")
    only = [args.target] if args.command == "case" else None
    report = evaluate(data, LOGS, run_id, only=only, **gens)
    report["usage"] = vars(usage)
    OUT.mkdir(exist_ok=True)
    if args.command == "case":
        if not report["results"]:
            sys.exit(f"no case or invoice called {args.target!r}; see {data}/cases.json")
        result = next(iter(report["results"].values()))
        path = OUT / f"{result['inv_id']}.json"
        path.write_text(json.dumps(result, indent=2, default=str, ensure_ascii=False), encoding="utf-8")
        print(f"{result['inv_id']}: {result['decision']} -> {result['recommendation']}")
        print(result["brief"]["text"])
        print(f"trace: logs/trace-{run_id}.jsonl  result: {path}")
        return
    tag = args.tag or ("live" if args.live else "sample")
    (OUT / f"eval-{tag}.json").write_text(json.dumps({k: v for k, v in report.items() if k != "results"},
                                                     indent=2, default=str), encoding="utf-8")
    (OUT / f"eval-{tag}.md").write_text(to_markdown(report), encoding="utf-8")
    print(to_markdown(report))
    if args.live:
        print(f"model calls: {usage.calls}, tokens: {usage.prompt_tokens} in / {usage.completion_tokens} out")


if __name__ == "__main__":
    main()
