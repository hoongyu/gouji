---
title: gouji
emoji: 🧾
colorFrom: gray
colorTo: red
sdk: docker
app_port: 8000
pinned: false
license: mit
short_description: A pre-payment investigator that can explain why
---

# gouji: live demo

Before an invoice is paid, gouji checks across five fictional systems (ERP, vendor master, contracts,
accounts-payable mailbox, company registry) whether the supplier is who it claims to be. Every sentence of
its explanation cites a cell a program re-read, a signed mandate (not the model) decides whether money moves,
and the payment system refuses any payment without a signed execution contract.

This Space runs in sample mode: DuckDB over the bundled fictional data, scripted planner and reporter, no
model calls and no keys. Open a payment request to see its one-page brief, or call the API:

```bash
curl -X POST https://<this-space>.hf.space/run -H "Content-Type: application/json" -d '{"input": {"inv_id": "INV-5567"}}'
```

Source code, evaluation and documentation: https://github.com/hoongyu/gouji (MIT).
