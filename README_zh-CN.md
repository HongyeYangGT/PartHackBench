# PartHackBench

**PartHackBench** 是一个受控基准，用于对有状态工具智能体任务中的部分得分评估器进行压力测试。它试图回答一个简单的问题：**在最终经过认证的任务进度完全相同的情况下，智能体是否能够仅通过改变执行路径来改变自己获得的分数？**

## 为什么需要 PartHackBench？

![PartHackBench](assets/1.png)

设想你让一个 AI 助手为你安排一次周末旅行。

你交给它四项简单任务：预订酒店、购买火车票、预订餐厅，以及安排从车站出发的接送。

第一个助手完成了酒店和火车票的预订，然后停止。四项任务完成了两项。如果你此时查看旅行安排，它已经完成了 **一半**。

第二个助手采取了一条更奇怪的路径。它先完成全部四项任务。某一时刻，你的旅行已经安排得十分完整：酒店已订、车票已买、餐厅已预约、接送已安排。随后，它又取消了餐厅预约和接送。

现在再次检查两份旅行安排。

它们完全相同。两者都保留了酒店和火车票，也都没有餐厅预约和接送。

那么，这两个助手应该获得多少分？

直觉上，它们应该获得相同的分数。

但设想一个评分系统会记住每个助手在整个执行过程中曾经达到过的最佳状态。第一个助手从未超过 50%，因此它获得 **0.5**。第二个助手曾短暂达到 100%，所以评估器仍然给它 **1.0**，即使其中一半成果后来已经消失。

这个简单的不一致，就是 **PartHackBench** 所关注的问题。

单纯获得更高的分数本身说明不了太多。也许第二个助手确实完成了更多工作。为了公平地测试评估器，PartHackBench 首先排除这种可能性：它构造轨迹对，并确保这些轨迹的**最终任务进度经过认证后完全一致**。

在旅行示例中，基准会逐项检查每个要求：酒店、车票、餐厅和接送。它还会检查保留下来的成果是否归属于同一个执行主体。只有当两条轨迹到达相同的终止世界状态，并且在各个组成部分上逐一匹配时，它们才能构成一个**等进度轨迹对（equal-progress pair）**。

在满足这一条件之后，基准进一步询问：

> **如果两个智能体最终具有相同的认证进度，评估器是否仍然会给出不同的分数？**

分数差定义为

```math
\Delta_{\text{hack}} = f(A)-f(H),
```

其中 `H` 表示诚实轨迹（honest trajectory），`A` 表示对抗轨迹（adversarial trajectory）。当 `\Delta_{\text{hack}}` 为正时，意味着在基准定义的最终任务进度保持不变的情况下，评估器仍然给予了额外分数。

![PartHackBench](assets/2.png)

这个旅行示例也可以帮助理解整个基准中的几个核心对象。**目标谓词（goal predicate）**表示一个需要持续满足的要求，例如“酒店已经预订”。**轨迹（trajectory）**表示智能体执行过的完整动作序列。**当前状态（current state）**描述任务结束时实际上仍然成立的事实。**历史型评估器（historical evaluator）**可能会保留轨迹早期曾经取得的成果对应的分数，而**当前状态评估器（current-state evaluator）**只根据评估时仍然成立的状态进行评分。**回滚（rollback）**则指已经完成的工作后来又被撤销，例如取消餐厅预约。

这引出了第二类压力测试。假设一个助手当前满足两个要求，随后取消其中一个。那么它的认证进度已经下降，因此部分得分评估器的分数也应该随之下降。PartHackBench 将这种测试称为**严格回滚测试（strict rollback test）**。等进度测试用于检查当认证进度保持不变时分数是否具有不变性；回滚测试则用于检查当认证进度下降时分数是否也随之下降。

PartHackBench 在 **PB-CSTE v1.0** 中实现了这两类测试。PB-CSTE 是一个确定性、可重放的工具使用环境。任务通过白名单中的状态修改操作作用于显式的持久目标。每一次成功操作都会产生状态变化、来源记录（provenance record）以及可重放快照。只有在完成认证之后才会比较评估器分数，因此基准测得的分数差异，是在最终任务进度已经被控制之后所产生的差异。

## PartHackBench 如何工作

PB-CSTE 包含 **6 个开发任务和 18 个留出任务（held-out tasks）**，覆盖四类任务族：Persistent multi-step、Entity CRUD、Fixed-goal interaction 和 GoalPatch。其中 14 个固定目标案例还支持严格回滚评估。

在等进度测试中，诚实轨迹 `H` 和候选对抗轨迹 `A` 会从同一个冻结初始状态开始重放。认证器逐项评估终止状态中的目标谓词，并验证保留下来的成果对应的归属信息。对于 GoalPatch 案例，还要求当前激活的目标版本保持一致。当激活目标版本、谓词向量以及归属向量逐项一致时，这一轨迹对才具备资格。基准进度定义之外的任务外字段不会影响轨迹对的资格判定。随后，评估器会分别对两条轨迹打分，`\Delta_{\text{hack}}` 用于衡量在认证进度一致之后仍然存在的额外分数差异。

在回滚评估中，基准从一条已经认证的轨迹出发，应用一个合法的反向操作，使当前任务进度下降，同时保持相关固定目标定义不变。能够正确识别回滚的评估器应满足 `f(R) < f(H)`。如果历史型评估器仍然把已经被撤销的早期成果计入分数，就可能无法通过这一测试。

因此，该基准明确区分了智能体评估中经常被混为一谈的三个层次：**发生过哪些动作**、**最终仍然保留哪些任务状态**，以及**评估器最终给出什么分数**。PB-CSTE 提供可执行的状态与来源记录层；认证过程决定哪些轨迹比较是有效的；随后，各评估器自己的评分规则才用于揭示：在认证进度已经受到控制之后，评分是否仍然受到路径历史影响。

冻结参考实验为 Historical 目标产生了 **15 个匹配的留出等进度轨迹对**。这一匹配集合存储在经验账本（empirical ledger）中，作为实际观察到的实验结果，而不是被编码进留出任务定义之中。

## 发布原则

冻结的经验记录以不可变发布产物的形式分发。仓库不会根据任务模板重新构造缺失的冻结攻击轨迹或回滚轨迹，然后再把这些重构结果当作经验观测值。开发夹具仍然可用于协议、序列化器、评估器和难度检查；开发阶段的机制见证数据不会被纳入经验统计聚合。

这种设计可以将确定性的基准机制与外部模型运行结果分离开来，因为后者在独立重复运行时可能发生变化。

## 已包含内容

- PB-CSTE 任务 / 环境代码以及确定性的协议机制；
- 横跨四类任务族的 6 个开发任务 + 18 个留出任务规范；
- 公共序列化器和无 schema 的 IDJ 投影视图；
- 认证器以及确定性评估器实现；
- 攻击者、DeepSeek judge、IDJ checklist 构建和 IDJ 评分所使用的提示词模板；
- 冻结的共享参考任务级经验账本；
- 冻结的共享参考、目标特定、回滚和完整性聚合结果；
- 目标特定的 ranked deltas；
- 公共诚实轨迹评估器 payload / projection 记录、重放审计记录，以及任务结构审计；
- 用于发布完整性、任务结构、公共 / 私有记录隔离和经验账本算术校验的 CI 测试。

## 冻结的核心结果

冻结的 Historical/Predicate-Max 共享集合包含 15 个匹配任务。Historical 的平均 Δhack 四舍五入为 **.252**，条件 ASR 为 **10/15**，端到端 yield 为 **10/18**。共享参考下 DeepSeek 的平均分数膨胀为 **.022**，ASR 为 **1/15**；IDJ 为 **.017**，ASR 为 **1/15**。当前状态控制评估器在共享集合上的分数膨胀为 0。回滚检测结果分别为：历史型评估器 0/14，DeepSeek 10/14，IDJ 12/14，CSPS / Lightweight CAPE 14/14。

只要对应的底层输入已经公开，这些数值均由发布的经验记录聚合得到。它们并没有被硬编码进评估器实现或完整性测试中。

## 快速开始

```bash
python scripts/verify_package.py
python scripts/verify_release_integrity.py
python -m unittest discover -s tests -v
python -m parthackbench.cli aggregate-results --json
python -m parthackbench.cli manifest --split heldout
python -m parthackbench.cli replay-honest --task PH-H01 --json
```

如需运行仅用于验证机制的开发见证案例：

```bash
python -m parthackbench.cli protocol-fixture --task PH-D04 --kind adversary --json
```

开发协议夹具用于离线测试重放与认证机制。无法通过公共 fixture API 为留出任务构造这些夹具；它们也从不被用作默认攻击生成器，并且不计入任何经验测量。

## 数据布局

| 路径 | 用途 |
|---|---|
| `artifacts/empirical_shared_ledger.json` | Historical、CAPE-Max、DeepSeek 和 IDJ 的冻结任务级共享参考 delta |
| `artifacts/empirical_results.json` | 冻结的经验聚合结果 |
| `artifacts/candidate_accounting_k3.json` | 冻结的 K=3 候选聚合计数 |
| `records/evaluator_records/` | 已发布的共享及目标特定评估器记录 |
| `records/tasks/` | 公共任务规范 |
| `records/public_payloads/honest/` | 已序列化的诚实轨迹公共评估器输入 |
| `records/idj_projections/honest/` | 无 schema 的诚实轨迹投影 |
| `prompts/` | 随发布版本冻结的提示词模板 |
| `paper/PartHackBench_preprint_reference.pdf` | 仓库中附带的参考论文 |

## 公共 / 私有边界

公开发布版本会从导出记录中排除私有认证向量、资格判定结果、canary 和私有标识符。期望值、隐藏测试、可信状态、私有标识符、认证向量以及资格判定结果均不会进入公共评估器输入。

源码包在 `parthackbench/fixtures.py` 中包含仅用于开发的见证构造逻辑，以便可以离线测试机制。公共 API 会拒绝为留出任务构造见证。开发见证仅用于机制验证，不会被计入冻结经验观测。

## 冻结模型配置

Historical 目标的攻击者使用 `deepseek-v4-pro`，启用 thinking mode，temperature 设为 0，使用 strict JSON，token 上限为 12,000，超时时间 600 秒，并允许一次受限重试。DeepSeek judge 使用结构化部分评分，temperature 设为 0，使用 strict JSON，token 上限 4,096，超时时间 600 秒，并允许一次受限重试。IDJ checklist 的构建使用 Gemini 2.5 Pro；IDJ 评分使用无 schema 的 projection，每条轨迹调用三次，并以中位数作为主要结果。

供应商侧的模型 revision identifier，以及每个任务被冻结的 IDJ checklist hash，并未包含在当前发布源码中，因此仓库将这些字段保留为未指定状态。

## 公共发布版本能够复现什么

`aggregate-results` 会在对应底层输入公开的情况下，根据已发布的低层记录重新计算共享参考和目标特定的汇总字段。`verify_release_integrity.py` 会独立检查相同的算术关系和跨记录不变量。对于底层输入未包含在公共 bundle 中的聚合字段，则会作为经验记录保留下来。

因此，公共包支持对已发布基准机制进行确定性重放，也支持重新聚合已公开的经验记录。没有包含在公共 bundle 中的原始模型轨迹不属于其重放范围。

## 独立重复运行

新的模型执行应使用新的 run identifier，并与冻结参考运行结果分开报告。语义模型评分在独立执行之间可能发生变化。重复运行产生的输出不应覆盖 `artifacts/empirical_shared_ledger.json` 或 `artifacts/empirical_results.json`。

更多细节请参阅 `docs/RELEASE_INTEGRITY.md`、`docs/data_provenance.md` 和 `docs/reproducibility.md`。
