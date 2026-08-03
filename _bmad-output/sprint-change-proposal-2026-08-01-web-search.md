# Sprint Change Proposal — 外部事实来源扩充：Tavily 全网搜索 + 权威源兜底

- **日期**：2026-08-01
- **触发人**：BMad
- **状态**：**已批准（2026-08-01）** — 四条增量提案（W1-W4）逐条批准，其中 W2 经修订扩展为"领域感知多源兜底池"；代码按 W1 → W2 → W3 交接 Developer agent 实施，文档修订已应用
- **变更等级**：Moderate（Epic 1/2 多 Story 措辞调整 + 后端模块重写 + 设置页新增字段，需 PO/DEV 协同）
- **前置依赖**：无（独立于已完成的 P1-P10 图谱质量批次；其产出复用，不冲突）

---

## 1. Issue Summary

### 触发原因

BMad 反馈：**外部事实来源只有 Wikidata/维基百科不够，希望实现真正的"全网搜索"**。

> 我觉得外部事实来源 wiki 不够，能够实现全网搜索吗

即：希望将外部事实来源从"Wikidata/维基百科为主"扩展为"真实全网搜索"，并在结果不足时以权威站点内容兜底扩充。

### 根因分析（代码级证据）

| # | 根因 | 代码证据 |
|:---|:---|:---|
| 1 | 现有 `WebSearch.search_and_extract()` 是**占位实现**：不真实联网，仅让 LLM 凭训练记忆生成一段摘要，`entities`/`relations` 恒为空 | [web_search.py:33](backend/app/ai/web_search.py#L33) `# TODO: 当 LLM 提供商支持 web_search 工具时实现真实搜索` |
| 2 | 该占位已被接入两条刚完成的数据管道，导致图富/时间轴的"AI Web Search"输入实为 LLM 记忆而非真实信息 | [graph_service.py:308-315](backend/app/services/graph_service.py#L308)（图富）、[timeline_service.py:253-257](backend/app/services/timeline_service.py#L253)（时间轴兜底）——下游均只消费 `search_result["summary"]` |
| 3 | 无任何搜索 API 依赖与配置面（tavily/serp/duckduckgo 均未安装，`TAVILY_API_KEY` 不存在） | `requirements.txt`、`app/config.py`、`app/services/config_service.py` |

### 变更性质

不推翻既有架构决策，而是**兑现 PRD（FR-3/FR-8）与架构规划中"AI Web Search"第二数据源**的缺口：把"AI Web Search"从 LLM 记忆占位升级为"真实全网搜索 + 权威源兜底"。属**技术缺口补全 + 产品数据质量增强**，非需求误解、非战略转向。

---

## 2. Impact Analysis

### 2.1 Epic 影响

| Epic | 影响 | 说明 |
|:---|:---|:---|
| **Epic 1 搜索与知识图谱构建引擎** | 主要 | Story 1.5 Web 丰富通道：数据源从"LLM 记忆"升级为"Tavily 全网 + 权威源兜底"，AC 已补充 |
| **Epic 2 图谱可视化与探索体验** | 轻度 | Story 2.5 时间轴兜底数据源升级（措辞受益，AC 已含 Web 兜底），无结构改动 |
| **Epic 3 人物优先与数据质量系统** | 无 | 数据来源更丰富间接提升，无 AC 变更 |
| **Epic 4 匿名搜索历史** | 无 | 快照自动复用新数据，保存逻辑不变 |

### 2.2 Story 影响

- **修改 Story 1.5**（已应用 AC）：AI Web Search 走真实全网（Tavily + 权威源兜底 + LLM 记忆终极退化）。
- **Story 2.5**：时间轴 AI 兜底输入升级（无需改 AC，数据源自动受益）。
- 其余 Story 不变；无新增/删除 Story。

### 2.3 文档冲突与更新

| 文档 | 更新内容 | 状态 |
|:---|:---|:---|
| PRD | FR-3 特征级 NFR（数据源策略 + 外部事实来源说明）；开放问题 #5（SLA 依赖缓解） | ✅ 已应用（2026-08-01） |
| Epics | Story 1.5 新增 AI Web Search 真实全网 AC | ✅ 已应用（2026-08-01） |
| Architecture | ADR-006 外部事实来源扩充决策记录 | ✅ 已应用（2026-08-01） |
| Frontend Design | 无（设置页新增一个表单字段，属组件内扩展，不涉及设计规范） | N/A |

### 2.4 技术影响

- **配置面**：设置页（含后端 `ConfigService`/`GET|PUT /config/llm`）新增 `tavily_api_key` 运行时配置，与 LLM Key 同模式（存 Redis，`has_tavily_api_key` 布尔透出，不回传密钥）。
- **数据管道**：`WebSearch.search_and_extract` 重写为三层数据源：Tavily 全网搜索（主源）→ 领域感知权威源兜底池（按实体类型路由）→ LLM 记忆终极退化；返回增加非破坏性 `sources` 字段。
- **权威兜底池**：统一连接器接口（每源一个适配器：`name` + `query` + `parse`），按 P7 实体类型路由选源，逐源容错。
- **安全**：Tavily/Wikipedia/OpenAlex/GitHub/Wiktionary/Open Library/MusicBrainz/arXiv/Hacker News/Nominatim 等外部域均复用 `resolve_endpoint` DNS-pinning；Nominatim/MusicBrainz 请求节流（1 req/s）+ User-Agent。
- **依赖**：纯 `httpx` 直调，**不新增 pip 依赖**（`tavily-python` 因无法复用 DNS-pin 弃用）。
- **成本**：Tavily 免费额度约 1000 次/月；兜底池各源 free 无 Key；仅在 `search_and_extract` 被既有"必要触发"路径调用时消耗（图富强相关节点 <6 / 时间轴 <5），符合 NFR-6 分层成本控制。

---

## 3. Recommended Approach

**路径选择：Direct Adjustment**（现有计划内直接调整，不推翻任何决策、无需回滚、无需缩减 MVP）

**工作量估算**：

| 提案 | 内容 | 估算 |
|:---|:---|:---|
| W1 | Tavily Key 设置页配置（后端 ConfigService/API + 前端设置页字段） | 0.5 人日 |
| W2 | `WebSearch` 重写：Tavily 主源 + **领域感知权威源兜底池（按实体类型路由）** + LLM 综合 + 退化 | 2 人日 |
| W3 | 单元测试（Mock 外部，锁死分层路由与退化） | 0.5 人日 |
| W4 | 文档同步（PRD/Epics/Architecture） | 已应用 |
| **合计** | | **约 3 人日** |

**风险评估**：

| 风险 | 等级 | 缓解 |
|:---|:---|:---|
| Tavily 免费额度限制/故障 | 中 | 权威兜底池（Wikipedia/OpenAlex）降级接管；全失败退 LLM 记忆；结果缓存 |
| 权威兜底源返回内容过薄 | 低 | 多层数据源拼接 + LLM 综合；单一源不足自动进入下一层 |
| LLM 综合时编造内容 | 中 | Prompt 约束"仅基于给定材料概括，禁止编造"；输出仍由下游 relevance 过滤 + 置信度标注 |
| 设置页新增字段引入前端回归 | 低 | 沿用现有表单模式（password + hasExistingKey），纯增量字段 |
| Tavily Key 泄露 | 低 | 与 LLM Key 同规则：只存 Redis、只透出布尔、PUT 不回显；测试用 mock |

**时间线影响**：约 3 人日，独立批次；不阻塞任何在途工作；与已完成的 P1-P10 图谱质量批次无冲突。

---

## 4. Detailed Change Proposals

以下 4 条提案已经 BMad 在增量模式下逐条批准（`[a]`）。

### 4.1 W1：Tavily API Key 设置页配置（如 LLM）

**后端：**

`backend/app/services/config_service.py` — `LLMConfig` 增加字段：
```python
tavily_api_key: str = Field(default="", description="Tavily 全网搜索 API Key")
```

`backend/app/api/config.py`：
- `GET /config/llm` 响应增加 `"has_tavily_api_key": bool(config.tavily_api_key)`（不回传 Key 本身）。
- `LLMConfigUpdate` 增加 `tavily_api_key: str = ""`；`PUT` 透传 `tavily_api_key=body.tavily_api_key`。

**前端 `frontend/src/app/settings/page.tsx`：**
- 新增 state `tavilyApiKey` / `hasExistingTavilyKey`；挂载 GET 读 `has_tavily_api_key`，Key 置空不回显。
- 保存 PUT body 增加 `tavily_api_key: tavilyApiKey`；成功后 `setHasExistingTavilyKey(true)` + 清空输入框。
- 表单新增「Tavily API Key」password 输入框：已配置 placeholder「已配置（输入新 Key 覆盖）」/ 否则「输入 Tavily API Key...」，附说明「全网搜索用，申请自 tavily.com，可留空」。

**理由**：Tavily Key 与 LLM Key 同为运行时密钥，走同一套 Redis 配置 + 设置页，体验一致；布尔透出满足"已配置"提示且不回传密钥。

### 4.2 W2：`WebSearch` 真实全网实现（Tavily 主源 + 领域感知权威源兜底池）

**文件**：`backend/app/ai/web_search.py`（重写，复用 DNS-pinning 与 ConfigService）

**三层数据源**（替换现有 LLM 记忆占位）：

```
search_and_extract(query):
  Layer 1: Tavily 全网搜索（真实联网，主源）
     有 Key → POST api.tavily.com/search（advanced，max 5，include_answer）
     失败/无 Key/结果过薄 ↓
  Layer 2: 领域感知权威源兜底池（按实体类型路由，直接查询，非 Tavily 内配置）
     person          → Wikipedia + OpenAlex + GitHub(作品/组织)
     concept/学术    → Wikipedia + OpenAlex + arXiv + Wiktionary
     technology/软件 → Wikipedia + GitHub + arXiv + Hacker News
     book/文学       → Wikipedia + Open Library
     music/专辑      → Wikipedia + MusicBrainz
     place/国家/城市  → Wikipedia + Nominatim(OSM)
     event/新闻类    → Wikipedia + Hacker News + (GNews 可选)
  Layer 3: 终极兜底 —— 无任何外部源可用时退到 LLM 记忆摘要（现行为）
  → 将采集到的真实内容拼接 → LLM 综合成聚焦摘要（仅基于给定材料，禁止编造）→ 返回
```

**权威兜底源初选**（全部免费、无需 Key 或可选，除 Wikipedia 与 OpenAlex 外均非学术；池子做成统一连接器列表，后续增源只加一个适配器）：

| 源 | 覆盖领域 | 类型 | Key |
|:---|:---|:---|:---|
| Wikipedia REST（zh/en） | 通用百科正文 | 通用 | 无 |
| OpenAlex | 学术文献 | 学术 | 无 |
| GitHub API | 软件/项目/组织 | 技术 | 无 |
| Wiktionary API | 词条定义/词源 | 通用 | 无 |
| Open Library | 图书/作者 | 文艺 | 无 |
| MusicBrainz | 音乐/艺术家/专辑 | 文艺 | 无 |
| arXiv API | 预印本（科技/AI） | 学术 | 无 |
| Hacker News (Algolia) | 科技新闻/讨论 | 新闻 | 无 |
| Nominatim (OSM) | 地名/城市/国家 | 地理 | 无 |
| GNews（可选） | 通用新闻 | 新闻 | 可选 |

（百度百科/Britannica 因强反爬/无免费 API 暂缓，列入可扩展池。）

**关键实现点：**
- **统一连接器接口**：每源一个适配器类（`name` + `query` + `parse`，约 10-30 行），路由表按实体类型选源，`无新 pip 依赖`（全 httpx）。
- **按实体类型路由**：复用 P7 类型推断，冷门名词自动落到最合适的源组合。
- **逐源容错**：单个源失败不影响其他源，全部失败才进 Layer 3。
- 安全：所有外部域走 `resolve_endpoint` DNS-pinning；Nominatim/MusicBrainz 请求节流（1 req/s）+ User-Agent。
- Tavily Key 运行时从 ConfigService 读（W1），无需重启。
- 返回结构增加非破坏性 `sources: [{name, url}]`；下游图富/时间轴仍只读 `summary`，自动受益。

**理由**：兑现 PRD/架构规划的 "AI Web Search"；把图富与时间轴兜底输入从"LLM 记忆"升级为"真实全网 + 多领域权威源"；覆盖非学术领域（技术/文艺/新闻/地理）；无 Key 时优雅退化，不破坏现有流程。

### 4.3 W3：单元测试（Mock 外部，不发真实请求）

**文件**：新增 `backend/tests/test_services/test_web_search.py`

| # | 场景 | 断言 |
|:---:|:---|:---|
| T1 | 未配置 Tavily Key | 走 LLM 记忆降级路径，返回 summary，无外部 HTTP 调用 |
| T2 | Tavily 搜索成功 | 真实调用 Tavily；LLM 综合的是**搜索到的真实内容**（非空 prompt）；`sources` 含 Tavily 结果 URL |
| T3 | Tavily 失败/结果过薄 | 降级到领域感知权威兜底池，summary 来自兜底内容 |
| T4 | Tavily + 兜底池全部失败 | 最终退到 LLM 记忆摘要（graceful degradation，不抛异常） |
| T5 | 请求参数 | Tavily 请求体含 `max_results`、`search_depth`、`include_answer` |
| T6 | DNS-pinning 复用 | 对 `api.tavily.com` 走 `resolve_endpoint`/`make_http_client`（不裸 httpx 直连） |
| T7 | 实体类型路由 | `person` 类型 → Wikipedia+OpenAlex+GitHub；`technology` 类型 → GitHub+Hacker News；逐源失败不影响其他源 |

**实现要点**：Mock 点 = `ConfigService.get_llm_config`（有无 tavily key）、`httpx`（各外部域响应）、`LLMClient.generate_summary`；复用现有测试模式，零真实网络请求。

**理由**：核心是"数据源分层 + 类型路由 + 优雅退化"，用测试锁住各层行为，防止后续改动改坏降级路径；验证 Tavily 参数与 DNS-pin 安全接线。

### 4.4 W4：文档同步（✅ 已应用 2026-08-01）

**PRD 修订：**

**FR-3 特征级 NFR**（[prd.md:162](backend/../_bmad-output/prds/prd-Logos-2026-07-30/prd.md#L162)）
> OLD：`图谱构建使用分层数据源策略：Wikidata API（免费结构化数据） → LLM 补充提取 → spaCy 备选`
> NEW：`图谱构建使用分层数据源策略：Wikidata API（免费结构化数据，主源） → AI Web Search（Tavily 全网搜索） + 领域感知权威源兜底池（Wikipedia / OpenAlex / GitHub / Open Library / MusicBrainz / arXiv / Hacker News / Nominatim 等，按实体类型路由） → LLM 综合提取 → spaCy 备选`
> 追加：`外部事实来源：Wikidata/Wikipedia 结构化 + Tavily 全网搜索 + 多源权威兜底池（运行时在设置页配置 TAVILY_API_KEY，未配置时静默退化）`

**开放问题 #5**（[prd.md:466](backend/../_bmad-output/prds/prd-Logos-2026-07-30/prd.md#L466)）
> OLD：`5. **数据源 SLA 依赖** — Wikidata API 的服务可用性变化如何应对？`
> NEW：`5. **数据源 SLA 依赖** — Wikidata API 的服务可用性变化如何应对？（AI Web Search 已接入 Tavily 全网搜索 + 领域感知多源权威兜底池，单一数据源故障时自动降级，缓解依赖）`

**Epics 修订：** Story 1.5 新增 AC（[epics.md:319](backend/../_bmad-output/epics.md#L319)）
> `And AI Web Search 走真实全网搜索（Tavily API，运行时设置页配置 Key）；Tavily 结果不足/不可用时由领域感知权威源兜底池扩充（Wikipedia / OpenAlex / GitHub / Open Library / MusicBrainz / arXiv / Hacker News / Nominatim 等，按实体类型路由，覆盖学术与非学术领域），仍不足时退化 LLM 记忆摘要（静默，不阻塞图谱构建）`

**Architecture 修订：** 追加 ADR-006（[architecture.md:116](backend/../_bmad-output/architecture.md#L116)）
> **ADR-006：外部事实来源 = Wikidata 结构化 + Tavily 全网搜索 + 领域感知权威源兜底池** — 主源 Wikidata/Wikipedia 结构化；AI Web Search = Tavily API（server-side、DNS-pinned、Key 运行时设置页配置）；Tavily 不足时兜底池 = Wikipedia / OpenAlex / GitHub / Open Library / MusicBrainz / arXiv / Hacker News / Nominatim 等（按实体类型路由，覆盖学术与非学术）；无 Key/全失败时退化 LLM 记忆摘要。零前端改动；纯 httpx 直调复用 DNS-pinning，不新增 pip 依赖。

---

## 5. Implementation Handoff

### 变更范围分类：**Moderate**（Epic 1/2 多 Story 措辞调整 + 后端模块重写 + 设置页新增字段，需 PO/DEV 协同）

### 交接对象与职责

| 角色 | 职责 |
|:---|:---|
| **PO / BMad** | 批准本提案（已完成）；确认 W1 设置页字段与"权威兜底源初选"清单；后续可扩展兜底源池 |
| **Developer agent** | 按 W1 → W2 → W3 顺序实现；补 `test_web_search.py` 单测；验证设置页保存/回显 |
| **Architect（如需）** | 复核三层数据源 + 优雅退化设计与 ADR-006 记录 |

### 实现顺序与依赖

```
W1 设置页 Tavily Key 配置（后端 ConfigService/API + 前端表单）
   ↓ （WebSearch 运行时读 Key，依赖 W1）
W2 WebSearch 三层数据源重写（Tavily + Wikipedia/OpenAlex 兜底池 + LLM 综合 + 退化）
   ↓
W3 单元测试（T1-T6，锁死分层与退化）
   ↓
验证：设置页保存 Tavily Key → 搜索一个冷门名词 → 图富/时间轴含真实全网内容；无 Key 时行为不变
```

### 成功标准

- [x] 设置页可配置 Tavily API Key（保存/已配置提示/不回显），`GET/PUT /config/llm` 透传 `has_tavily_api_key`
- [x] 配置 Tavily Key 后，`search_and_extract` 真实调用 Tavily；返回 `summary` 基于真实全网内容，`sources` 含结果 URL
- [x] Tavily 无 Key/失败/结果过薄时，降级到领域感知权威源兜底池（按实体类型路由，逐源容错）；全失败退 LLM 记忆（不抛异常、不阻塞图富/时间轴）
- [x] 无新 pip 依赖；所有外部域均走 DNS-pinning；Nominatim/MusicBrainz 节流 + User-Agent
- [x] 后端 `pytest` 通过（`test_web_search.py` 七类场景）
- [x] 文档修订已应用（PRD/Epics/Architecture）
- [ ] 浏览器端全流程验证（配置 Key → 搜索 → 图富/时间轴数据来源确认）——依赖本机网络 + LLM 配置，见 Dev 实施注意事项

---

## 附：本次决策记录

| 决策点 | 结论 |
|:---|:---|
| 工作模式 | 增量模式，四条提案逐条批准（W2 经修订扩展为多源兜底池） |
| 全网搜索方案 | **Tavily API 主源** + **领域感知权威源兜底池**（直接查询，按实体类型路由，非 Tavily 内 `include_domains` 配置） |
| 权威兜底源初选 | Wikipedia / OpenAlex / GitHub / Open Library / MusicBrainz / arXiv / Hacker News / Nominatim 等（free、稳定、无 Key、统一连接器可扩展） |
| 配置方式 | Tavily Key **走设置页**（如 LLM，Redis 运行时生效），非 .env |
| 应用范围 | **仅替换占位**：零前端展示改动（设置页字段除外），图富/时间轴自动受益 |
| 依赖策略 | 纯 httpx 直调复用 DNS-pinning；不新增 pip 依赖；弃用 `tavily-python` |
| 退化策略 | Tavily → 领域感知多源兜底池 → LLM 记忆，逐层静默降级，不阻塞现有流程 |
