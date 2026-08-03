# Dev Agent Record — 图谱质量增强批次（P1–P10）

- **故事范围**：两份已批准 Sprint Change Proposal（graph-timeline P1-P6、graph-enrichment P7-P10）
- **实施日期**：2026-08-01
- **baseline_commit**：`1d85588`（`docs: 图谱内容丰富性/降噪与 Web 数据管道变更（P1-P10）文档修订`）
- **实施顺序**：P1 → P2 → P3 → P4 → P5 → P6 → P7 → P8 → P9 → P10
- **状态**：review（待人工评审）

---

## 1. 完成摘要

### P1 数据模型 `relevance` 字段 ✅
- `GraphNode`/`GraphEdge` 增加 `relevance`（与中心实体的相关度，≠confidence 可靠度），pydantic 校验 [0,1]
- Neo4j `upsert_entity`/`upsert_relation` 用 `coalesce($relevance, e.relevance)` 写入——未传 relevance 的旧调用方不冲掉已有值
- `get_graph` 读回 relevance；旧数据（无属性）兜底默认：中心 1.0 / 连通 0.5 / 孤立 0.1
- 前端 `GraphNode`/`GraphEdge` 类型加 `relevance?: number`（非破坏性）

### P2 提取器相关性打分 + 焦点锚定 ✅
- `ExtractedEntity.relevance`（核心 >0.7，弱相关 0.3-0.5，<0.3 不提取）
- `extract_from_text(text, focus_entity=None)` 焦点锚定 system prompt

### P3 图谱构建相关性过滤 + `llm_*` ID 统一解析 ✅
- `merge_llm_entities()`：`relevance>=0.5` 过滤 → `resolve_qid()`（Wikidata label/alias 精确命中 → QID，否则 `llm_*`）→ 无法解析 relevance 封顶 0.5
- 中心实体不重复写；关系仅两端都解析成功才写入
- 冷启动 `build_graph` 复用同一规则

### P4 Wikidata 去噪 + 类型优先级排序 ✅
- 强关联白名单收敛为 `[P800,P1416,P106,P463,P910,P127,P355,P1830]`
- P31/P279 分类节点保留但 `type:"category"` + `relevance:0.2`（方案 B，不剔除）
- 按类型优先级 `person>event>technology>organization>concept>entity>category` 排序后截断 `_RELATED_LIMIT`

### P5 正常搜索触发 Web 丰富（同步合并）✅
- 基础图谱强相关节点（relevance>=0.6，不含中心）<6 时触发 `WebSearch + LLM` 提取合并
- 丰富结果缓存 1h（`web_enrich:{qid}`）；图谱缓存 1h
- LLM 未配置 / 任何失败 → 静默退化为基础图谱（不拖垮请求）

### P6 时间轴 AI 兜底丰富 ✅
- `Summarizer.extract_milestones()` 结构化里程碑提取（替换 TODO 占位 `extract_key_facts`）
- Wikidata 里程碑 <5 时 Web Search + 里程碑提取兜底合并：`(year,title)` 去重、Wikidata 优先、AI 标置信度 0.5、按年份排序、封顶 10
- Wikidata 里程碑补来源链接（sitelink）

### P7 通用实体类型推断（规则表 + AI 兜底）✅
- `_ENTITY_TYPE_MAP` 覆盖 person/organization/technology/event/concept（QID 均经 Wikidata API 校验）
- 修复旧映射 3 处 QID bug：Q577=年（误标编程语言）、Q11424=电影（误标 technology）、Q16521=生物分类单元（误标 event）；Q7889 电子游戏误标 person 修复为 technology
- 三层推断：P31 直映射 → P279 子类继承（含实体自身 P279 + 批量拉取 P31 目标类父类）→ 描述关键词兜底
- AI 兜底：`EntityExtractionResult.focus_entity_type`，仅当中心规则类型为 entity 且 LLM 已配置时覆盖写回

### P8 关系类型映射 + Neo4j 边规范化 ✅
- `_RELATION_TYPE_MAP`：P800/P50/P144→creation；P106/P1416/P463/P127/P355/P361→affiliation；P2860/P737→influence；P910/P1830/P279→other
- `_extract_related_qids` 返回 `(qid, prop)`；写边 UPPER_SNAKE
- Neo4j 读回归一为小写语义类型（`_EDGE_TYPE_READ_MAP`），未知/`related_to` → `other`；`upsert_relation` 写前归一 UPPER_SNAKE

### P9 弱关联淡化（前后端）✅
- 后端：孤立节点 relevance 0.1；不剔除任何数据
- 前端：边 `stroke-opacity = 0.2+conf*0.5`、`stroke-width=max(0.75, conf*3)`、低置信度虚线 `3,5`（阈值对齐图例 MEDIUM 档 <0.5）；节点 `opacity = 中心1 : 0.45+relevance*0.55`
- 淡化开关（默认开）：关闭时弱边恢复实线全透明度；切换只更新属性不重建整图（保留缩放/布局）

### P10 前端类型体系对齐 ✅
- `GraphNode.type` 联合拓宽为 7 种（`NodeType`）；`category: #94A3B8`
- GraphCanvas 配色 / GraphLegend 图例 / GraphNodePanel 类型标签同步；删除死代码 `types/graph.ts`

---

## 2. 多代理对抗性评审（2026-08-01）

4 维度并行评审（correctness/contract/security-robustness/frontend）+ 28 个 subagent 对抗性验证，共 24 条发现，19 条确认。

### 已修复（评审确认的真缺陷）
| # | 严重度 | 问题 | 修复 |
|:--|:--|:--|:--|
| 1 | HIGH | P5 丰富在内存去重前先把 LLM 值写库，覆盖 P4 基础图谱（破坏 Wikidata 优先契约） | `merge_llm_entities` 新增 `existing_node_ids`/`existing_edge_keys`/`existing_relevance`，已有节点/边跳过写库 |
| 2 | MEDIUM | 中心实体边 relevance 被兜底 0.5 截断 | 中心 `id_relevance[center_id]=1.0` 预置 |
| 3 | MEDIUM | 写侧 `coalesce(...,0.0)` 与读侧 None 兜底矛盾，主摄取路径节点恒 0.0 | coalesce 去掉第三参 0.0，未传 relevance 保持属性缺失 |
| 4 | MEDIUM | 冷启动中心节点 relevance 写 0.0 | 由 #3 统一修复（新节点不落 0.0 硬值） |
| 5 | MEDIUM | `search_service.TYPE_LABEL_MAP` 仍用旧 P31 语义 | 与 `_ENTITY_TYPE_MAP` 对齐（Q11424/Q577/Q16521/Q188451/Q9143 等） |
| 6 | MEDIUM | 淡化开关切换整图销毁重建 | ref 存 d3 selection，独立 effect 仅更新 opacity/dash |
| 7 | MEDIUM | 虚线阈值与图例不一致（0.3 vs MEDIUM 0.5） | 用 `CONFIDENCE_LEVELS.MEDIUM.min` |
| 8 | LOW | 死代码 `types/graph.ts`（仅 3 类型） | 删除 |
| 9 | LOW | `get_graph` depth 注入无本地防护 | 本地强校验并 clamp [1,3] |
| 10 | LOW | neo4j_repo 头注释与 P8 语义不符 | 更新文档 |
| 11 | LOW | AI 里程碑 source_url 指向实体 sitelink | **保留**：WebSearch 占位实现不返回来源 URL，sitelink 为当前可得的最佳来源；已标注 AI 置信度 0.5 |

### 保留（提案已批准的明确设计，非缺陷）
- **同步合并延迟 +3-10s**：P5 决策记录明确"本迭代采用同步合并（零前端改动）；SSE 增量列 Phase 2"
- **边淡化用 confidence 而非 relevance**：P9 方案 Y 明确"边透明度随 confidence、节点透明度随 relevance 分级"
- **edgeOpacity 上限 0.7**：P9 公式 `0.2 + confidence*0.5` 即提案原文
- **P7 每实体嵌套 `_get_subclass_of` HTTP 调用**：仅在 P31 直映射未命中时触发（成本受控，符合 NFR-6 分层）
- **Neo4j 非事务写**：既有设计（单语句 MERGE），非本次引入
- **`qid_resolve` 按名缓存 1h**：精确匹配保证低错配风险，缓存已 1h

### 修复过程新增回归测试
- 中心边 relevance 不被 0.5 截断（应=min(1.0, 节点relevance)）
- Wikidata 优先：已有节点/边不被 LLM 覆盖写库

---

## 3. 测试与验证

| 项目 | 结果 |
|:--|:--|
| 后端 pytest 全量 | **125 passed**（新增 8 个测试文件，含 7 个新测试文件覆盖 P1-P10 + 3 个评审回归测试） |
| 前端 `tsc --noEmit` | ✅ 0 错误 |
| 前端 eslint（改动文件） | ✅ 无新增错误（既有 `as any`/死变量警告保留） |
| 真实 Wikidata E2E | ✅ Q312→organization、Q6881511（工商企业）经 P279 继承→organization、Q7215242（Category）→entity；Q312 P355/P127/P1830/P463 白名单命中产生强关联 |

### 新增测试文件
- `tests/test_services/test_relevance.py`（P1）
- `tests/test_services/test_extractor.py`（P2）
- `tests/test_services/test_graph_service_relevance.py`（P3 + 评审回归）
- `tests/test_services/test_graph_denoise.py`（P4）
- `tests/test_services/test_graph_enrichment.py`（P5）
- `tests/test_services/test_timeline_fallback.py`（P6）
- `tests/test_services/test_type_inference.py`（P7）
- `tests/test_services/test_relation_mapping.py`（P8）

---

## 4. 文件清单（相对 repo 根）

**Modified**
- `backend/app/models/graph.py`
- `backend/app/repositories/neo4j_repo.py`
- `backend/app/repositories/wikidata_repo.py`
- `backend/app/api/graph.py`
- `backend/app/services/graph_service.py`
- `backend/app/services/timeline_service.py`
- `backend/app/services/search_service.py`
- `backend/app/ai/extractor.py`
- `backend/app/ai/summarizer.py`
- `frontend/src/lib/api.ts`
- `frontend/src/components/graph/GraphCanvas.tsx`
- `frontend/src/components/graph/GraphLegend.tsx`
- `frontend/src/components/graph/GraphNodePanel.tsx`

**Deleted**
- `frontend/src/types/graph.ts`（死代码）

**Added**
- 8 个后端测试文件（见上）

---

## 5. 注意事项（Dev → Reviewer）

1. **`_RELATION_PROPS` 手写拼装**：`_STRONG_RELATION_PROPS`/`_EXTRA_RELATION_PROPS`/`_CATEGORY_PROPS` 定义后由 `_RELATION_PROPS` 显式引用，三处清单可能漂移——后续建议改为程序化拼接（`_STRONG + _EXTRA + _CATEGORY`）。
2. **Wikidata 直连 SSL**：本机 python httpx 直连 wikidata.org 抛 `SSL: UNEXPECTED_EOF`，curl 正常；生产/开发环境需配置代理或由 `settings.http_proxy` 注入（仓库已有代理支持）。
3. **`web_enrich` 缓存与图谱缓存双 TTL**：`get_graph` 先读 `graph:{id}:depth1`（1h），命中即短路，`web_enrich` 缓存作为第二层防护。
4. **LLM 未配置时**：`search_and_extract` 返回空摘要 → P5/P6 静默退化为纯 Wikidata（已测）。
5. **历史快照兼容**：`HistorySnapshot` 存的 graph JSON 无 relevance 字段 → 前端 `?? 0.5` 兜底（旧数据），新数据含真实值。
6. **Windows + fake-ip DNS（Clash）下 `getaddrinfo` 返回 `socktype=0`**：`endpoint_security.resolve_endpoint` 的 `_DNSFixedTransport.pinned()` 曾因严格过滤 `info[1] == type` 把缓存滤空，导致 LLM 配置测试与运行时 LLM 管道全部 `Connection error`；已修复（socktype/proto 的 0 视为任意匹配，family 保持严格），见 `test_endpoint_security.py` 回归测试。该环境同时是注意事项 2（Wikidata SSL）的可能诱因。
