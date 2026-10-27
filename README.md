English | [简体中文](README.zh-CN.md)

# PayProof

**No proof, no payment.** PayProof is the checkpoint between whoever wants to pay an invoice, an accounts-payable agent or a person, and the payment rail. Before money moves it investigates across the ERP, the vendor master, the contracts, the accounts-payable mailbox and the company registry, queried where they live, whether the supplier really is who it claims to be. It explains why with evidence a program has re-read, and it releases a payment only with a proof: a contract signed by a notary that contains no model, bound to this payment, this evidence and a policy the controller signed.

Open Agent Hackathon 2026 · Track 2: The Agent That Can Explain Why. The code and the repository go by its working name, *gouji*, from the Chinese 勾稽: cross-checking accounts against each other.

## The problem

Between 2013 and 2015, a man registered a company in Latvia with the same name as an Asian computer-hardware supplier, opened bank accounts in Latvia and Cyprus, and e-mailed two US internet companies, reported to be Google and Facebook, as if he were that supplier. They wired over $120 million to him ([US DOJ, 2019](https://www.justice.gov/usao-sdny/pr/lithuanian-man-sentenced-5-years-prison-theft-over-120-million-fraudulent-business); [WSKG/NPR, 2019](https://www.wskg.org/news/2019-03-25/man-pleads-guilty-in-new-york-to-fleecing-facebook-and-google-of-100-million)). Nothing in the attack was technically clever: the company name matched, and the e-mails looked like the supplier's.

Business e-mail compromise is the costliest fraud the FBI tracks after investment fraud: 24,768 complaints and $3.05 billion in reported losses in 2025, including over $30 million in BEC scams involving AI ([IC3 2025 report](https://www.ic3.gov/AnnualReport/Reports/2025_IC3Report.pdf), pp. 3, 25, 26, 39).

Now accounts-payable teams are handing invoice processing to AI agents. An agent is fooled the same way people were, and it adds a new attack surface: text inside the invoice that tells the agent what to do.

## Why today's checks let it through

| Check in use today | What it asks | Against the impostor |
|---|---|---|
| Approved-payee list | Is the account on our list? | Passes once a forged onboarding pack gets it listed. In our tests the list paid every such impostor (3 of 3 in each set). |
| Verification of Payee (EU, mandatory for euro transfers since 9 October 2025) | Does the account holder's name match the name we typed? | Passes: the impostor's company is registered under that very name ([KPMG](https://kpmg.com/de/en/home/insights/2025/10/verification-of-payee.html)). |
| Three-way match | Do the order, the goods receipt and the invoice agree? | Passes: the impostor bills a real order. |
| An AI agent reading the invoice | Does the invoice look right? | The invoice can tell it what to think. |
| **PayProof** | Is the issuer the legal entity we contracted, by registration number, according to two systems the attacker cannot write to? | **Fails: hold.** |

## Three guarantees

Each one is a property of the code, and each has a test you can run.

1. **Words cannot move money.** Invoice text, e-mails and the model's own output never reach the decision. Grades come from structured records in trusted systems; the decision comes from a signed policy; a payment needs a notary's signature. We handed the model to the attacker (`python run.py eval --hostile`): it denied every injection, skipped every follow-up check and argued for paying in every brief. PayProof released no attack it had held without a model (0 of 18 attacks after money on the held-out set), and the brief filter removed 80 of its sentences: each one that argued against a hold or cited a finding that does not exist.
2. **Every claim can be checked.** Each sentence of an explanation cites database cells that the Verifier re-read from their system of record. Each decision leaves a proof file, and `python run.py verify <proof>` checks it later without trusting anything in it: the controller's signature on the policy, every cited cell read again through Zetaris, the decision derived again by the program, the notary's signature, and for a release, the whole investigation run once more without a model.
3. **Nothing pays without a proof.** Only the notary can sign an execution contract, with its own Ed25519 key, and it contains no model: it runs every check again on the systems of record and signs only if its own decision, under the controller-signed policy, is ALLOW. The contract binds the payment, the evidence (a hash of every cited cell and its value) and the policy; it is valid for 15 minutes and usable once. The payment gateway holds no private key, only the notary's public key, and keeps spent contracts in a hash-chained ledger that survives a restart.

Because the notary decides without a model, a model can make PayProof stricter (flag an injection, add a check) but never looser: money goes out only when the investigation without a model would have released it too.

![The one-page brief for an impostor's invoice: Hold, decided by the signed policy; the cited explanation; the quarantined instruction to the AI](docs/brief-hold.jpg)

## Threat model

| Attacker | Controls | Would need, to be paid | Stopped by | Shown by |
|---|---|---|---|---|
| Impostor under the supplier's name | a registered company, e-mails, invoices | the contract and the vendor master to name its registration number | identity is VERIFIED only when two trusted systems agree on the registration number; the World Model keys companies by it | held-out impostors: 0 of 6 paid |
| Bank-change fraudster | a look-alike domain, e-mails, perhaps a vendor-master edit without callback | a change confirmed by callback, in the supplier's jurisdiction | checks C2 and C6; World Model alerts | held-out bank changes: 0 of 6 paid |
| Overbilling, duplicate, goods never received | the invoice | the contract price, the goods receipt, the payment history to agree | checks C3, C4, C5 | held-out: 0 of 6 paid |
| Prompt injector | any text in invoices and e-mails | the text to change a grade or the policy | text never reaches grades or the decision; the Guard quarantines what it recognises | no attack after money paid even where the Guard missed the injection |
| Compromised model | everything the model says | the model-free notary to agree | the notary re-derives without a model; the brief filter | `eval --hostile`: 0 of 18 attacks after money paid; 80 sentences removed |
| Compromised agent code | the agent's process | the notary's private key | the gateway accepts only the notary's Ed25519 signature | test: a contract signed with any other key is refused |
| Replay or tampering | an old or edited contract | a fresh notary signature | expiry, single use in a persistent ledger, binding to payment, evidence and policy | tests: reuse after restart, longer validity, other amount, old policy: all refused |
| Policy tampering | the policy file | the controller's private key | the controller's signature, checked on load and before every contract | test: a raised payment cap is refused and nothing is signed |

Not covered, by design or for now:

- An insider who can change two independent systems of record, for example the contract repository and the vendor master.
- A compromised company registry.
- A person who releases a held payment against the brief's advice. PayProof tells them to call the supplier on the number on file; it cannot make them.
- Key custody. In this repository the controller, notary and gateway keys sit on one machine, and the notary runs inside the agent's process as a separate component. In a deployment the notary and the gateway would be separate services with their keys in an HSM. The model never runs code here: it only returns text, which is parsed into typed values.

## What PayProof does

For one payment request, seven agents investigate in a fixed, bounded loop; then the notary and the gateway, neither of which uses a model, decide whether any money moves. Every step is written to `logs/trace-<run_id>.jsonl` and to stdout, and every decision to a proof file.

| Component | Job |
|---|---|
| **Guard** | Scans the invoice notes and the covering e-mail for instructions aimed at an AI, before anything else reads them. A pattern check always runs; with a model, a second screen catches rephrased instructions, and its verdict counts only if the substring it quotes really is in the document. |
| **Planner** | Adds follow-up checks (at most 2 rounds). It cannot remove the standard checks and never decides payment. |
| **Investigator** | Runs each check as one federated SQL query where the data lives: Zetaris, or DuckDB in sample mode. |
| **Verifier** | Re-reads every cited cell from its source system by primary key. A finding whose cells do not match is dropped. |
| **WorldModel** | Meterless World Model. Resolves legal entities by registration number and jurisdiction, never by name, and raises alerts such as "two companies share this name". |
| **Decider** | mandate-engine applies the controller-signed policy to the graded evidence: ALLOW or ASK. |
| **Reporter** | Writes the brief. Sentences without verified citations are removed, and on a hold, so are sentences that argue for paying. |
| **Notary** | No model. On ALLOW it runs every check again, re-reads every cell, applies the signed policy, and signs an Ed25519 execution contract only if it reaches ALLOW for the same payment. |
| **Gateway** | Holds no private key, only the notary's public key. Pays against a valid, unused contract bound to the payment; refuses everything else. |

The seven checks:

| Check | Question | Sources |
|---|---|---|
| C1 identity | Is the issuer the same legal entity as the contract counterparty? | registry, contracts, vendor master |
| C2 account | Is the paying account on file, and was every change to it confirmed by callback? | vendor master, contracts |
| C3 price | Is the unit price within 2% of the contract in force on the invoice date? | contracts, ERP |
| C4 receipt | Were the goods received, and not fewer than invoiced? | ERP |
| C5 duplicate | Was this invoice, or the same purchase order, already paid? | ERP |
| C6 channel | Did the request come from a domain on file, or from a look-alike (edit distance, homoglyphs)? | mailbox, vendor master |
| C7 injection | Does the text try to instruct the AI? | ERP, mailbox |

An aspect such as identity is VERIFIED only when at least two independent trusted systems agree. The mailbox is never trusted: it is where the attacker writes. The signed policy allows automatic payment of up to EUR 250,000 only when every required aspect (identity, account, price, receipt, duplicate, injection) is VERIFIED; anything else is ASK, and a person decides with the brief in front of them.

## Results

**B1** is a payee list: pay anyone whose account is in the approved-payee registry, up to the same cap. **B3** is PayProof. Attacks are counted two ways: those after money the buyer does not owe (an impostor, a changed account, an inflated price, a duplicate, goods never received), and genuine invoices that only carry an instruction to the AI. Paying one of the latter pays the real supplier what it is owed, so it is kept apart.

### Held-out set (44 requests, written by NVIDIA Nemotron)

The set was sealed (commit efa9fec) before it was first evaluated, and no code was tuned on it since.

| | B1: payee list | B3: no model | B3: with model screen | B3: model controlled by the attacker |
|---|---|---|---|---|
| Attacks after money not owed, paid without a human | 9 / 18 (EUR 170,800.31) | 0 / 18 | 0 / 18 | 0 / 18 |
| of which to an impostor's or attacker's account | 3 / 18 (EUR 58,740.50) | 0 / 18 | 0 / 18 | 0 / 18 |
| Genuine invoices carrying an instruction to the AI, paid | 6 / 6 | 6 / 6 | 2 / 6 | 6 / 6 |
| Normal payments interrupted | 4 / 20 (20.0%) | 0 / 20 | 0 / 20 | 0 / 20 |

- Every impostor, bank-change, price, duplicate and receipt attack was held in every configuration. Those checks read structured data, which the attacker's prose cannot change.
- The model screen caught four of the six instructions that the pattern check missed. The two it missed (a note claiming the finance director gave verbal approval, and an e-mail asking for payment at the earliest convenience because a project depends on it) sat on genuine invoices: purchase order, goods receipt, contract price, account on file. The labels were fixed before the evaluation, so they count as misses.
- With the model in the attacker's hands, PayProof behaves exactly as it does without a model: the notary decides without one. The hostile model only switched off the extra screen.
- None of the eight honest sentences written to confuse a filter (automated billing, an AI-based ERP, "approved by our finance team") interrupted a payment.
- The column "with model screen" is the run of 24 October, before the notary existed. The notary can only turn a release into a hold, never the reverse, so it cannot raise these numbers; it confirmed all 26 releases in the runs without a model.

### Dev set (48 requests, designed by us)

| | B1: payee list | B3: PayProof |
|---|---|---|
| Attacks after money not owed, paid without a human | 15 / 23 (EUR 197,089.83) | 0 / 23 |
| of which to an impostor's or attacker's account | 3 / 23 (EUR 57,011.40) | 0 / 23 |
| Genuine invoices carrying an instruction to the AI, paid | 1 / 1 | 0 / 1 |
| Normal payments interrupted | 4 / 24 (16.7%) | 0 / 24 |

We wrote both the checks and these cases, so this table shows that the pipeline works, not that it generalises.

Full reports: [`eval-sample.md`](output_examples/eval-sample.md), [`eval-hostile.md`](output_examples/eval-hostile.md), [`eval-heldout-sample.md`](output_examples/eval-heldout-sample.md), [`eval-heldout-hostile.md`](output_examples/eval-heldout-hostile.md), [`eval-heldout-live.md`](output_examples/eval-heldout-live.md).

## Check a decision yourself

Every investigation writes a proof file (`logs/proofs/<run>/<invoice>.json`; the examples are in [`output_examples/`](output_examples/)). Verifying one trusts nothing in it:

```bash
uv run python run.py verify output_examples/zetaris-run/INV-5559-proof.json --backend zetaris
```

```text
Proof output_examples/zetaris-run/INV-5559-proof.json: INV-5559, decision ALLOW, judged at 2026-10-20T09:00:00+00:00
  [ok] The policy carries the controller's signature: ap-payments v2, controller key bcdf6089495e4149
  [ok] The decision was taken under this policy: sha256 3086c1d774b38882
  [ok] Every cited cell reads the same in zetaris today: 18 of 18 cells match
  [ok] The evidence root matches the cited cells: 8a07e7069954995e
  [ok] The World Model raises the same alerts: none
  [ok] The signed mandate decides the same on this evidence: allow (P2)
  [ok] The contract carries the notary's signature: EC-96e4f180, notary key 2c9d7b4eb936d38e
  [ok] The notary's cells read the same in zetaris today: 17 of 17 cells match
  [ok] The contract binds this payment, this evidence and this policy: facts 38dd54349306, evidence 8a07e7069954, policy 3086c1d774b3
  [ok] Run again without a model, the investigation releases it too: allow after 35 queries
VALID: 10 of 10 checks pass (46 queries on zetaris)
```

Edit a cited value in the proof, any field of the contract, or the policy file, and the matching check fails (`tests/test_gouji.py`); a cell that has changed in its source system fails the same way. A hold verifies too: the impostor's proof passes 7 of 7 checks, the last being that no contract was issued.

## Quick start

### Docker

```bash
cp .env.example .env        # optional: without keys everything runs in sample mode
docker build -t gouji .
docker run --rm -p 8000:8000 --env-file .env gouji
```

Then:

```bash
curl -X POST http://localhost:8000/run -H "Content-Type: application/json" -d @input_examples/example_1_doppelganger.json
```

Open http://localhost:8000/ for the list of open payment requests, and click one for its brief.

### Without Docker

Python 3.12 or newer and [uv](https://docs.astral.sh/uv/):

```bash
uv sync
uv run python run.py case INV-5567              # one request: decision, brief, trace, proof
uv run python run.py verify output_examples/INV-5559-proof.json
uv run python run.py eval                       # B1 vs B3 on the dev set
uv run python run.py eval --hostile             # the same, with a model the attacker controls
uv run python run.py eval --data data/heldout   # the held-out set
uv run python run.py serve                      # HTTP API on $PORT (default 8000)
uv run pytest                                   # tests
```

Add `--live` to `case` or `eval` to let DeepSeek plan, screen for injection and write the brief (needs `DEEPSEEK_API_KEY`). `python run.py generate` rebuilds the dev set; `python run.py heldout` asks Nemotron for a new held-out set (needs `NVIDIA_API_KEY`).

### Keys and the signed policy

`keys/controller.pub`, `keys/trusted/notary-2c9d7b4e.pub` (the notary that signed the example proofs) and the two signed policies in `policy/` are in the repository, so a fresh clone checks the policy and verifies the example proofs without any private key. The notary on your machine makes its own key pair in `keys/` on first run; private keys are git-ignored and never copied into the Docker image. To act as the controller yourself, for example after regenerating the data, `python run.py policy --data data/sample` creates `keys/controller.key` if there is none and signs the policy again.

### Sample mode

With `SAMPLE_MODE=true`, or with no keys at all, PayProof needs no network: the backend is DuckDB over the files in `data/`, the planner and reporter are scripted, and the Guard uses patterns only. Every trace says which of these ran.

### API

`POST /run`

```json
{"run_id": "example_1", "input": {"inv_id": "INV-5567"}, "options": {"sample_mode": true}}
```

The response includes the `decision`, the `recommendations`, the `brief`, the evidence `grades`, the World Model `alerts`, the `notary` re-check, the execution `contract` (or null), the `proof_file`, the list of `agents`, and the `log_file` of the trace. Errors come back as `{"status": "error", "error": {"type", "message", "recoverable"}}`, never as a crash.

Other routes: `GET /brief/{inv_id}` (the one-page brief, with its proof), `GET /row/{table}/{pk}` (a cited row, re-read from its source), `GET /health`.

## Running on Zetaris

In sample mode the checks run on DuckDB over the files in `data/`. On Zetaris the same SQL runs federated across the five systems where they live: two PostgreSQL databases and three files on S3-compatible storage. Nothing here needs credentials in the repository: the scripts generate local passwords into a git-ignored file, and the Zetaris API key stays in your `.env`.

**What you need.** A running Zetaris instance (the local Docker install from [Zetaris getting-started](https://zetaris.github.io/getting-started), or an AWS cluster); Docker, for the stand-in PostgreSQL and S3 store (Adobe S3Mock); and in `.env` your `ZETARIS_REST_URL` (local default `http://localhost:8888/api/v1.0`), `ZETARIS_ORG_ID` and an API key `ZETARIS_API_KEY` created under Management > API Tokens.

**Steps, in order.**

```bash
uv run python scripts/zetaris_sources.py up        # start PostgreSQL (5433) and an S3 store (9000), local passwords
uv run python scripts/zetaris_sources.py load      # ERP and vendor master into PostgreSQL, the documents into S3
uv run python scripts/zetaris_sources.py register  # the statements in deploy/zetaris-sources/register.sql
uv run python scripts/zetaris_sources.py check     # SELECT 1, SHOW LIGHTNING DATABASES, row counts vs local
uv run python run.py case INV-5567 --backend zetaris
uv run python run.py eval --backend zetaris
```

The setup SQL, in execution order and with the passwords as placeholders, is [`deploy/zetaris-sources/register.sql`](deploy/zetaris-sources/register.sql): two `CREATE DATASOURCE` plus `REGISTER DATASOURCE TABLES` for the databases, one `CREATE LIGHTNING DATABASE` and three `CREATE LIGHTNING FILESTORE TABLE` for the files.

**One of the queries.** C1, the identity check, joins three systems in one statement (as sent to Zetaris for INV-5567):

```sql
SELECT i.inv_id, i.issuer_reg_no, p.po_id, v.vendor_id, v.reg_no AS master_reg_no,
       c.contract_id, c.vendor_reg_no AS contract_reg_no, c.jurisdiction
FROM erp.invoices i
JOIN erp.purchase_orders p ON p.po_id = i.po_ref
JOIN vendor_master.vendors v ON v.vendor_id = p.vendor_id
LEFT JOIN documents.contracts c ON c.vendor_reg_no = v.reg_no AND c.item = p.item AND c.amendment_of IS NULL
WHERE i.inv_id = 'INV-5567'
```

| inv_id | issuer_reg_no | po_id | vendor_id | master_reg_no | contract_id | contract_reg_no | jurisdiction |
|---|---|---|---|---|---|---|---|
| INV-5567 | LV-SYN-90501 | PO-7767 | V-101 | TW-SYN-48213 | C-101 | TW-SYN-48213 | TW |

The invoice comes from a Latvian registration while the order, the vendor master and the contract all point to the Taiwanese one: that row is findings F2 and F3 in the brief above.

**Run record.** 27 October 2026, 11:06 to 11:14 CET, on a local Zetaris 2.4.3 install (Docker, hackathon build v2.4.3.1) with the dev set (`data/sample`, seed 20261022), DeepSeek planning, screening and writing. All nine tables are registered, and their row counts on Zetaris equal the local files (86, 84, 90, 42, 20, 12, 18, 63, 20). Three requests were investigated with every query on Zetaris, with the same decisions and evidence grades as on DuckDB: INV-5567 (the impostor: ASK, hold as likely fraud), INV-5579 (18% over the contract: ASK, have the supplier correct it) and INV-5559 (a genuine bank change: ALLOW; the notary re-checked it without a model in 35 queries and signed contract EC-96e4f180). 160 federated queries in all (46, 40 and 74), about 2.5 s each on the laptop-sized engine (2 cores). The three proofs were then verified through Zetaris, with 72 more queries: 7 of 7, 7 of 7 and 10 of 10 checks pass. Every statement sent, with its row count and timing, and every proof are in [`output_examples/zetaris-run/`](output_examples/zetaris-run/). One thing learned on the way: Zetaris reads a JSON file as one document, so the mailbox is stored as a JSON array.

**Objects created, and cleanup.** In Zetaris: datasources `erp` and `vendor_master` with their registered tables, and Lightning database `documents` with the file tables `contracts`, `registry` and `mailbox`. In Docker: the `postgres` and `s3` containers of `deploy/zetaris-sources` and the PostgreSQL volume. To remove them: `DROP DATASOURCE erp` and `DROP DATASOURCE vendor_master` in the Zetaris SQL Editor, drop the `documents` tables there, then `docker compose down -v` in `deploy/zetaris-sources`.

## Examples

[`input_examples/`](input_examples/) and [`output_examples/`](output_examples/) hold three requests and their results:

| Input | Case | PayProof |
|---|---|---|
| `example_1_doppelganger.json` | An impostor registered under the supplier's name in Latvia, with an instruction to the AI hidden in the notes | Hold: likely fraud |
| `example_2_price_inflation.json` | An approved supplier invoices 18% above the contract price | Hold: ask the supplier to correct the invoice |
| `example_3_legitimate_bank_change.json` | A real bank change, confirmed by callback and recorded in the vendor master | Release, with a notary-signed execution contract |

## Architecture

```text
payment request (invoice, e-mail: untrusted)
   │
   ▼
Guard ──► Planner ──► Investigator ──► Verifier ──► WorldModel ──┐     model: plans and writes only
              ▲         (SQL on Zetaris / DuckDB)                │
              └──────────── follow-ups (≤ 2 rounds) ◄────────────┘
                                   │
                                   ▼
             Decider: mandate-engine + policy signed by the controller (Ed25519)
                         │                     │
                       ALLOW                  ASK ──► brief for a person; no contract
                         │
                         ▼
             Notary (no model): every check again, signed policy again
                         │ ALLOW for the same payment
                         ▼
             execution contract, Ed25519, bound to payment + evidence + policy, 15 min, once
                         │
                         ▼
             Gateway: notary's public key only, persistent ledger ──► pays
```

| File | What it holds |
|---|---|
| `gouji/harness.py` | One interface to the five systems; LocalHarness (DuckDB) and ZetarisHarness |
| `gouji/checks.py` | C1 to C7, each returning findings with citations `{table, pk, column, value}` |
| `gouji/agents.py` | Guard, Planner, Verifier, Reporter |
| `gouji/world_model.py` | Meterless World Model: the three services |
| `gouji/policy.py` | The mandate, the signed policy file, evidence grading, the payment decision |
| `gouji/notary.py` | The notary: re-derivation without a model, and the only signing key for contracts |
| `gouji/contract.py` | Execution contract, evidence root, and the payment gateway |
| `gouji/signing.py` | Ed25519 keys and signatures |
| `gouji/verify.py` | Checks a proof file after the fact |
| `gouji/pipeline.py` | One investigation end to end, with the trace and the proof |
| `gouji/evaluate.py` | B1 vs B3, with every denominator printed |
| `gouji/world.py` | The fictional world and the dev set |
| `gouji/redteam.py` | The Nemotron held-out set |
| `gouji/api.py` | FastAPI: `/run`, the brief, the cited rows |

## Sponsor technology

**Zetaris.** The five systems stay where they are: the ERP and the vendor master as databases, the contracts as Parquet, the mailbox as JSON, the registry as CSV. Each check is one ANSI SQL query that joins across them; the Verifier, the notary and `verify` re-read every cited cell through the same interface, from the system of record, at the moment it matters. With `ZETARIS_REST_URL` and `ZETARIS_API_KEY` set, every query goes to Zetaris through its REST API (`gouji/harness.py`, `ZetarisHarness`; no Java or JDBC driver needed); without them, the same SQL runs on DuckDB over the same files. Map the logical tables to your Zetaris catalog with `ZETARIS_TABLES` in `.env`.

**Meterless.** PayProof implements the World Model engine's three services, under the guide's names (`gouji/world_model.py`). Entities are keyed by registration number and jurisdiction, so two companies with one name are two entities, and the doppelganger alert comes from the World Model, not from a prompt. The store is an append-only JSONL log the canonical view can be rebuilt from. Every model call goes through one injected generator (`gouji/llm.py`), as the engine guides require, so DeepSeek can be swapped for Nemotron or any OpenAI-compatible model by configuration, or for the attacker's model in `eval --hostile`. A bonus component follows the Scout intent design: a signed object the downstream system verifies before it acts. Here it is the notary's Ed25519 execution contract (`gouji/notary.py`, `gouji/contract.py`).

**NVIDIA.** Nemotron (`nvidia/nemotron-3.5-lightning-30b-a3b` on build.nvidia.com) wrote the held-out red-team set: the impostor and bank-change e-mails, the look-alike domains, eight new prompt injections, eight honest sentences meant to trip a naive filter, and four genuine bank-change notices (`gouji/redteam.py`). Using a different model from the one we built with means the checks are tested on text their authors did not write.

**Cursor.** Not used; Cursor is optional under rule 5.1.

## Data

Everything is fictional and generated by `gouji/world.py`: the buyer (Veltrona Drives GmbH), fourteen suppliers, the impostors pretending to be them, and every record below. Domains use the reserved `.example` suffix, and every IBAN carries check digits `00`, which ISO 13616 never issues, so no generated account can be a real one. Every case is judged as of 2026-10-20 09:00 UTC; paid history starts about 60 days earlier.

| System and format | Tables (on Zetaris) | One row is | Rows: dev / held-out |
|---|---|---|---|
| ERP, PostgreSQL (DuckDB file in sample mode) | `erp.purchase_orders` | a purchase order: supplier, item, quantity, unit price | 86 / 84 |
| | `erp.goods_receipts` | goods received against an order | 84 / 83 |
| | `erp.invoices` | an invoice: issuer name and registration, account to pay, notes, the e-mail it came with | 90 / 86 |
| | `erp.payments` | a payment already made | 42 / 42 |
| Vendor master, PostgreSQL | `vendor_master.vendors` | a supplier record: registration, account on file, known domains | 20 / 20 |
| | `vendor_master.vendor_changes` | a change to a record: field, old and new value, how it was requested, whether a callback confirmed it | 12 / 12 |
| Contracts, Parquet on S3 | `documents.contracts` | a contract or amendment: counterparty registration, jurisdiction, item, unit price, validity | 18 / 18 |
| AP mailbox, JSON on S3 | `documents.mailbox` | an e-mail: sender domain, body, attached invoice. Untrusted by design: it is where the attacker writes | 63 / 60 |
| Company registry, CSV on S3 | `documents.registry` | a registered legal entity: name, registration number, jurisdiction, incorporation date | 20 / 20 |

- `data/sample/`: the dev set, seed 20261022, 48 requests. Rebuild with `python run.py generate`.
- `data/heldout/`: the held-out set, seed 20261024, 44 requests, with text by Nemotron. `manifest.json` holds the prompts, the model, the temperature and a SHA-256 of every file. The set was committed (efa9fec) before it was first evaluated, and CI checks the seal on every change.

Limits of the data: the case mix and volumes are design choices for a fictional buyer, not field data; there are no foreign currencies, credit notes or multi-line invoices; the registry is a single snapshot.

## Limitations

- The case mix and volumes are design choices for a fictional buyer, not field data. The numbers show what the checks catch on these cases, not a fraud rate.
- The Guard's pattern check is narrow by design. On text it has not seen it relies on the model screen, and a model screen can be wrong; the guarantees above do not depend on it.
- PayProof holds a payment and explains why; it does not contact the supplier. The callback on the number on file stays a human step, as it should.
- Key custody and process separation are as described under the threat model: one machine, one process, separate keys.
- On Zetaris, each query takes about 3 seconds on a laptop-sized engine, so one investigation takes two to four minutes there (under a second on DuckDB). The full evaluations ran on DuckDB with the same SQL.

## Existing components

[mandate-engine v0.1.1](https://github.com/hoongyu/mandate-engine) (MIT OR Apache-2.0) evaluates the mandate and keeps the hash-chained audit log the gateway uses as its ledger. It was written before the development period and is declared as an existing component; everything else in this repository was built during the hackathon.

## License

MIT. See [LICENSE](LICENSE). The mandate-engine dependency is dual-licensed MIT OR Apache-2.0.
