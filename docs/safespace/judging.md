# Judging map

Each criterion is scored 1 to 5. All figures come from the README or from commands run on 2026-11-02 (see `build-log.md`). The buyer and suppliers are fictional.

## Safety Benefit

PayProof stops business e-mail compromise and invoice fraud before money moves.

- Dev set, 48 requests: attacks after money not owed paid without a human: payee-list baseline 15 of 23, PayProof 0 of 23 (`uv run python run.py eval`, `output_examples/eval-sample.md`).
- Held-out set, 44 requests written by a different model and sealed before evaluation: baseline 9 of 18 (EUR 170,800.31), PayProof 0 of 18 (`uv run python run.py eval --data data/heldout`).
- Impostor accounts: baseline 3 of 18 held-out, PayProof 0.
- Concrete case: INV-5567, a doppelganger supplier, EUR 49,629.00, held (`output_examples/INV-5567.json`).

## Practical Functionality

- Runs end to end in sample mode with no keys: `uv sync`, `uv run pytest` (15 passed), `uv run python run.py case INV-5567`, `uv run python run.py serve`.
- HTTP API (`POST /run`), a request list and a one-page brief per request (`docs/safespace/img/`).
- Normal payments interrupted: 0 of 24 (dev) and 0 of 20 (held-out); the payee list interrupted 4 in each set.
- Docker image (`Dockerfile`), CI, and a run on a live Zetaris instance (`output_examples/zetaris-run/`, README).

## Trust & Responsible Design

- Words cannot move money: invoice text and model output never reach the decision; text aimed at the AI is quarantined and shown as data (brief screenshot).
- Hostile-model test: with the model controlled by the attacker, 0 of 18 held-out attacks after money were paid (`uv run python run.py eval --hostile`, `output_examples/eval-heldout-hostile.md`).
- A payment needs a signed contract from a notary that contains no model; the policy is signed by the controller. Anyone can verify a proof: `uv run python run.py verify output_examples/INV-5559-proof.json` (10 of 10 checks), and a hold verifies too (7 of 7).
- Synthetic data only; the hold recommends a human call to the supplier rather than acting alone.
- Honest limits stated in the README, including that the numbers are not a fraud rate.

## Clarity & User Experience

- The brief shows the verdict first ("Hold: likely fraud, do not pay; call the supplier on the number on file"), then the reasons with cited findings, the quarantined text, the signed proof and every agent step (`docs/safespace/img/brief-INV-5567.png`).
- Every claim cites cells that can be opened in their source system.
- Two README languages (English, Simplified Chinese) and a 2 to 3 minute walkthrough script (`walkthrough.md`).
