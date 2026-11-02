# Walkthrough script (2 to 3 minutes)

Screenshots already captured in `img/`: `request-list.png`, `brief-INV-5567.png`. Use them as fallbacks. Terminal at `/home/user/gouji` or your clone, branch `safespace`. Total about 2:30.

**1. The problem (0:00-0:20).** Show the README title.
Say: "Fraudsters pretend to be a supplier. They change the bank account. Payment lists and AI agents let it through. PayProof is the checkpoint before money moves."

**2. Start (0:20-0:40).** Run `uv sync` (cut), then `uv run python run.py serve`. Open http://localhost:8000/.
Say: "No keys. Sample mode. Everything runs offline. Fictional buyer and suppliers."

**3. The attack (0:40-1:30).** Click INV-5567 (Taivora Electronics, EUR 49,629.00).
Say: "The verdict comes first: hold. Do not pay." Scroll to Why. "The issuer is not the company we signed the contract with." Show the registry finding: three companies, one name. Show the quarantined text. "The invoice tried to tell the AI to release payment. PayProof treats it as data."

**4. Proof (1:30-2:10).** In a terminal run `uv run python run.py verify output_examples/INV-5567-proof.json`, then `uv run python run.py verify output_examples/INV-5559-proof.json`.
Say: "Anyone can re-check a decision. A hold verifies. A payment needs a notary's signed contract."

**5. Evidence it holds up (2:10-2:35).** Run `uv run python run.py eval --data data/heldout`.
Say: "Held-out set. Payee list paid 9 of 18 attacks. PayProof paid none. No normal payment was blocked."

**6. Limit and close (2:35-2:50).** Say: "One limit. PayProof holds and explains. A human still calls the supplier. The data is fictional."
