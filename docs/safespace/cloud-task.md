# Cloud task: SafeSpace Hacks materials for PayProof

You are a cloud Claude Code session in hoongyu/gouji (a **public** repository). PayProof already works; this task prepares its entry for SafeSpace Hacks and verifies that it runs. Read this file, then `README.md`.

`CLAUDE.md` refers to a `.hackertrip/` folder. That folder is local only and not in git; ignore those references.

## 1. Deadlines (Berlin time; CET = UTC+1 since 2026-10-25)

| What | When |
|---|---|
| SafeSpace development period opened | 2026-10-17 00:00 ET (06:00 Berlin summer time) |
| Submission deadline | 2026-11-22 23:00 CET (official: 5:00 PM ET) |
| Judging / results | 2026-11-23 to 11-24 / 2026-11-25 |
| Links must stay live until | 2026-11-24 |

## 2. Hard rules

1. Work only on branch `safespace` and push it. Do not touch `main` or any other branch, do not merge, do not open a pull request, do not change repository settings. Everything you push is public.
2. Materials and verification only; no new features. Change product code only if a test fails in sample mode, keep the fix minimal and record it in the build log.
3. Sample mode only: no API keys. Never commit `.env`, private keys or tokens.
4. English. Never invent numbers: every figure must come from a command you ran or from the README, and say which.
5. Do not claim anything about other hackathons or prizes.

## 3. SafeSpace Hacks: rules that matter

- Devpost, organiser SafeSpace. Students worldwide, solo allowed. The owner handles eligibility and posts the entry.
- Theme: a working prototype related to safety: cybersecurity, privacy, scam prevention, community safety, emergency preparedness, trustworthy information, safe habits, accessible safety tools. PayProof fits scam prevention (business e-mail compromise and invoice fraud).
- Prior work is allowed, but the parts built during the development period must be clearly separated from older components.
- Only synthetic data or systems you are authorised to test; never expose real vulnerabilities. PayProof's buyer and suppliers are fictional.
- The entry needs: problem, solution, technology, challenges, what we learned; a live demo, a downloadable build or a recorded walkthrough, with install instructions; screenshots; optional video; source link and credits; **one example of a safer outcome**; **one limitation**.
- Judging, four equal criteria scored 1 to 5: **Safety Benefit**, **Practical Functionality**, **Trust & Responsible Design**, **Clarity & User Experience**. Ties go to Safety Benefit, then Practical Functionality.

## 4. Tasks

Commit after each.

**S1 Verify.** Run, in sample mode: `uv sync`, `uv run pytest`, `uv run python run.py case INV-5567`, `uv run python run.py verify output_examples/INV-5559-proof.json`, `uv run python run.py eval`, `uv run python run.py eval --hostile`, `uv run python run.py eval --data data/heldout`. Record each command, its key output and duration in `docs/safespace/build-log.md`. If a number differs from the README's Results section, report the difference there; do not edit the README numbers.

**S2 Prior-work disclosure.** From `git log`: only two commits predate 2026-10-17, both chores (project initialisation and `.env.example`); product code was committed from 2026-10-24 onward. `mandate-engine` v0.1.1 (MIT OR Apache-2.0) was written before the period and is an existing component. Verify these claims with git yourself and write them in a short section of `docs/safespace/submission.md`.

**S3 Judging map.** `docs/safespace/judging.md`: one section per criterion, with concrete evidence (file paths, commands, results) showing how PayProof meets it.

**S4 Devpost text.** `docs/safespace/submission.md`, ready to paste: Inspiration, What it does, How we built it, Challenges, Accomplishments, What we learned, What's next, Built with, **A safer outcome** (one concrete case from `output_examples/`, e.g. INV-5567: what the attacker tried, what PayProof did, what the payer sees, how anyone can verify the proof), **One limitation** (from the README's Limitations), Prior work and credits, Try it (sample-mode commands and Docker), Links (`https://github.com/hoongyu/gouji/tree/safespace`, video placeholder for the owner).

**S5 Walkthrough.** `docs/safespace/walkthrough.md`: a 2 to 3 minute screen-recording script for the owner (commands, what to show, what to say, in short caption-friendly sentences). If headless Chromium with Playwright is available, capture screenshots of the running app (`run.py serve`, the request list and a brief page) into `docs/safespace/img/`; otherwise list what to capture.

**S6 README pointer.** On this branch only, add a short "SafeSpace Hacks 2026" section before "License" that links `docs/safespace/submission.md` and states the development-period split in one sentence.

**S7 Hand-off.** Finish `docs/safespace/build-log.md` with what was done, verification results, anything that failed, and the owner's checklist: record the walkthrough video, post on Devpost, decide whether to merge `safespace` into `main`. Push.

Definition of done: tests pass in sample mode (or failures are explained); the five files above exist with no invented figures; branch `safespace` is pushed.
