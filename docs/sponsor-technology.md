# How PayProof uses the sponsor technologies

PayProof is the checkpoint before money moves: no proof, no payment. It investigates a payment request across five systems to find out whether the supplier is who it claims to be, cites every finding to a database cell a program re-read, lets a policy the controller signed decide instead of the model, and releases money only against a contract signed by a notary that contains no model. Each sponsor technology carries part of that load.

## Zetaris: the data harness every check, and every proof, runs on

- **Where:** `gouji/harness.py` (`ZetarisHarness`), used by every check in `gouji/checks.py`, by the Verifier, by the World Model's ingest, by the notary's re-check (`gouji/notary.py`) and by `run.py verify` (`gouji/verify.py`).
- **How:** the five systems stay where they are. The ERP and the vendor master are two PostgreSQL databases, registered with `CREATE DATASOURCE`; the contracts (Parquet), the accounts-payable mailbox (JSON) and the company registry (CSV) are files on S3-compatible storage, registered as `CREATE LIGHTNING FILESTORE TABLE` in one Lightning database (`deploy/zetaris-sources/register.sql`). Every check is federated SQL sent through the Zetaris REST API; the identity check, for example, joins the ERP's invoices and orders, the vendor master and the contracts in a single query.
- **Why it matters here:** a checkpoint that copies data into its own store has already lost the provenance it needs. Because Zetaris queries the systems in place, every cited cell can be read again from its system of record at the moment it matters: by the Verifier before the brief may use it, by the notary before it signs, and by an auditor running `verify` months later. A proof verified through Zetaris means the evidence still stands in the systems the company runs on.
- **Same SQL, two backends:** in sample mode the identical statements run on DuckDB over the same files, so judges can run everything without credentials; `--backend zetaris` switches every query to Zetaris.

## Meterless: the World Model, the generator rule, and a Scout-style contract

- **World Model** (`gouji/world_model.py`): `WorldStoreService`, `IngestPipelineService` and `ContextBuilderService`, implemented from the hackathon's engine guide under the guide's names. Legal entities are keyed by registration number and jurisdiction, never by name, with content-hash ids, provenance on every entity, and an append-only JSONL log the canonical view rebuilds from. That design is what catches a doppelganger supplier: two companies with one name are two entities, and the World Model raises the alert ("resolves to 3 legal entities") from data, not from a prompt. A name check such as the EU's Verification of Payee passes the same impostor, because the names really match.
- **Injected generator** (`gouji/llm.py`): as the engine guides require, no agent calls a model provider directly. One injected generator serves the Guard, the Planner and the Reporter, so DeepSeek can be swapped for Nemotron or any OpenAI-compatible model by configuration. The same seam lets us hand the model to the attacker (`run.py eval --hostile`): on the held-out set it released no attack after money (0 of 18), exactly as PayProof without a model.
- **Execution contract** (`gouji/notary.py`, `gouji/contract.py`), following the Scout intent design in the public Meterless repository: a signed object the downstream system verifies before it acts. Only the notary can sign one, with its own Ed25519 key, after re-running every check without a model under the policy the controller signed. The contract binds the payment, the evidence (a hash of every cited cell) and the policy, is valid for 15 minutes and usable once; the payment gateway holds only the notary's public key.

## NVIDIA: Nemotron as the red team

- **Where:** `gouji/redteam.py`, `data/heldout/`.
- **How:** NVIDIA Nemotron (`nvidia/nemotron-3.5-lightning-30b-a3b` on build.nvidia.com) wrote the held-out set: impostor invoices, bank-change requests from look-alike domains, eight new prompt injections, eight honest sentences meant to trip a naive filter, and four genuine bank-change notices, dropped into 44 requests in a world with its own seed. The set was sealed (prompts, raw output and a SHA-256 of every file in `manifest.json`, commit efa9fec) before it was evaluated once; CI re-checks the seal on every change.
- **Why it matters:** the checks were written with one model's help; testing them on text a different model wrote, which their authors never read before the run, is what makes the numbers mean something. Result: a payee list paid 9 of the 18 attacks after money (EUR 170,800.31, three of them straight to impostors); PayProof paid none, and interrupted none of the 20 normal payments.

## Cursor

Not used. Rule 5.1 makes Cursor optional; PayProof was developed with other tools.

## What is unusual about this use

- The sponsor technologies are load-bearing, not decorative: remove Zetaris and nothing can be re-read from the systems of record, so there is no proof; remove the World Model and the doppelganger is invisible; remove the contract and a talked-into agent could still move money.
- The model never decides and cannot make PayProof looser. Zetaris supplies the facts, the World Model resolves who is who, the controller's signed policy decides on graded evidence, the notary re-derives that decision without a model, and the gateway makes it enforceable.
