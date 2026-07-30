# PRD Quality Review — Logos: AI 名词知识图谱与演化平台

## Overall verdict
PRD 质量处于 **ready-to-build** 水平。愿景清晰、功能范围有纪律、非目标明确防止了范围蔓延。技术选型和 NFR 基于已完成的领域和技术研究，决策有据可依。最大风险在于核心假设（用户是否接受图谱探索方式）的验证——这是产品本身的命门，不是 PRD 的问题。

## Decision-readiness — strong

产品级别的决策（MVP vs Phase 2范围、技术栈选择、非目标）都已明确做出并以结构化方式记录。FR-12 的三层检索策略是关键的架构决策，技术选型约束（Neo4j-only MVP）有明确理由。

**Findings:**
- **[medium]** 「免费探索+高级付费」的设计原则保留但商业模式未定——当前标注为 `[ASSUMPTION]` 是合理的，但下游架构和 Epic 拆解可能会依赖此信息做决策（如计费系统的预留设计）。*Fix:* 保持当前 `[ASSUMPTION]` 状态，待 BMad 确认方向后在后续迭代补充。

## Substance over theater — strong

没有填充式内容。4 个 UJ 各有明确的写入目的和差异化场景（普通理解、记者调查、投资研究、创作积累）。Vision 不会与其他产品互换。NFR 有产品特定阈值（<2s 图谱加载、<$0.01/AI问答）。

**Findings:** 无。

## Strategic coherence — strong

核心论点清晰：**「用户是否愿意用图谱化的方式探索知识」**是所有决策的锚点。功能特性全部服务于这个验证循环。MVP 范围体现出清晰的问题求解逻辑：

- 搜索入 → 图谱展示 → 时间轴演化 → AI 问答闭环
- 人物优先作为差异化锚点
- 置信度溯源作为信任机制

**Findings:** 无。

## Done-ness clarity — adequate

FR 的 Consequences 基本可验证，但部分条目偏定性。

**Findings:**
- **[high]** FR-3「图谱构建时间不超过 15 秒」——这个时间从哪来？是包含 LLM 调用时间的全部构建时间还是仅数据提取？网络延迟、数据源响应速度不可控。*Fix:* 拆分为「初始骨架数据展示时间 < 3s」和「完整图构建（含 LLM 增强）在后台完成，不超过 30s」。
- **[medium]** 多处「不超过」「至少」的阈值标注缺乏依据——例如「5-10 个关键里程碑」「200 节点以内」。这些在实际开发中可能需要调整。*Fix:* 标注为 `[ASSUMPTION: 基于___经验基准]` 或开放给工程师实测后决定。

## Scope honesty — strong

10 条非目标 + 详细的 MVP In/Out of Scope 表格。`[NON-GOAL for MVP]` 在特性层和全局层都有标注。6 条开放问题诚实承认了不确定领域。

**Findings:** 无。

## Downstream usability — strong

词汇表定义清晰且一致。FR 编号连续（FR-1 到 FR-16）。UJ 有命名的人物角色和具体场景。架构工作流和 Epic 拆解可以干净地从此提取输入。

**Findings:** 无。

## Shape fit — strong

消费级产品 + 4 条命名人物 UJ = 匹配。链顶 PRD（后续走架构/Epic/Story），下游可用性做得好。

**Findings:** 无。

## Mechanical notes

- Glossary 术语「GraphRAG」在正文中被引用但在 Glossary 中定义为架构模式而非产品层术语——建议在架构文档（architecture.md）中展开，PRD 中保留即可。
- FR-12 的三层检索策略是关键的架构决策，建议在架构文档中展开。
- SM-0 的 20% 回访率基准明确标注了 `[ASSUMPTION]`——建议在 Phase 1 上线前进行基准调研验证。
