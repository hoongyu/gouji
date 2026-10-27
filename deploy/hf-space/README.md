---
title: PayProof
emoji: 🧾
colorFrom: gray
colorTo: red
sdk: docker
app_port: 8000
pinned: false
license: mit
short_description: No proof, no payment: a pre-payment checkpoint
---

# PayProof: live demo

No proof, no payment. Before an invoice is paid, PayProof checks across five fictional systems (ERP, vendor
master, contracts, accounts-payable mailbox, company registry) whether the supplier is who it claims to be.
Every sentence of its explanation cites a cell a program re-read, a policy the controller signed (not the model)
decides, and the payment gateway pays only against a contract signed by a notary that contains no model.

This Space runs in sample mode: DuckDB over the bundled fictional data, scripted planner and reporter, no
model calls and no keys. Open a payment request to see its one-page brief, or call the API:

```bash
curl -X POST https://<this-space>.hf.space/run -H "Content-Type: application/json" -d '{"input": {"inv_id": "INV-5567"}}'
```

Source code, evaluation and documentation: https://github.com/hoongyu/gouji (MIT).
