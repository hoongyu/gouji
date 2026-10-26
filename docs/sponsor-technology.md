# How PayProof uses the sponsor technologies

PayProof investigates a payment request before money moves: it checks across five systems whether the supplier is who it claims to be, cites every finding to a database cell a program re-read, and lets a signed mandate, not the model, decide. Each sponsor technology carries part of that load.

## Zetaris: the data harness every check runs on

- **Where:** `gouji/harness.py` (`ZetarisHarness`), used by every check in `gouji/checks.py`, by the Verifier and by the World Model's ingest.
- **How:** the five systems stay where they are. The ERP and the vendor master are two PostgreSQL databases, registered with `CREATE DATASOURCE`; the contracts (Parquet), the accounts-payable mailbox (JSON) and the company registry (CSV) are files on S3-compatible storage, registered as `CREATE LIGHTNING FILESTORE TABLE` in one Lightning database (`deploy/zetaris-sources/register.sql`). Every check is federated SQL sent through the Zetaris REST API; the identity check, for example, joins the ERP's invoices and orders, the vendor master and the contracts in a single query.
- **Why it matters here:** an investigator that copies data into its own store has already lost the provenance it needs. Because Zetaris queries the systems in place, the Verifier can re-read every cited cell from its system of record by primary key, through the same interface, just before the brief is allowed to use it. No finding reaches the decision unless its cells still match.
- **Same SQL, two backends:** in sample mode the identical statements run on DuckDB over the same files, so judges can run everything without credentials; `--backend zetaris` switches every query to Zetaris.

## Meterless: the World Model, the generator rule, and a Scout-style contract

- **World Model** (`gouji/world_model.py`): `WorldStoreService`, `IngestPipelineService` and `ContextBuilderService`, implemented from the hackathon's engine guide under the guide's names. Legal entities are keyed by registration number and jurisdiction, never by name, with content-hash ids, provenance on every entity, and an append-only JSONL log the canonical view rebuilds from. That design is what catches a doppelganger supplier: two companies with one name are two entities, and the World Model raises the alert ("resolves to 3 legal entities") from data, not from a prompt. Its context, with a selection reason per item, feeds the Planner and the Reporter.
- **Injected generator** (`gouji/llm.py`): as the engine guides require, no agent calls a model provider directly. One injected generator serves the Guard, the Planner and the Reporter, so DeepSeek can be swapped for Nemotron or any OpenAI-compatible model by configuration, and sample mode simply runs without one.
- **Execution contract** (`gouji/contract.py`), following the Scout intent design in the public Meterless repository: when the mandate allows a payment, PayProof issues an HMAC-signed contract bound to a hash of the exact payment, valid for 15 minutes and usable once. The payment executor refuses every call without one, and each held case runs a bypass probe to show it.

## NVIDIA: Nemotron as the red team

- **Where:** `gouji/redteam.py`, `data/heldout/`.
- **How:** NVIDIA Nemotron (`nvidia/nemotron-3.5-lightning-30b-a3b` on build.nvidia.com) wrote the held-out set: impostor invoices, bank-change requests from look-alike domains, eight new prompt injections, eight honest sentences meant to trip a naive filter, and four genuine bank-change notices, dropped into 44 requests in a world with its own seed. The set was sealed (prompts, raw output and a SHA-256 of every file in `manifest.json`, commit 8bddf05) before it was evaluated once; CI re-checks the seal on every change.
- **Why it matters:** the checks were written with one model's help; testing them on text a different model wrote, which their authors never read before the run, is what makes the numbers mean something. Result: a payee list alone paid 15 of 24 attacks; PayProof with its model screen paid 2, and interrupted none of the 20 normal payments.

## Cursor

Not used. Rule 5.1 makes Cursor optional; PayProof was developed with other tools.

## What is unusual about this use

- The sponsor technologies are load-bearing, not decorative: remove Zetaris and the Verifier cannot re-read from the systems of record; remove the World Model and the doppelganger is invisible; remove the contract and a talked-into model could still move money.
- The model never decides. Zetaris supplies the facts, the World Model resolves who is who, the mandate decides on graded evidence, and the contract makes that decision enforceable at the payment system.
