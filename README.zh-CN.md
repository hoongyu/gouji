[English](README.md) | 简体中文

# PayProof

**一个能讲清“为什么”的付款前调查员。** 每张发票付款之前，PayProof 在 ERP、供应商主数据、合同、应付邮箱和公司注册信息这五个系统里就地查询，核实供应商是不是它自称的那家公司。它给出的每一句解释，都引用一个由程序重新读过的数据库单元格。付不付钱由签过名的授权书（mandate）决定，不由模型决定；没有签名执行合约的付款，付款系统一律拒绝。

Open Agent Hackathon 2026 · 赛道 2：The Agent That Can Explain Why。代码和仓库沿用工作名 *gouji*（勾稽：账目之间交叉核对）。

## 问题

2013 至 2015 年，有人在拉脱维亚注册了一家和亚洲某电脑硬件厂同名的公司，在拉脱维亚和塞浦路斯开了银行账户，然后冒充这家硬件厂给两家美国互联网公司发邮件。媒体报道这两家是 Google 和 Facebook。它们一共把超过 1.2 亿美元汇给了他（[美国司法部，2019](https://www.justice.gov/usao-sdny/pr/lithuanian-man-sentenced-5-years-prison-theft-over-120-million-fraudulent-business)；[WSKG/NPR，2019](https://www.wskg.org/news/2019-03-25/man-pleads-guilty-in-new-york-to-fleecing-facebook-and-google-of-100-million)）。这次攻击在技术上一点都不高明：公司名对得上，邮件看着就像供应商发的。

商业邮件诈骗（BEC）至今仍是 FBI 统计里损失最大的诈骗类型：2025 年报案 24,768 宗，报告损失 30.5 亿美元，其中涉及 AI 的 BEC 损失超过 3,000 万美元（[IC3 2025 年报](https://www.ic3.gov/AnnualReport/Reports/2025_IC3Report.pdf)，第 25、26、39 页）。

现在应付团队正把发票处理交给 AI 智能体。照着已批准收款人名单付款的智能体，会像当年的人一样被骗；它还多了一个新的攻击面：发票里写给智能体看的指令。

![冒名者发票的一页简报：结论是拦下，由授权书决定；带引用的解释；被隔离的写给 AI 的指令](docs/brief-hold.jpg)

## PayProof 做什么

对每一笔付款申请，七个智能体按固定且有上限的流程协作。每一步都写进 `logs/trace-<run_id>.jsonl`，同时打印到标准输出。

| 智能体 | 职责 |
|---|---|
| **Guard（守卫）** | 在任何环节读取之前，先扫描发票备注和随附邮件里有没有写给 AI 的指令。模式匹配每次都跑；接上模型时再加一道复核，抓换了说法的指令，但模型的判断只有在它引用的原文片段确实出现在文档里时才算数。 |
| **Planner（规划）** | 选择要跑的核查和追查（最多 2 轮），从不决定付款。 |
| **Investigator（调查）** | 每项核查是一条联邦 SQL 查询，在数据所在处执行：Zetaris，样例模式下是 DuckDB。 |
| **Verifier（核验）** | 按主键从源系统重新读取每一个被引用的单元格，对不上的结论直接丢弃。 |
| **WorldModel（世界模型）** | Meterless World Model。按注册号和法域识别法律实体，从不按名称，并发出“两家公司同名”之类的告警。 |
| **Decider（决策）** | mandate-engine 依据分级后的证据评估签名授权书：ALLOW、ASK 或 DENY。 |
| **Reporter（报告）** | 撰写简报。没有经核验引用的句子会被删掉。 |

七项核查：

| 核查 | 问题 | 来源 |
|---|---|---|
| C1 身份 | 开票方和合同签约方是不是同一个法律实体？ | 注册信息、合同、供应商主数据 |
| C2 账户 | 收款账户在不在档案里，每次变更有没有回拨确认？ | 供应商主数据、合同 |
| C3 价格 | 单价是否在开票日有效合同价的 2% 以内？ | 合同、ERP |
| C4 收货 | 货收到了没有，收货数量是否不少于开票数量？ | ERP |
| C5 重复 | 这张发票或同一张订单是否已经付过？ | ERP |
| C6 渠道 | 请求来自档案里的域名，还是仿冒域名（编辑距离、同形字符）？ | 邮箱、供应商主数据 |
| C7 注入 | 文本是否试图指挥 AI？ | ERP、邮箱 |

### 为什么这份解释可信

1. **证据由程序分级。** 像“身份”这样的方面，只有至少两个独立的可信系统一致时才评为 VERIFIED。邮箱永远不算可信来源，因为攻击者就是在那里写字的。
2. **模型从不做决定。** 授权书是一份签名的策略。只有当所有必需方面（身份、账户、价格、收货、重复、注入）都是 VERIFIED 时，它才允许自动支付，单笔上限 25 万欧元，收款人在不在签名名单里都一样。其余情况一律 ASK：由人来决定，简报就摆在他面前。
3. **没有合约就不付款。** 决定为 ALLOW 时，PayProof 签发一份执行合约：HMAC 签名，绑定这笔付款的精确内容哈希，15 分钟内有效，只能用一次。付款执行器拒绝所有不带合约的调用。每个被拦下的案例还会跑一次绕过测试：不带合约直接调用付款，trace 里能看到它被拒绝。

## 结果

同一批案例跑两种配置。**B1** 只有授权书：名单里的收款人就付。**B3** 是 PayProof：同一份授权书，但每个方面都必须是 VERIFIED。

### 开发集（48 笔申请，由我们设计）

| | B1：只有授权书 | B3：PayProof |
|---|---|---|
| 未经人工就付出去的攻击 | 16 / 24 | 0 / 24 |
| 未经人工就付出去的攻击金额 | EUR 210,987.33（61.8%） | EUR 0.00（0.0%） |
| 被打断的正常付款 | 4 / 24（16.7%） | 0 / 24（0.0%） |

核查和案例都是我们写的，所以这张表只说明流程能跑通，不说明它能泛化。

### 留出集（44 笔申请，文本由 NVIDIA Nemotron 撰写）

封存的留出集（commit 8bddf05）上，每种配置只跑了一次，中间没有改过代码。

| | B1：只有授权书 | B3：PayProof，只用模式匹配 | B3：PayProof，加模型复核 |
|---|---|---|---|
| 未经人工就付出去的攻击 | 15 / 24 | 6 / 24 | 2 / 24 |
| 未经人工就付出去的攻击金额 | EUR 236,300.21（57.2%） | EUR 65,499.90（15.9%） | EUR 13,714.60（3.3%） |
| 被打断的正常付款 | 4 / 20（20.0%） | 0 / 20（0.0%） | 0 / 20（0.0%） |

说明了什么：

- 冒名、改账户、价格、重复付款和收货类攻击，两种配置下全部拦住。这些核查读的是结构化数据，攻击者写的文字改变不了它们。
- 模式匹配一条都没抓到 6 条新的单独注入；加上模型复核后抓到其中 4 条。
- 漏掉的两条（评测结束后才看的）：一条是发票备注里说“财务总监已口头批准”，另一条是邮件里说项目进度取决于这笔款，请尽快付款。后一条读起来就是正常的业务催款，但标签在评测前已经定死，照样算漏报。两条发票在其他方面都是真的（有订单、有收货、合同价、档案里的账户），钱会付给真正的供应商。
- 8 句专门用来迷惑过滤器的正常文本（自动开票系统、基于 AI 的 ERP、“已经过我方财务批准”）在两种配置下都没有打断任何付款。
- 看过这些失败之后再做的修改，会用一份新的留出集来衡量，不用这一份。

完整报告：[`output_examples/eval-sample.md`](output_examples/eval-sample.md)、[`output_examples/eval-heldout-sample.md`](output_examples/eval-heldout-sample.md)、[`output_examples/eval-heldout-live.md`](output_examples/eval-heldout-live.md)。

## 快速开始

### Docker

```bash
cp .env.example .env        # 可选：没有密钥时全部以样例模式运行
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
uv run python run.py case INV-5567              # 单笔申请：决定、简报、trace
uv run python run.py eval                       # 开发集上 B1 对比 B3
uv run python run.py eval --data data/heldout   # 留出集
uv run python run.py serve                      # HTTP API，端口 $PORT（默认 8000）
uv run pytest                                   # 测试
```

给 `case` 或 `eval` 加上 `--live`，就由 DeepSeek 负责规划、注入复核和撰写简报（需要 `DEEPSEEK_API_KEY`）。`python run.py generate` 重建开发集；`python run.py heldout` 让 Nemotron 生成一份新的留出集（需要 `NVIDIA_API_KEY`）。

### 样例模式

设置 `SAMPLE_MODE=true`，或者根本不配密钥，PayProof 就不需要联网：后端是 DuckDB 读取 `data/` 下的文件，规划和报告用脚本，守卫只用模式匹配。每条 trace 都写明跑的是哪一种。

### API

`POST /run`

```json
{"run_id": "example_1", "input": {"inv_id": "INV-5567"}, "options": {"sample_mode": true}}
```

返回内容包括 `decision`、`recommendations`、`brief`、证据分级 `grades`、世界模型告警 `alerts`、执行合约 `contract`（没有则为 null）、智能体列表 `agents`，以及 trace 文件 `log_file`。出错时返回 `{"status": "error", "error": {"type", "message", "recoverable"}}`，不会直接崩溃。

其他路由：`GET /brief/{inv_id}`（一页简报）、`GET /row/{table}/{pk}`（从源系统重新读取的被引用行）、`GET /health`。

## 示例

[`input_examples/`](input_examples/) 和 [`output_examples/`](output_examples/) 里有三笔申请及其结果：

| 输入 | 案例 | PayProof |
|---|---|---|
| `example_1_doppelganger.json` | 冒名者以供应商的名字在拉脱维亚注册，备注里还藏了一条给 AI 的指令 | 拦下：疑似诈骗 |
| `example_2_price_inflation.json` | 已批准的供应商开票价高出合同价 18% | 拦下：请供应商更正发票 |
| `example_3_legitimate_bank_change.json` | 真实的银行账户变更，已回拨确认并记入供应商主数据 | 放行，附执行合约 |

## 架构

```text
付款申请
   │
   ▼
Guard ──► Planner ──► Investigator ──► Verifier ──► WorldModel ──┐
              ▲         (SQL on Zetaris / DuckDB)                │
              └──────────── 追查（最多 2 轮） ◄───────────────────┘
                                   │
                                   ▼
                    Decider（mandate-engine，分级证据）
                         │                     │
                       ALLOW                  ASK
                         │                     │
                  签名执行合约            没有合约：执行器拒绝
                         │                     │
                         ▼                     ▼
                  PaymentExecutor          交给人的简报
```

| 文件 | 内容 |
|---|---|
| `gouji/harness.py` | 五个系统的统一接口；LocalHarness（DuckDB）和 ZetarisHarness |
| `gouji/checks.py` | C1 至 C7，每条结论都带引用 `{table, pk, column, value}` |
| `gouji/agents.py` | Guard、Planner、Verifier、Reporter |
| `gouji/world_model.py` | Meterless World Model 的三个服务 |
| `gouji/policy.py` | 授权书、证据分级、付款决定 |
| `gouji/contract.py` | 执行合约和 PaymentExecutor |
| `gouji/pipeline.py` | 一次完整调查及其 trace |
| `gouji/evaluate.py` | B1 对比 B3，打印每一个分母 |
| `gouji/world.py` | 虚构世界和开发集 |
| `gouji/redteam.py` | Nemotron 留出集 |
| `gouji/api.py` | FastAPI：`/run`、简报、被引用的行 |

## 赞助商技术

**Zetaris。** 五个系统原地不动：ERP 和供应商主数据是数据库，合同是 Parquet，邮箱是 JSONL，注册信息是 CSV。每项核查是一条跨系统关联的 ANSI SQL，Verifier 也通过同一个接口重新读取每个被引用的单元格。设置了 `ZETARIS_REST_URL` 和 `ZETARIS_API_KEY` 时，所有查询都通过 Zetaris 的 REST API 发给它（`gouji/harness.py` 的 `ZetarisHarness`，不需要 Java 和 JDBC 驱动）；没有设置时，同样的 SQL 在 DuckDB 上对同样的文件执行。在 `.env` 里用 `ZETARIS_TABLES` 把逻辑表映射到你的 Zetaris catalog。

**Meterless。** PayProof 实现了 World Model 引擎的三个服务，沿用指南里的名字（`gouji/world_model.py`）。实体按注册号和法域识别，同名的两家公司就是两个实体，“冒名供应商”告警来自世界模型，而不是来自提示词。存储是只追加的 JSONL 日志，规范视图可以从中重建。所有模型调用都经过一个注入的 generator（`gouji/llm.py`），符合引擎指南的要求，所以 DeepSeek 换成 Nemotron 或任何兼容 OpenAI 接口的模型只是改配置。附加组件 `gouji/contract.py` 参照 Scout intent 的设计：下游系统在动手之前先验证一个签名对象。

**NVIDIA。** 留出红队集由 Nemotron（build.nvidia.com 上的 `nvidia/nemotron-3.5-lightning-30b-a3b`）撰写：冒名邮件和改账户邮件、仿冒域名、8 条新的提示注入、8 句专门用来绊倒简单过滤器的正常文本，以及 4 份真实的银行变更通知（`gouji/redteam.py`）。换一个不同于开发时所用的模型来写，核查面对的就是作者没写过的文本。

**Cursor。** 目前没有使用；按规则 5.1，Cursor 是可选项。

## 数据

全部是虚构并自动生成的：买方（Veltrona Drives GmbH）、14 家供应商，以及它们的订单、收货、发票、付款、合同、邮件和注册信息。域名使用保留后缀 `.example`，每个 IBAN 的校验位都是 `00`，ISO 13616 从不签发这样的号码，所以生成的账户不可能是真实账户。

- `data/sample/`：开发集，种子 20261022。用 `python run.py generate` 重建。
- `data/heldout/`：留出集，种子 20261024，文本由 Nemotron 撰写。`manifest.json` 记录了提示词、模型、温度和每个文件的 SHA-256。这份数据在第一次评测之前就已提交（8bddf05）。

## 局限

- 案例构成和数量是为一个虚构买方设计的，不是实地数据。这些数字说明核查在这些案例上能抓到什么，不代表诈骗发生率。
- 守卫的模式匹配有意做得很窄。遇到没见过的文本时，它依赖模型复核，而模型复核也会出错。
- PayProof 负责拦下付款并说明原因，不负责联系供应商。按档案号码回拨仍然是人的步骤，本来也应该如此。
- Zetaris 适配器按官方文档的 REST API 编写，还没有对真实 Zetaris 实例跑过。

## 已有组件

[mandate-engine v0.1.1](https://github.com/hoongyu/mandate-engine)（MIT 或 Apache-2.0 双许可）负责评估授权书和记录审计日志。它写于开发期之前，已作为已有组件申报；本仓库其余部分都在黑客松期间完成。

## 许可证

MIT，见 [LICENSE](LICENSE)。依赖的 mandate-engine 是 MIT 或 Apache-2.0 双许可。
