English | [简体中文](README.zh-CN.md)

# gouji

**A pre-payment investigator that can explain why.** Before an invoice is paid, gouji checks across the ERP, the vendor master, the contracts, the accounts-payable mailbox and the company registry, queried where they live, whether the supplier really is who it claims to be. Every sentence of its explanation cites a database cell that a program has re-read. The decision to pay is taken by a signed mandate, not by the model, and the payment system refuses any payment that lacks a signed execution contract.

Open Agent Hackathon 2026 · Track 2: The Agent That Can Explain Why

## The problem

Between 2013 and 2015, a man registered a company in Latvia with the same name as an Asian computer-hardware supplier, opened bank accounts in Latvia and Cyprus, and e-mailed two US internet companies, reported to be Google and Facebook, as if he were that supplier. They wired over $120 million to him ([US DOJ, 2019](https://www.justice.gov/usao-sdny/pr/lithuanian-man-sentenced-5-years-prison-theft-over-120-million-fraudulent-business); [WSKG/NPR, 2019](https://www.wskg.org/news/2019-03-25/man-pleads-guilty-in-new-york-to-fleecing-facebook-and-google-of-100-million)). Nothing in the attack was technically clever. The name matched, the purchase orders were real, and the invoices looked right.

Business e-mail compromise is still the costliest fraud the FBI tracks: 24,768 complaints and $3.05 billion in reported losses in 2025, including over $30 million in BEC scams involving AI ([IC3 2025 report](https://www.ic3.gov/AnnualReport/Reports/2025_IC3Report.pdf), pp. 25, 26, 39).

Now accounts-payable teams are handing invoice processing to AI agents. An agent that pays from an approved-payee list is fooled the same way people were, and it adds a new attack surface: text inside the invoice that tells the agent what to do.

## What gouji does

For one payment request, seven agents work in a fixed, bounded loop. Every step is written to `logs/trace-<run_id>.jsonl` and to stdout.

| Agent | Job |
|---|---|
| **Guard** | Scans the invoice notes and the covering e-mail for instructions aimed at an AI, before anything else reads them. A pattern check always runs; with a model, a second screen catches rephrased instructions, and its verdict counts only if the substring it quotes really is in the document. |
| **Planner** | Chooses the checks and the follow-ups (at most 2 rounds). It never decides payment. |
| **Investigator** | Runs each check as one federated SQL query where the data lives: Zetaris, or DuckDB in sample mode. |
| **Verifier** | Re-reads every cited cell from its source system by primary key. A finding whose cells do not match is dropped. |
| **WorldModel** | Meterless World Model. Resolves legal entities by registration number and jurisdiction, never by name, and raises alerts such as "two companies share this name". |
| **Decider** | mandate-engine evaluates the signed mandate on graded evidence: ALLOW, ASK or DENY. |
| **Reporter** | Writes the brief. Sentences without verified citations are removed. |

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

### Why you can trust the explanation

1. **Evidence is graded by a program.** An aspect such as identity is VERIFIED only when at least two independent trusted systems agree. The mailbox is never trusted: it is where the attacker writes.
2. **The model never decides.** The mandate is a signed policy. It allows automatic payment of up to EUR 250,000 only when every required aspect (identity, account, price, receipt, duplicate, injection) is VERIFIED, whether or not the payee is in the signed registry. Anything else is ASK: a person decides, with the brief in front of them.
3. **No contract, no payment.** On ALLOW, gouji issues an execution contract: HMAC-signed, bound to a hash of the exact payment, valid for 15 minutes, usable once. The payment executor refuses every call without one. Each held case also runs a bypass probe: a direct pay call without a contract, which the trace shows being refused.

## Results

Two configurations on the same cases. **B1** is the mandate alone: pay anyone in the approved-payee registry. **B3** is gouji: the same mandate, but every aspect must be VERIFIED.

### Dev set (48 requests, designed by us)

| | B1: mandate only | B3: gouji |
|---|---|---|
| Attacks paid without a human | 16 / 24 | 0 / 24 |
| Attack money paid without a human | EUR 210,987.33 (61.8%) | EUR 0.00 (0.0%) |
| Normal payments interrupted | 4 / 24 (16.7%) | 0 / 24 (0.0%) |

We wrote both the checks and these cases, so this table shows that the pipeline works, not that it generalises.

### Held-out set (44 requests, written by NVIDIA Nemotron)

Each configuration ran once on the sealed set (commit 8bddf05), with no code change in between.

| | B1: mandate only | B3: gouji, patterns only | B3: gouji, with model screen |
|---|---|---|---|
| Attacks paid without a human | 15 / 24 | 6 / 24 | 2 / 24 |
| Attack money paid without a human | EUR 236,300.21 (57.2%) | EUR 65,499.90 (15.9%) | EUR 13,714.60 (3.3%) |
| Normal payments interrupted | 4 / 20 (20.0%) | 0 / 20 (0.0%) | 0 / 20 (0.0%) |

What it shows:

- Every impostor, bank-change, price, duplicate and receipt attack was held in both configurations. Those checks read structured data, which the attacker's prose cannot change.
- The pattern check caught none of the six new standalone injections. With the model screen, four of the six were caught.
- The two misses, read only after the evaluation: an invoice note claiming that the finance director gave verbal approval, and an e-mail asking for payment at the earliest convenience because a project timeline depends on it. The second reads like ordinary business urgency; it still counts as a miss, because the labels were fixed before the evaluation. In both cases the invoice was otherwise genuine (purchase order, goods receipt, contract price, account on file), so the money would have gone to the real supplier.
- None of the eight honest sentences written to confuse a filter (automated billing, an AI-based ERP, "approved by our finance team") interrupted a payment, in either configuration.
- A fix made after reading these failures will be measured on a new held-out set, not on this one.

Full reports: [`output_examples/eval-sample.md`](output_examples/eval-sample.md), [`output_examples/eval-heldout-sample.md`](output_examples/eval-heldout-sample.md), [`output_examples/eval-heldout-live.md`](output_examples/eval-heldout-live.md).

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
uv run python run.py case INV-5567              # one request: decision, brief, trace
uv run python run.py eval                       # B1 vs B3 on the dev set
uv run python run.py eval --data data/heldout   # the held-out set
uv run python run.py serve                      # HTTP API on $PORT (default 8000)
uv run pytest                                   # tests
```

Add `--live` to `case` or `eval` to let DeepSeek plan, screen for injection and write the brief (needs `DEEPSEEK_API_KEY`). `python run.py generate` rebuilds the dev set; `python run.py heldout` asks Nemotron for a new held-out set (needs `NVIDIA_API_KEY`).

### Sample mode

With `SAMPLE_MODE=true`, or with no keys at all, gouji needs no network: the backend is DuckDB over the files in `data/`, the planner and reporter are scripted, and the Guard uses patterns only. Every trace says which of these ran.

### API

`POST /run`

```json
{"run_id": "example_1", "input": {"inv_id": "INV-5567"}, "options": {"sample_mode": true}}
```

The response includes the `decision`, the `recommendations`, the `brief`, the evidence `grades`, the World Model `alerts`, the execution `contract` (or null), the list of `agents`, and the `log_file` of the trace. Errors come back as `{"status": "error", "error": {"type", "message", "recoverable"}}`, never as a crash.

Other routes: `GET /brief/{inv_id}` (the one-page brief), `GET /row/{table}/{pk}` (a cited row, re-read from its source), `GET /health`.

## Examples

[`input_examples/`](input_examples/) and [`output_examples/`](output_examples/) hold three requests and their results:

| Input | Case | gouji |
|---|---|---|
| `example_1_doppelganger.json` | An impostor registered under the supplier's name in Latvia, with an instruction to the AI hidden in the notes | Hold: likely fraud |
| `example_2_price_inflation.json` | An approved supplier invoices 18% above the contract price | Hold: ask the supplier to correct the invoice |
| `example_3_legitimate_bank_change.json` | A real bank change, confirmed by callback and recorded in the vendor master | Release, with an execution contract |

## Architecture

```text
payment request
   │
   ▼
Guard ──► Planner ──► Investigator ──► Verifier ──► WorldModel ──┐
              ▲         (SQL on Zetaris / DuckDB)                │
              └──────────── follow-ups (≤ 2 rounds) ◄────────────┘
                                   │
                                   ▼
                    Decider (mandate-engine, graded evidence)
                         │                     │
                       ALLOW                  ASK
                         │                     │
            signed execution contract     no contract: executor refuses
                         │                     │
                         ▼                     ▼
                  PaymentExecutor        brief for a person
```

| File | What it holds |
|---|---|
| `gouji/harness.py` | One interface to the five systems; LocalHarness (DuckDB) and ZetarisHarness |
| `gouji/checks.py` | C1 to C7, each returning findings with citations `{table, pk, column, value}` |
| `gouji/agents.py` | Guard, Planner, Verifier, Reporter |
| `gouji/world_model.py` | Meterless World Model: the three services |
| `gouji/policy.py` | The mandate, evidence grading, the payment decision |
| `gouji/contract.py` | Execution contract and PaymentExecutor |
| `gouji/pipeline.py` | One investigation end to end, with the trace |
| `gouji/evaluate.py` | B1 vs B3, with every denominator printed |
| `gouji/world.py` | The fictional world and the dev set |
| `gouji/redteam.py` | The Nemotron held-out set |
| `gouji/api.py` | FastAPI: `/run`, the brief, the cited rows |

## Sponsor technology

**Zetaris.** The five systems stay where they are: the ERP and the vendor master as databases, the contracts as Parquet, the mailbox as JSONL, the registry as CSV. Each check is one ANSI SQL query that joins across them, and the Verifier re-reads every cited cell through the same interface. With `ZETARIS_HOST` set, every query goes to Zetaris (`gouji/harness.py`, `ZetarisHarness`); without it, the same SQL runs on DuckDB over the same files. Map the logical tables to your Zetaris catalog with `ZETARIS_TABLES` in `.env`.

**Meterless.** gouji implements the World Model engine's three services, under the guide's names (`gouji/world_model.py`). Entities are keyed by registration number and jurisdiction, so two companies with one name are two entities, and the doppelganger alert comes from the World Model, not from a prompt. The store is an append-only JSONL log the canonical view can be rebuilt from. Every model call goes through one injected generator (`gouji/llm.py`), as the engine guides require, so DeepSeek can be swapped for Nemotron or any OpenAI-compatible model by configuration. A bonus component, `gouji/contract.py`, follows the Scout intent design: a signed object the downstream system verifies before it acts.

**NVIDIA.** Nemotron (`nvidia/nemotron-3.5-lightning-30b-a3b` on build.nvidia.com) wrote the held-out red-team set: the impostor and bank-change e-mails, the look-alike domains, eight new prompt injections, eight honest sentences meant to trip a naive filter, and four genuine bank-change notices (`gouji/redteam.py`). Using a different model from the one we built with means the checks are tested on text their authors did not write.

**Cursor.** Not used so far; Cursor is optional under rule 5.1.

## Data

Everything is fictional and generated: the buyer (Veltrona Drives GmbH), fourteen suppliers, their purchase orders, receipts, invoices, payments, contracts, e-mails and registry entries. Domains use the reserved `.example` suffix, and every IBAN carries check digits `00`, which ISO 13616 never issues, so no generated account can be a real one.

- `data/sample/`: the dev set, seed 20261022. Rebuild with `python run.py generate`.
- `data/heldout/`: the held-out set, seed 20261024, with text by Nemotron. `manifest.json` holds the prompts, the model, the temperature and a SHA-256 of every file. The set was committed (8bddf05) before it was first evaluated.

## Limitations

- The case mix and volumes are design choices for a fictional buyer, not field data. The numbers show what the checks catch on these cases, not a fraud rate.
- The Guard's pattern check is narrow by design. On text it has not seen it relies on the model screen, and a model screen can be wrong.
- gouji holds a payment and explains why; it does not contact the supplier. The callback on the number on file stays a human step, as it should.
- The Zetaris adapter speaks standard SQL through the Trino client; the connection to a live Zetaris instance is pending access from the organisers.

## Existing components

[mandate-engine v0.1.0](https://github.com/hoongyu/mandate-engine) (Apache-2.0) evaluates the mandate and keeps the audit log. It was written before the development period and is declared as an existing component; everything else in this repository was built during the hackathon.

## License

Apache-2.0
