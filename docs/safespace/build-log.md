# SafeSpace build log

Run by a scheduled cloud session on 2026-11-02 (container clock 09:21 UTC), branch `safespace`, sample mode (`SAMPLE_MODE=true`, no API keys set). Durations are wall-clock from this run.

## S1 Verification

| Command | Result | Time |
|---|---|---|
| `uv sync` | exit 0 | 4.6 s |
| `uv run pytest` | 15 passed | 20.9 s |
| `uv run python run.py case INV-5567` | `ask -> hold: likely fraud, do not pay; call the supplier on the number on file`; 2 World Model alerts (doppelganger, account_jurisdiction_mismatch); direct pay call without contract refused | 0.6 s |
| `uv run python run.py verify output_examples/INV-5559-proof.json` | `VALID: 10 of 10 checks pass (46 queries on local-duckdb)` | 0.5 s |
| `uv run python run.py eval` (dev, 48 cases) | attacks after money not owed paid: B1 15/23, B3 0/23; impostor/attacker account: B1 3/23, B3 0/23; genuine invoices with an AI instruction paid: B1 1/1, B3 0/1; normal payments interrupted: B1 4/24, B3 0/24; notary re-checked 24 releases, refused 0 | 8.8 s |
| `uv run python run.py eval --hostile` (dev) | same table as above with the attacker-controlled model; 96 brief sentences removed | 7.8 s |
| `uv run python run.py eval --data data/heldout` (44 cases) | attacks after money not owed paid: B1 9/18, B3 0/18; impostor account: B1 3/18, B3 0/18; genuine invoices with an AI instruction paid: B1 6/6, B3 6/6; normal payments interrupted: B1 4/20, B3 0/20; notary re-checked 26 releases, refused 0 | 8.9 s |

Also run: `verify output_examples/INV-5567-proof.json` gives `VALID: 7 of 7 checks pass (14 queries on local-duckdb)` (the hold proof).

### Comparison with the README Results section

No differences. Dev and held-out tables match the README exactly (EUR amounts included). The README's "80 sentences removed" refers to the held-out hostile run, which this task did not run; the dev hostile run removed 96, and the README does not give a dev figure, so there is nothing to compare. Docker was not built or run in this session; the Docker commands in `submission.md` come from the README and are untested here.

### Side effects

The eval commands overwrite tracked files in `output_examples/` (new run ids, and `eval-sample.*` is overwritten by the held-out run). I restored them with `git checkout -- output_examples`, so the committed examples and their signatures are unchanged. No product code was changed.

## S2 Prior work (checked with git)

`git log --before=2026-10-17` returns exactly two commits: `06a7ea8` (2026-10-06, project initialisation) and `55aa59e` (2026-10-09, `.env.example` exception), both chores. The first product commit is `54b02ac` (2026-10-24). `mandate-engine` is added as a dependency in that same commit (`pyproject.toml`, v0.1.1). Caveat: git shows only when this repository adopted it; the claim that it was written before the period comes from the README, and I could not check the mandate-engine repository from this session. The README also mentions an identity rewrite of history, so commit dates are as recorded in this repository.

## S3-S6

- `judging.md`, `submission.md`, `walkthrough.md` written.
- Screenshots captured with headless Chromium and Playwright against `run.py serve`: `img/request-list.png`, `img/brief-INV-5567.png`.
- README: "SafeSpace Hacks 2026" section added before "License" on this branch only.

## What failed

Nothing failed. One shell command (`pkill -f "run.py serve"`) killed my own shell once; the server was stopped regardless.

## Owner's checklist

1. Record the walkthrough video following `walkthrough.md` and put its link into `submission.md` (Links).
2. Check eligibility and post the entry on Devpost before 2026-11-22 23:00 CET; keep links live until 2026-11-24.
3. Docker: done by the owner on 2026-11-02, see "Owner-side Docker check" below.
4. Confirm that mandate-engine predates 2026-10-17 (its repository history) before relying on the disclosure.
5. Decide whether to merge `safespace` into `main`. Nothing was merged and no PR was opened.

## Owner-side Docker check (2026-11-02)

Run on the owner's Windows 11 laptop, sample mode, no `.env`:

- `docker build -q -t gouji-safespace-check .` finished in about 590 s.
- `docker run -d --rm -p 18000:8000 gouji-safespace-check`: `GET /` and `GET /brief/INV-5567` both returned HTTP 200. The container was stopped afterwards.
