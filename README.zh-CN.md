[English](README.md) | 简体中文

# PayProof

**没有证明，就不付款。** PayProof 是一道关卡，设在想付发票的一方（应付智能体或人）与付款通道之间。在钱付出去之前，它在 ERP、供应商主数据、合同、应付邮箱和公司注册信息里就地查询，调查供应商是不是真的就是它自称的那家公司。它用程序重新读过的证据讲清原因，并且只凭证明放行付款：证明是一份由不含模型的公证人（Notary）签名的合约，绑定这笔付款、这些证据，以及一份由财务负责人（controller）签名的策略。

Open Agent Hackathon 2026 · 赛道 2：The Agent That Can Explain Why。代码和仓库沿用工作名 *gouji*（勾稽：账目之间交叉核对）。

## 问题

2013 至 2015 年，有人在拉脱维亚注册了一家和亚洲某电脑硬件厂同名的公司，在拉脱维亚和塞浦路斯开了银行账户，然后冒充这家硬件厂，给 2 家美国互联网公司发邮件，据报道是 Google 和 Facebook。它们一共把超过 1.2 亿美元汇给了他（[美国司法部，2019](https://www.justice.gov/usao-sdny/pr/lithuanian-man-sentenced-5-years-prison-theft-over-120-million-fraudulent-business)；[WSKG/NPR，2019](https://www.wskg.org/news/2019-03-25/man-pleads-guilty-in-new-york-to-fleecing-facebook-and-google-of-100-million)）。这次攻击在技术上一点都不高明：公司名对得上，邮件看着就像供应商发的。

商业邮件诈骗（BEC）至今仍是 FBI 统计里损失最大的诈骗类型：2025 年报案 24,768 宗，报告损失 30.5 亿美元，其中涉及 AI 的 BEC 损失超过 3,000 万美元（[IC3 2025 年报](https://www.ic3.gov/AnnualReport/Reports/2025_IC3Report.pdf)，第 25、26、39 页）。

现在应付团队正把发票处理交给 AI 智能体。智能体会像当年的人一样被骗，而且它还多了一个新的攻击面：发票里告诉智能体该做什么的文字。

## 现有核查为什么拦不住它

| 现行核查 | 它问什么 | 面对冒名者 |
|---|---|---|
| 已批准收款人名单 | 这个账户在我们的名单上吗？ | 只要一套伪造的供应商准入材料让它上了名单，就能通过。在我们的测试里，名单给所有这类冒名者都付了款（每个数据集都是 3 个中付了 3 个）。 |
| 收款人核验（Verification of Payee；欧盟，自 2025 年 10 月 9 日起对欧元转账强制执行） | 账户持有人的名字和我们填的名字一致吗？ | 通过：冒名者的公司正是用这个名字注册的（[KPMG](https://kpmg.com/de/en/home/insights/2025/10/verification-of-payee.html)）。 |
| 三单匹配 | 订单、收货单和发票对得上吗？ | 通过：冒名者针对一张真实的订单开票。 |
| 读发票的 AI 智能体 | 这张发票看起来对吗？ | 发票可以告诉它该怎么想。 |
| **PayProof** | 依据攻击者写不进去的 2 个系统，按注册号核对，开票方是不是我们签约的那个法律实体？ | **不通过：拦下。** |

## 3 项保证

每项都是代码本身的性质，也都有一个你可以运行的测试。

1. **文字动不了钱。** 发票文本、邮件和模型自己的输出，都到不了决策这一步。证据分级来自可信系统里的结构化记录；决定来自签名的策略；付款需要公证人的签名。我们把模型交给了攻击者（`python run.py eval --hostile`）：它否认每一处注入的存在，跳过每一项追查，在每份简报里都主张付款。凡是不用模型时拦下的攻击，PayProof 一个都没有放行（留出集上冲着钱来的攻击，18 次中放行 0 次）；简报过滤删掉了它写的 80 句话，也就是所有反对拦下或者引用了不存在的结论的句子。
2. **每一条说法都能核对。** 解释里的每一句都引用了数据库单元格，这些单元格由 Verifier 从各自的记录系统重新读过。每个决定都会留下一份证明文件，事后用 `python run.py verify <proof>` 核对它时，不信任其中任何内容：核对策略上财务负责人的签名，通过 Zetaris 再读一遍每个被引用的单元格，由程序重新推导决定，核对公证人的签名；如果是放行，还要不用模型把整个调查再跑一遍。
3. **没有证明，什么都不付。** 只有公证人能签执行合约，用的是它自己的 Ed25519 密钥，而且公证人不含模型：它在记录系统上把每项核查重跑一遍，只有它在财务负责人签名的策略下自己得出的决定是 ALLOW，才会签名。合约绑定付款、证据（每个被引用单元格及其值的哈希）和策略；有效期 15 分钟，只能用一次。付款网关（Gateway）不持有私钥，只有公证人的公钥，并把用过的合约记进哈希链账本，重启后也不会丢失。

因为公证人做决定时不用模型，模型能让 PayProof 更严（标出一处注入、加一项核查），却永远不能让它更松：只有不用模型的调查也会放行时，钱才会付出去。

![冒名者发票的一页简报：结论是拦下，由签名的策略决定；带引用的解释；被隔离的写给 AI 的指令](docs/brief-hold.jpg)

## 威胁模型

| 攻击者 | 能控制什么 | 要拿到钱还需要 | 靠什么挡住 | 实证 |
|---|---|---|---|---|
| 冒用供应商名字的冒名者 | 一家注册公司、邮件、发票 | 合同和供应商主数据都写着它的注册号 | 只有 2 个可信系统的注册号一致时，身份才是 VERIFIED；世界模型按注册号识别公司 | 留出集冒名者：6 个中付了 0 个 |
| 改银行账户的诈骗者 | 一个仿冒域名、邮件，也许还有一处未经回拨的供应商主数据修改 | 一次经回拨确认、且在供应商所在法域的变更 | 核查 C2 和 C6；世界模型告警 | 留出集改账户：6 笔中付了 0 笔 |
| 超额开票、重复发票、货从未收到 | 发票 | 合同价、收货记录、付款历史都对得上 | 核查 C3、C4、C5 | 留出集：6 笔中付了 0 笔 |
| 提示注入者 | 发票和邮件里的任何文字 | 文字能改变某项分级或策略 | 文字永远到不了分级和决策；守卫隔离它识别出的内容 | 即使守卫漏掉了注入，也没有任何冲着钱来的攻击被付款 |
| 被攻破的模型 | 模型说的一切 | 不含模型的公证人也同意 | 公证人不用模型重新推导；简报过滤 | `eval --hostile`：冲着钱来的 18 次攻击里付了 0 次；删掉 80 句 |
| 被攻破的智能体代码 | 智能体的进程 | 公证人的私钥 | 付款网关只接受公证人的 Ed25519 签名 | 测试：用任何其他密钥签名的合约都被拒绝 |
| 重放或篡改 | 一份旧的或改过的合约 | 一个新的公证人签名 | 过期失效；在持久化账本里只能用一次；与付款、证据和策略绑定 | 测试：重启后再次使用、更长的有效期、别的金额、旧策略，全部被拒绝 |
| 篡改策略 | 策略文件 | 财务负责人的私钥 | 财务负责人的签名，加载时和每次签合约前都会核验 | 测试：调高付款上限会被拒绝，也不会签出任何东西 |

以下情况不在覆盖范围内，有的是设计如此，有的是暂时如此：

- 能修改 2 个独立记录系统的内部人员，比如合同库和供应商主数据。
- 被攻破的公司注册信息系统。
- 不顾简报建议、放行被拦付款的人。PayProof 会告诉他们按档案里的号码打电话给供应商，但没法强迫他们这么做。
- 密钥保管。在这个仓库里，财务负责人、公证人和付款网关的密钥放在同一台机器上，公证人作为独立组件运行在智能体的进程里。实际部署时，公证人和付款网关会是各自独立的服务，密钥放在 HSM 里。这里的模型从不运行代码：它只返回文本，文本再被解析成带类型的值。

## PayProof 做什么

对每一笔付款申请，7 个智能体在固定且有上限的循环里调查；然后由公证人和付款网关决定有没有钱付出去，这两者都不用模型。每一步都写进 `logs/trace-<run_id>.jsonl`，同时打印到标准输出；每个决定都写进一份证明文件。

| 组件 | 职责 |
|---|---|
| **Guard（守卫）** | 在任何环节读取之前，先扫描发票备注和随附邮件里有没有写给 AI 的指令。模式匹配每次都跑；接上模型时再加一道复核，抓换了说法的指令，但模型的判断只有在它引用的原文片段确实出现在文档里时才算数。 |
| **Planner（规划）** | 增加追查（最多 2 轮）。它不能删掉标准核查，也从不决定付款。 |
| **Investigator（调查）** | 每项核查是一条联邦 SQL 查询，在数据所在处执行：Zetaris，样例模式下是 DuckDB。 |
| **Verifier（核验）** | 按主键从源系统重新读取每一个被引用的单元格。单元格对不上的结论直接丢弃。 |
| **WorldModel（世界模型）** | Meterless World Model。按注册号和法域识别法律实体，从不按名称，并发出“这个名字有 2 家公司在用”之类的告警。 |
| **Decider（决策）** | mandate-engine 把财务负责人签名的策略应用到分级后的证据上：ALLOW 或 ASK。 |
| **Reporter（报告）** | 撰写简报。没有经核验引用的句子会被删掉；拦下时，主张付款的句子也会被删掉。 |
| **Notary（公证人）** | 不含模型。遇到 ALLOW 时，它把每项核查重跑一遍，重新读取每个单元格，应用签名的策略，只有对同一笔付款也得出 ALLOW，才签一份 Ed25519 执行合约。 |
| **Gateway（付款网关）** | 不持有私钥，只有公证人的公钥。只凭一份有效、未用过、绑定这笔付款的合约付款；其余一律拒绝。 |

7 项核查：

| 核查 | 问题 | 来源 |
|---|---|---|
| C1 身份 | 开票方和合同签约方是不是同一个法律实体？ | 注册信息、合同、供应商主数据 |
| C2 账户 | 收款账户在不在档案里，每次变更有没有回拨确认？ | 供应商主数据、合同 |
| C3 价格 | 单价是否在开票日有效合同价的 2% 以内？ | 合同、ERP |
| C4 收货 | 货收到了没有，收货数量是否不少于开票数量？ | ERP |
| C5 重复 | 这张发票或同一张订单是否已经付过？ | ERP |
| C6 渠道 | 请求来自档案里的域名，还是仿冒域名（编辑距离、同形字符）？ | 邮箱、供应商主数据 |
| C7 注入 | 文本是否试图指挥 AI？ | ERP、邮箱 |

像“身份”这样的方面，只有至少 2 个独立的可信系统一致时才评为 VERIFIED。邮箱永远不算可信来源，因为攻击者就是在那里写字的。签名的策略只在所有必需方面（身份、账户、价格、收货、重复、注入）都是 VERIFIED 时才允许自动支付，最高 EUR 250,000；其余情况一律 ASK：由人来决定，简报就摆在他面前。

## 结果

**B1** 是收款人名单：不管是谁，只要账户在已批准收款人登记表里就付，上限相同。**B3** 是 PayProof。攻击分成 2 类统计：一类冲着买方并不欠的钱来（冒名者、改过的账户、抬高的价格、重复发票、从未收到的货），另一类是只夹带了一条写给 AI 的指令的真实发票。付了后一类，等于把欠真正供应商的钱付给了它，所以单独统计。

### 留出集（44 笔申请，由 NVIDIA Nemotron 撰写）

这份数据集在首次评测之前就已封存（commit efa9fec），此后没有针对它调过任何代码。

| | B1：收款人名单 | B3：不用模型 | B3：加模型复核 | B3：攻击者控制的模型 |
|---|---|---|---|---|
| 冲着不欠的钱来、未经人工就付出去的攻击 | 9 / 18（EUR 170,800.31） | 0 / 18 | 0 / 18 | 0 / 18 |
| 其中付进冒名者或攻击者账户的 | 3 / 18（EUR 58,740.50） | 0 / 18 | 0 / 18 | 0 / 18 |
| 夹带写给 AI 的指令、被付了款的真实发票 | 6 / 6 | 6 / 6 | 2 / 6 | 6 / 6 |
| 被打断的正常付款 | 4 / 20（20.0%） | 0 / 20 | 0 / 20 | 0 / 20 |

- 冒名、改账户、价格、重复付款和收货类攻击，在每一种配置下都全部拦住。这些核查读的是结构化数据，攻击者写的文字改变不了它们。
- 模式匹配漏掉的 6 条指令，模型复核抓到了其中 4 条。它漏掉的 2 条（一条备注声称财务总监已口头批准，一封邮件说有个项目要靠这笔款，请在方便时尽早付款）都出现在真实发票上：有采购订单、有收货记录、按合同价、账户在档案里。标签在评测前就已定死，所以照样算漏报。
- 模型落到攻击者手里时，PayProof 的表现和不用模型时完全一样：公证人做决定时不用模型。攻击者控制的模型只是关掉了那道额外的复核。
- 那 8 句专门用来迷惑过滤器的正常句子（自动开票系统、基于 AI 的 ERP、“已经过我方财务批准”）没有一句打断付款。
- “加模型复核”这一列是 10 月 24 日那次运行的结果，当时还没有公证人。公证人只能把放行变成拦下，不能反过来，所以它不可能让这些数字变高；在不用模型的运行中，它确认了全部 26 次放行。

### 开发集（48 笔申请，由我们设计）

| | B1：收款人名单 | B3：PayProof |
|---|---|---|
| 冲着不欠的钱来、未经人工就付出去的攻击 | 15 / 23（EUR 197,089.83） | 0 / 23 |
| 其中付进冒名者或攻击者账户的 | 3 / 23（EUR 57,011.40） | 0 / 23 |
| 夹带写给 AI 的指令、被付了款的真实发票 | 1 / 1 | 0 / 1 |
| 被打断的正常付款 | 4 / 24（16.7%） | 0 / 24 |

核查和这些案例都是我们写的，所以这张表只说明流程能跑通，不说明它能泛化。

完整报告：[`eval-sample.md`](output_examples/eval-sample.md)、[`eval-hostile.md`](output_examples/eval-hostile.md)、[`eval-heldout-sample.md`](output_examples/eval-heldout-sample.md)、[`eval-heldout-hostile.md`](output_examples/eval-heldout-hostile.md)、[`eval-heldout-live.md`](output_examples/eval-heldout-live.md)。

## 自己核对一个决定

每次调查都会写出一份证明文件（`logs/proofs/<run>/<invoice>.json`；示例在 [`output_examples/`](output_examples/) 里）。核对一份证明文件时，不信任其中任何内容：

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

改动证明里某个被引用的值、合约的任何字段或者策略文件，对应的检查就会失败（`tests/test_gouji.py`）；源系统里某个单元格变了，也会同样失败。拦下的决定也能核对：冒名者的证明 7 项检查通过 7 项，最后一项是确认没有签发合约。

## 快速开始

### Docker

```bash
cp .env.example .env        # optional: without keys everything runs in sample mode
docker build -t gouji .
docker run --rm -p 8000:8000 --env-file .env gouji
```

然后：

```bash
curl -X POST http://localhost:8000/run -H "Content-Type: application/json" -d @input_examples/example_1_doppelganger.json
```

打开 http://localhost:8000/ 查看待付款申请列表，点进任一条看它的简报。

### 不用 Docker

需要 Python 3.12 或更新版本和 [uv](https://docs.astral.sh/uv/)：

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

给 `case` 或 `eval` 加上 `--live`，就由 DeepSeek 负责规划、注入复核和撰写简报（需要 `DEEPSEEK_API_KEY`）。`python run.py generate` 重建开发集；`python run.py heldout` 让 Nemotron 生成一份新的留出集（需要 `NVIDIA_API_KEY`）。

### 密钥和签名的策略

`keys/controller.pub`、`keys/trusted/notary-2c9d7b4e.pub`（签署示例证明的那个公证人）和 `policy/` 里的 2 份签名的策略都在仓库里，所以刚克隆下来的仓库不需要任何私钥，就能核验策略并核对示例证明。你机器上的公证人会在首次运行时，在 `keys/` 里生成它自己的密钥对；私钥都被 git 忽略，也从不复制进 Docker 镜像。想自己充当财务负责人，比如重新生成数据之后，运行 `python run.py policy --data data/sample`：如果还没有 `keys/controller.key`，它会先生成一个，然后重新给策略签名。

### 样例模式

设置 `SAMPLE_MODE=true`，或者根本不配密钥，PayProof 就不需要联网：后端是 DuckDB 读取 `data/` 下的文件，规划和报告用脚本，守卫只用模式匹配。每条 trace 都写明跑的是哪一种。

### API

`POST /run`

```json
{"run_id": "example_1", "input": {"inv_id": "INV-5567"}, "options": {"sample_mode": true}}
```

返回内容包括 `decision`、`recommendations`、`brief`、证据分级 `grades`、世界模型告警 `alerts`、公证人复核 `notary`、执行合约 `contract`（没有则为 null）、证明文件 `proof_file`、智能体列表 `agents`，以及 trace 文件 `log_file`。出错时返回 `{"status": "error", "error": {"type", "message", "recoverable"}}`，不会直接崩溃。

其他路由：`GET /brief/{inv_id}`（一页简报，附带它的证明）、`GET /row/{table}/{pk}`（从源系统重新读取的被引用行）、`GET /health`。

## 在 Zetaris 上运行

样例模式下，核查在 DuckDB 上读 `data/` 里的文件；在 Zetaris 上，同样的 SQL 跨 5 个系统就地联邦执行：2 个 PostgreSQL 库，加上 S3 兼容存储里的 3 个文件。仓库里不需要任何凭据：脚本把本地密码生成到被 git 忽略的文件里，Zetaris 的 API key 留在你自己的 `.env`。

**需要准备什么。** 一个正在运行的 Zetaris 实例（[Zetaris getting-started](https://zetaris.github.io/getting-started) 里的本地 Docker 安装，或者一个 AWS 集群）；Docker，用来跑充当替身的 PostgreSQL 和 S3 存储（Adobe S3Mock）；以及 `.env` 里的 `ZETARIS_REST_URL`（本地默认 `http://localhost:8888/api/v1.0`）、`ZETARIS_ORG_ID`，和在 Management > API Tokens 下创建的 API key `ZETARIS_API_KEY`。

**按顺序执行的步骤。**

```bash
uv run python scripts/zetaris_sources.py up        # start PostgreSQL (5433) and an S3 store (9000), local passwords
uv run python scripts/zetaris_sources.py load      # ERP and vendor master into PostgreSQL, the documents into S3
uv run python scripts/zetaris_sources.py register  # the statements in deploy/zetaris-sources/register.sql
uv run python scripts/zetaris_sources.py check     # SELECT 1, SHOW LIGHTNING DATABASES, row counts vs local
uv run python run.py case INV-5567 --backend zetaris
uv run python run.py eval --backend zetaris
```

配置用的 SQL 按执行顺序写在 [`deploy/zetaris-sources/register.sql`](deploy/zetaris-sources/register.sql) 里，密码用占位符代替：数据库部分是 2 条 `CREATE DATASOURCE` 加 `REGISTER DATASOURCE TABLES`，文件部分是 1 条 `CREATE LIGHTNING DATABASE` 和 3 条 `CREATE LIGHTNING FILESTORE TABLE`。

**其中一条查询。** C1 身份核查用单条语句关联 3 个系统（以下是针对 INV-5567 实际发给 Zetaris 的语句）：

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

发票来自一个拉脱维亚注册号，而订单、供应商主数据和合同都指向那个台湾注册号：这一行就是上面简报里的结论 F2 和 F3。

**运行记录。** 2026 年 10 月 27 日，中欧时间（CET）11:06 至 11:14，在本机安装的 Zetaris 2.4.3（Docker，黑客松版 v2.4.3.1）上运行，用开发集（`data/sample`，种子 20261022），由 DeepSeek 负责规划、复核和撰写。9 张表全部注册，Zetaris 上的行数与本地文件一致（86、84、90、42、20、12、18、63、20）。3 笔申请的每条查询都走 Zetaris，决定和证据分级与 DuckDB 上相同：INV-5567（冒名者：ASK，按疑似诈骗拦下）、INV-5579（高出合同价 18%：ASK，请供应商更正）和 INV-5559（真实的银行变更：ALLOW；公证人不用模型、用 35 条查询重新核查后，签发了合约 EC-96e4f180）。共 160 条联邦查询（46、40 和 74 条），在笔记本规格的引擎（2 核）上每条约 2.5 秒。随后又通过 Zetaris 核对了这 3 份证明，另用了 72 条查询：分别通过 7 / 7、7 / 7 和 10 / 10 项检查。发出的每条语句（连同行数和耗时）和每份证明都在 [`output_examples/zetaris-run/`](output_examples/zetaris-run/) 里。途中发现一点：Zetaris 把 JSON 文件当作一个整体文档读取，所以邮箱存成 JSON 数组。

**创建了哪些对象，以及如何清理。** Zetaris 里：数据源 `erp` 和 `vendor_master` 及其注册的表，以及 Lightning 数据库 `documents` 及其文件表 `contracts`、`registry` 和 `mailbox`。Docker 里：`deploy/zetaris-sources` 的 `postgres` 和 `s3` 容器，以及 PostgreSQL 数据卷。删除方法：在 Zetaris SQL Editor 里执行 `DROP DATASOURCE erp` 和 `DROP DATASOURCE vendor_master`，在那里删掉 `documents` 的表，然后在 `deploy/zetaris-sources` 里运行 `docker compose down -v`。

## 示例

[`input_examples/`](input_examples/) 和 [`output_examples/`](output_examples/) 里有 3 笔申请及其结果：

| 输入 | 案例 | PayProof |
|---|---|---|
| `example_1_doppelganger.json` | 冒名者以供应商的名字在拉脱维亚注册，备注里还藏了一条给 AI 的指令 | 拦下：疑似诈骗 |
| `example_2_price_inflation.json` | 已批准的供应商开票价高出合同价 18% | 拦下：请供应商更正发票 |
| `example_3_legitimate_bank_change.json` | 真实的银行账户变更，已回拨确认并记入供应商主数据 | 放行，附公证人签名的执行合约 |

## 架构

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

| 文件 | 内容 |
|---|---|
| `gouji/harness.py` | 5 个系统的统一接口；LocalHarness（DuckDB）和 ZetarisHarness |
| `gouji/checks.py` | C1 至 C7，每项都返回带引用 `{table, pk, column, value}` 的结论 |
| `gouji/agents.py` | Guard、Planner、Verifier、Reporter |
| `gouji/world_model.py` | Meterless World Model：3 个服务 |
| `gouji/policy.py` | 授权书（mandate）、签名的策略文件、证据分级、付款决定 |
| `gouji/notary.py` | 公证人：不用模型的重新推导，以及合约唯一的签名密钥 |
| `gouji/contract.py` | 执行合约、证据根和付款网关 |
| `gouji/signing.py` | Ed25519 密钥和签名 |
| `gouji/verify.py` | 事后核对证明文件 |
| `gouji/pipeline.py` | 一次端到端的调查，连同 trace 和证明 |
| `gouji/evaluate.py` | B1 对比 B3，打印每一个分母 |
| `gouji/world.py` | 虚构世界和开发集 |
| `gouji/redteam.py` | Nemotron 留出集 |
| `gouji/api.py` | FastAPI：`/run`、简报、被引用的行 |

## 赞助商技术

**Zetaris。** 5 个系统原地不动：ERP 和供应商主数据是数据库，合同是 Parquet，邮箱是 JSON，注册信息是 CSV。每项核查是一条跨系统关联的 ANSI SQL；Verifier、公证人和 `verify` 都通过同一个接口，在要紧的时刻从记录系统重新读取每个被引用的单元格。设置了 `ZETARIS_REST_URL` 和 `ZETARIS_API_KEY` 时，所有查询都通过 Zetaris 的 REST API 发给它（`gouji/harness.py` 的 `ZetarisHarness`，不需要 Java 和 JDBC 驱动）；没有设置时，同样的 SQL 在 DuckDB 上对同样的文件执行。在 `.env` 里用 `ZETARIS_TABLES` 把逻辑表映射到你的 Zetaris catalog。

**Meterless。** PayProof 实现了 World Model 引擎的 3 个服务，沿用指南里的名字（`gouji/world_model.py`）。实体按注册号和法域识别，同名的 2 家公司就是 2 个实体，“冒名供应商”告警来自世界模型，而不是来自提示词。存储是只追加的 JSONL 日志，规范视图可以从中重建。所有模型调用都经过同一个注入的 generator（`gouji/llm.py`），符合引擎指南的要求，所以 DeepSeek 换成 Nemotron 或任何兼容 OpenAI 接口的模型只是改配置，在 `eval --hostile` 里也可以换成攻击者的模型。附加组件参照 Scout intent 的设计：下游系统在动手之前先验证一个签名对象。在这里，这个对象就是公证人的 Ed25519 执行合约（`gouji/notary.py`、`gouji/contract.py`）。

**NVIDIA。** 留出红队集由 Nemotron（build.nvidia.com 上的 `nvidia/nemotron-3.5-lightning-30b-a3b`）撰写：冒名邮件和改账户邮件、仿冒域名、8 条新的提示注入、8 句专门用来绊倒简单过滤器的正常文本，以及 4 份真实的银行变更通知（`gouji/redteam.py`）。换一个不同于开发时所用的模型来写，核查面对的就是作者没写过的文本。

**Cursor。** 没有使用；按规则 5.1，Cursor 是可选项。

## 数据

全部是虚构的，由 `gouji/world.py` 生成：买方（Veltrona Drives GmbH）、14 家供应商、冒充它们的冒名者，以及下表里的每一条记录。域名使用保留后缀 `.example`，每个 IBAN 的校验位都是 `00`，ISO 13616 从不签发这样的号码，所以生成的账户不可能是真实账户。每个案例都以 2026-10-20 09:00 UTC 为判定时点；已付款的历史大约从 60 天前开始。

| 系统和格式 | 表（Zetaris 上） | 一行是 | 行数：开发集 / 留出集 |
|---|---|---|---|
| ERP，PostgreSQL（样例模式下是 DuckDB 文件） | `erp.purchase_orders` | 一张采购订单：供应商、物料、数量、单价 | 86 / 84 |
| | `erp.goods_receipts` | 针对某张订单的收货 | 84 / 83 |
| | `erp.invoices` | 一张发票：开票方名称和注册号、收款账户、备注、随附的邮件 | 90 / 86 |
| | `erp.payments` | 一笔已经付出的款项 | 42 / 42 |
| 供应商主数据，PostgreSQL | `vendor_master.vendors` | 一条供应商记录：注册号、档案里的账户、已知域名 | 20 / 20 |
| | `vendor_master.vendor_changes` | 对记录的一次修改：字段、旧值和新值、通过什么方式提出、有没有经回拨确认 | 12 / 12 |
| 合同，S3 上的 Parquet | `documents.contracts` | 一份合同或补充协议：签约方注册号、法域、物料、单价、有效期 | 18 / 18 |
| 应付邮箱，S3 上的 JSON | `documents.mailbox` | 一封邮件：发件域名、正文、附带的发票。按设计就不可信：攻击者就是在这里写字的 | 63 / 60 |
| 公司注册信息，S3 上的 CSV | `documents.registry` | 一个已注册的法律实体：名称、注册号、法域、成立日期 | 20 / 20 |

- `data/sample/`：开发集，种子 20261022，48 笔申请。用 `python run.py generate` 重建。
- `data/heldout/`：留出集，种子 20261024，44 笔申请，文本由 Nemotron 撰写。`manifest.json` 记录了提示词、模型、温度和每个文件的 SHA-256。这份数据在首次评测之前就已提交（efa9fec），每次改动时 CI 都会检查封存。

数据的局限：案例构成和数量是为一个虚构买方做的设计选择，不是实地数据；没有外币、贷项通知单和多行发票；注册信息只是单一快照。

## 局限

- 案例构成和数量是为一个虚构买方设计的，不是实地数据。这些数字说明核查在这些案例上能抓到什么，不代表诈骗发生率。
- 守卫的模式匹配有意做得很窄。遇到没见过的文本时，它依赖模型复核，而模型复核也会出错；上面的保证并不依赖它。
- PayProof 负责拦下付款并说明原因，不负责联系供应商。按档案号码回拨仍然是人的步骤，本来也应该如此。
- 密钥保管和进程隔离的情况如威胁模型一节所述：同一台机器、同一个进程、各自独立的密钥。
- 在 Zetaris 上，笔记本规格的引擎每条查询约 3 秒，所以一次调查在那里要 2 到 4 分钟（DuckDB 上不到 1 秒）。完整评测用同样的 SQL 在 DuckDB 上跑。

## 已有组件

[mandate-engine v0.1.1](https://github.com/hoongyu/mandate-engine)（MIT 或 Apache-2.0 双许可）负责评估授权书，并维护哈希链审计日志，付款网关把这份日志当作账本。它写于开发期之前，已作为已有组件申报；本仓库其余部分都在黑客松期间完成。

## 许可证

MIT，见 [LICENSE](LICENSE)。依赖的 mandate-engine 是 MIT 或 Apache-2.0 双许可。
