# Sprint Change Proposal — 实体消歧与跨语言搜索增强

**日期:** 2026-07-30
**提出人:** BMad
**触发 Story:** Story 1.3（名词搜索 API 与 Wikidata 集成）

---

## 1. 问题摘要

当用户搜索名词时，可能遇到同音/同形不同义实体（如"苹果"→水果/苹果公司/Apple Records），当前系统直接返回 Wikidata 结果列表而不做消歧，用户无法明确选择目标实体。同时也缺少跨语言实体的统一消歧策略。

**具体场景：**
- **同形异义词：** "苹果"（水果/公司）、"Java"（岛/语言/咖啡）
- **同名不同人：** "迈克尔·乔丹"（运动员/科学家）
- **跨语言重名：** "Einstein" 搜索时 Wikidata 返回爱因斯坦姓氏/阿尔伯特·爱因斯坦等

**当前实现缺陷：**
1. 搜索 API 返回原始 Wikidata 结果，无消歧信息
2. 无消歧交互 UI，用户不知如何选择
3. 无实体去重逻辑：不同语言的同一实体未合并
4. 搜索结果缺少区分性描述辅助用户判断

---

## 2. 影响分析

| 维度 | 影响 |
|------|------|
| **Epic 影响** | Epic 1（搜索与图谱构建）：需增强 Story 1.3，新增子 Story 1.3b |
| **Story 影响** | Story 1.3（搜索 API）需增强；Story 1.4 搜索建议需接入消歧；Story 2.4 搜索页需集成消歧UI |
| **架构冲突** | 搜索 API 响应格式需扩展 `needs_disambiguation` / `disambiguation_groups` |
| **前端冲突** | 缺少 DisambiguationDialog 组件设计；SearchBar 交互流程需修改 |
| **数据模型** | 需定义消歧分组模型 DisambiguationGroup |
| **技术影响** | 低——所有改动是在现有结构上做加法，无重写 |

---

## 3. 推荐方案

**路径选择：直接调整（Direct Adjustment）**

**理由：** 
- 消歧是搜索体验的必要质量特性，非 scope 变更
- 已在 Story 1.3 基础上完成基础搜索，只需在 API 响应格式增加消歧字段 + 新增消歧 UI 组件
- 无需回退已提交代码，不影响项目时间线

**关键决策已确认：**
1. ⚡ 消歧交互方式：**消歧弹窗选择**（非自动跳转）
2. ⚡ 消歧触发条件：**严格模式**——只要有多选结果就弹出
3. ⚡ 跨语言显示：**用户语言优先级**（搜中文显中文，搜英文显英文）

---

## 4. 详细变更提案

### 4.1 Story 修改

#### Story 1.3 — 名词搜索 API 增强

在现有实现基础上，对搜索 API 响应格式做加法：

**修改 `backend/app/models/noun.py`：**
```python
class NounSearchResponse(BaseModel):
    results: list[NounResponse] = []
    query: str
    total: int = 0
    needs_disambiguation: bool = False        # 新增
    disambiguation_groups: list[DisambiguationGroup] = []  # 新增
```

**修改 `backend/app/services/search_service.py`：**
- 搜索结果按 Q ID 去重合并（不同语言标签 belong to 同一实体）
- 当实体数量 > 1 且 description 明显不同时，设置 `needs_disambiguation = True`
- 返回消歧分组信息（名称、类型、描述、置信度）

**API 返回示例：**
```json
{
  "query": "苹果",
  "results": [...],
  "total": 3,
  "needs_disambiguation": true,
  "disambiguation_groups": [
    {
      "id": "Q89",
      "label": "苹果",
      "label_en": "apple",
      "type": "entity",
      "type_label": "水果/食品",
      "confidence": 0.9,
      "summary": "蔷薇科植物的果实"
    },
    {
      "id": "Q312",
      "label": "苹果公司",
      "label_en": "Apple Inc.",
      "type": "entity",
      "type_label": "技术公司",
      "confidence": 0.9,
      "summary": "美国跨国科技公司"
    }
  ]
}
```

#### 新增 Story 1.3b — 实体消歧与用户选择界面

**Acceptance Criteria:**

- **Given** 用户搜索一个有多义的名词
- **When** API 返回 `needs_disambiguation: true`
- **Then** 前端弹出 DisambiguationDialog 消歧弹窗
- **And** 消歧弹窗展示每个实体的：名称、英文名、类型标签、置信度、一句话描述
- **And** 弹窗支持键盘导航（↑↓选择，Enter确认，Escape关闭）
- **And** 用户选择某一实体后，前端导航至该实体的图谱页 `/search?q={entity_id}`
- **And** 使用 Wikidata 的实例类型（P31）和描述自动生成实体区分信息
- **And** 各实体按置信度降序排列，优先展示权威结果（有 Wikipedia 页面的）

### 4.2 架构文档更新

请在 `_bmad-output/architecture.md` 中：
1. **API 边界表格**：/api/nouns 的 "消歧"标注保持不变，增加响应字段描述
2. **数据流图**：在"用户搜名词"流程中添加消歧判断步骤
3. **组件树**：frontend 组件列表增加 `DisambiguationDialog`

### 4.3 前端设计更新

请在 `_bmad-output/frontend-design.md` 中：
1. **组件树**：`components/search/` 下新增 `DisambiguationDialog.tsx`
2. **SearchBar 交互**：增加消歧流程描述
3. **API 规范**：10.3 类型定义增加消歧相关类型

### 4.4 修改文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/app/models/noun.py` | 修改 | 新增 DisambiguationGroup 模型和 needs_disambiguation 字段 |
| `backend/app/services/search_service.py` | 修改 | 实体去重+消歧判断逻辑 |
| `backend/app/api/nouns.py` | 修改 | 使用新模型 |
| `frontend/src/components/search/DisambiguationDialog.tsx` | **新建** | 消歧弹窗组件 |
| `frontend/src/app/search/page.tsx` | 修改 | 接入消歧流程 |
| `frontend/src/lib/api.ts` | 修改 | 新增消歧类型定义 |
| `_bmad-output/architecture.md` | 修改 | 数据流增加消歧步骤 |
| `_bmad-output/frontend-design.md` | 修改 | 组件树+交互流程 |
| `_bmad-output/epics.md` | 修改 | 新增 Story 1.3b |

---

## 5. 实施交接

| 角色 | 职责 |
|------|------|
| **Developer** | 实施 4.1 中所有代码变更（后端模型+服务 + 前端组件+流程） |
| **Developer** | 更新 `epics.md` 添加 Story 1.3b |
| **Developer** | 更新 `architecture.md` 和 `frontend-design.md` 的相应章节 |

**变更等级：** ⚡ Minor（可直接由 Developer 实现）

**成功率判断：**
- 所有改动均为现有结构上的加法
- 已存在完整的搜索 API、搜索服务、API 客户端
- 消歧弹窗可复用现有的 Modal 组件
- 无需新增第三方依赖

---

*提案状态：✅ 已获用户批准（2026-07-30）*
