# Logos 前端设计文档

> 基于 PRFAQ、架构决策文档及 UI/UX Pro Max 设计智能生成
> 产品：Logos — AI 名词知识图谱与演化平台
> 日期：2026-07-30
> 栈：Next.js v16 + TypeScript + Tailwind CSS + D3.js + vis-timeline

---

## 1. Design System

### 1.1 设计风格

**主风格：最小主义 + 内容优先（Exaggerated Minimalism）**
- 大留白、大字号排版、高对比度
- 图谱占视觉主体，UI 元素退让为背景
- 深色模式为主（图谱可视化对焦光），浅色模式为辅

**辅助风格：Zero Interface**
- AI 驱动的渐进式信息披露，界面元素"按需出现"
- 搜索框常驻，其余面板在搜索完成后逐步展开
- 预测性 UI（如热门名词建议、搜索历史）

### 1.2 色彩系统

#### Light Mode（默认）

| 角色 | Hex | Tailwind | 用途 |
|------|-----|----------|------|
| Primary | `#475569` | `slate-600` | 品牌主色，交互元素 |
| On Primary | `#FFFFFF` | `white` | 主色上的文字 |
| Accent/CTA | `#2563EB` | `blue-600` | 搜索按钮、链接、节点高亮 |
| Background | `#F8FAFC` | `slate-50` | 页面背景 |
| Foreground | `#1E293B` | `slate-900` | 主文字 |
| Card | `#FFFFFF` | `white` | 卡片、面板背景 |
| Card Foreground | `#1E293B` | `slate-900` | 卡片内文字 |
| Muted | `#EAEFF3` | `slate-200` | 次要背景、分割线 |
| Muted Foreground | `#64748B` | `slate-500` | 次要文字 |
| Border | `#E2E8F0` | `slate-200` | 边框、分割线 |
| Destructive | `#DC2626` | `red-600` | 错误、危险操作 |
| Success | `#16A34A` | `green-600` | 成功、高置信度 |
| Warning | `#D97706` | `amber-600` | 低置信度、待验证 |
| Ring | `#475569` | `slate-600` | 焦点环 |

#### Dark Mode（主要模式）

| 角色 | Hex | Tailwind | 用途 |
|------|-----|----------|------|
| Primary | `#818CF8` | `indigo-400` | 品牌主色 |
| On Primary | `#0F172A` | `slate-900` | 主色上文字 |
| Accent/CTA | `#60A5FA` | `blue-400` | 搜索、链接、高亮 |
| Background | `#0A0A0F` | `neutral-950` | 页面背景（深黑专注） |
| Foreground | `#F1F5F9` | `slate-100` | 主文字 |
| Card | `#18181B` | `zinc-900` | 面板背景 |
| Card Foreground | `#E2E8F0` | `slate-200` | 卡片内文字 |
| Muted | `#27272A` | `zinc-800` | 次要背景 |
| Muted Foreground | `#A1A1AA` | `zinc-400` | 次要文字 |
| Border | `#3F3F46` | `zinc-700` | 边框 |
| Destructive | `#F87171` | `red-400` | 错误 |
| Success | `#4ADE80` | `green-400` | 成功、高置信度 |
| Warning | `#FBBF24` | `amber-400` | 低置信度 |
| Ring | `#818CF8` | `indigo-400` | 焦点环 |

### 1.3 排版系统

**字体家族：Inter**
- 功能型瑞士风格字体，适合数据密集界面
- Google Fonts CDN：`Inter:wght@300;400;500;600;700`

**字号层级（Type Scale）：**

| 层级 | 大小 | 字重 | 行高 | 用途 |
|------|------|------|------|------|
| Display | `clamp(2.5rem, 6vw, 4rem)` | 700 | 1.1 | 首页大标题 |
| h1 | `clamp(1.5rem, 4vw, 2.5rem)` | 700 | 1.2 | 页面标题 |
| h2 | `1.5rem` | 600 | 1.3 | 区块标题 |
| h3 | `1.25rem` | 600 | 1.4 | 面板标题 |
| Body | `1rem` | 400 | 1.6 | 正文 |
| Body-sm | `0.875rem` | 400 | 1.5 | 辅助文字 |
| Caption | `0.75rem` | 400 | 1.5 | 标签、图注 |
| Mono | `0.875rem` | 400 | 1.5 | 数据值、置信度 |

### 1.4 间距系统

采用 **4px 增量** 间距体系（Tailwind 原生支持）：

| Token | rem | px | 用途 |
|-------|-----|----|------|
| `space-1` | 0.25rem | 4px | 微间距 |
| `space-2` | 0.5rem | 8px | 密集行内间距 |
| `space-3` | 0.75rem | 12px | 标签/徽章间距 |
| `space-4` | 1rem | 16px | 标准间距 |
| `space-6` | 1.5rem | 24px | 段落间距 |
| `space-8` | 2rem | 32px | 组件间距 |
| `space-12` | 3rem | 48px | 区块间距 |
| `space-16` | 4rem | 64px | 大区块间距 |
| `space-20` | 5rem | 80px | 页面节间距 |

### 1.5 圆角系统

| Token | 值 | 用途 |
|-------|----|------|
| `rounded-sm` | 4px | 输入框、按钮 |
| `rounded-md` | 8px | 卡片、面板 |
| `rounded-lg` | 12px | 模态框 |
| `rounded-xl` | 16px | 搜索栏 |
| `rounded-full` | 9999px | 头像、标签 |

### 1.6 阴影系统（Light Mode）

| 层级 | Tailwind | 用途 |
|------|----------|------|
| 0 | `shadow-none` | 默认 |
| 1 | `shadow-sm` | 卡片悬浮 |
| 2 | `shadow-md` | 下拉面板 |
| 3 | `shadow-lg` | 模态框 |
| 4 | `shadow-xl` | 搜索建议弹窗 |

### 1.7 阴影系统（Dark Mode）

暗色模式下用 **发光边框（glow border）** 替代阴影：

| 层级 | 效果 | 用途 |
|------|------|------|
| 1 | `ring-1 ring-white/5` | 默认面板 |
| 2 | `ring-1 ring-white/10 shadow-lg shadow-black/20` | 悬浮卡片 |
| 3 | `ring-1 ring-white/15 shadow-xl shadow-black/30` | 模态框 |

### 1.8 动效系统

| 元素 | 时长 | 缓动 | 属性 |
|------|------|------|------|
| 悬浮态 | 150ms | `ease-out` | transform, opacity |
| 面板展开 | 200ms | `ease-out` | opacity, transform |
| 图谱节点入 | 300ms | `ease-out` | opacity, transform |
| 图谱节点移 | 400ms | `cubic-bezier(0.34, 1.56, 0.64, 1)` | transform (弹跳) |
| 时间轴滚动 | 250ms | `ease-in-out` | scroll |
| 页面切换 | 200ms | `ease-out` | opacity |
| SSE 增量 | 500ms | `ease-out` | opacity + scale |
| 骨架屏 | 1.5s 循环 | `linear` | opacity 脉冲 |

---

## 2. 页面架构

### 2.1 页面路由结构

```
/                   → Landing Page（首页/品牌入口）
/search?q={noun}    → 搜索图谱结果页（核心页面）
/noun/{id}          → 名词详情（单独入口，支持深度链接）
/history            → 历史搜索列表页（匿名快照）
/history/{noun_id}  → 历史快照详情页（直接渲染已保存快照，不经过搜索流程）
```

> 架构决策：不采用 `/explore/{id}` 泛化路径，使用 `/noun/{id}` 语义化路径，符合人物优先原则且利于 SEO。

### 2.2 页面布局

#### 2.2.1 全局布局 (`app/layout.tsx`)

```
┌─────────────────────────────────────────────┐
│  Nav Bar (Logo + SearchBar + ThemeToggle)    │  ← sticky top, h-16
├─────────────────────────────────────────────┤
│                                             │
│            Main Content Area                 │  ← flex-1, overflow-auto
│                                             │
├─────────────────────────────────────────────┤
│  Footer (仅 Landing 页展示)                  │
└─────────────────────────────────────────────┘
```

#### 2.2.2 图谱页布局 (`/search?q={noun}`)

```
┌─────────────────────────────────────────────┐
│  Nav Bar (compact)                           │  ← h-14, narrower
├──────────────────┬──────────────────────────┤
│                  │                          │
│  侧边栏          │   图谱主区域               │
│  (实体详情)      │   (GraphCanvas)           │  ← flex-1
│                  │                          │
│                  ├──────────────────────────┤
│                  │   时间轴条                │
│                  │   (TimelineCompact)       │  ← h-24
├──────────────────┴──────────────────────────┤
│  搜索查询提示 / 置信度说明                    │  ← 仅在需要时显示
└─────────────────────────────────────────────┘
```

**响应式布局（< 768px）：**

```
┌─────────────────────┐
│  Nav Bar (compact)   │
├─────────────────────┤
│                     │
│   图谱主区域          │  ← 全宽
│                     │
├─────────────────────┤
│  时间轴条             │  ← 可折叠
├─────────────────────┤
│  实体详情 (底部面板)   │  ← 点击节点后滑入式底部面板
└─────────────────────┘
```

---

## 3. 组件树

### 3.1 组件目录结构

```
src/
├── app/
│   ├── globals.css                 # 全局样式 + CSS 自定义属性
│   ├── layout.tsx                  # 全局布局（NavBar + Provider）
│   ├── page.tsx                    # Landing Page
│   ├── loading.tsx                 # 全局加载骨架屏
│   ├── error.tsx                   # 全局错误边界
│   ├── not-found.tsx               # 404 页
│   └── search/
│       ├── page.tsx                # 搜索结果页（图谱主界面）
│       ├── loading.tsx             # 搜索加载骨架屏
│       └── not-found.tsx           # 无搜索结果
│
├── components/
│   ├── layout/
│   │   ├── NavBar.tsx              # 导航栏（Logo + 搜索 + 主题切换）
│   │   ├── NavBarCompact.tsx       # 搜索结果页紧凑导航
│   │   ├── Footer.tsx              # 页脚（仅在首页展示）
│   │   └── ThemeToggle.tsx         # 明暗切换
│   │
│   ├── search/
│   │   ├── SearchBar.tsx           # 搜索输入框（带自动补全）
│   │   ├── SearchSuggestions.tsx   # 热门/历史搜索建议
│   │   ├── SearchHistory.tsx       # 搜索历史记录（本地存储）
│   │   └── SearchEmpty.tsx         # 空搜索状态
│   │
│   ├── graph/
│   │   ├── GraphCanvas.tsx         # D3.js 力导向图画布（核心）
│   │   ├── GraphNode.tsx           # 单个节点渲染（Person/Entity/Event）
│   │   ├── GraphEdge.tsx           # 边渲染（带关系类型着色）
│   │   ├── GraphControls.tsx       # 缩放/重置/全屏/深度控制
│   │   ├── GraphTooltip.tsx        # 节点悬浮信息卡
│   │   ├── GraphLegend.tsx         # 关系类型图例
│   │   ├── GraphNodePanel.tsx      # 侧边栏/底部实体详情面板
│   │   └── GraphSkeleton.tsx       # 图谱加载骨架
│   │
│   ├── timeline/
│   │   ├── TimelineCompact.tsx     # 紧凑时间轴条（图谱页内嵌）
│   │   ├── TimelineFull.tsx        # 完整时间轴页（可展开）
│   │   ├── TimelineItem.tsx        # 单个时间节点
│   │   └── TimelineEmpty.tsx       # 无时间数据状态
│   │
│   └── ui/
│       ├── Button.tsx              # 按钮组件
│       ├── LoadingSpinner.tsx      # 加载旋转器
│       ├── Skeleton.tsx            # 通用骨架屏
│       ├── ConfidenceBadge.tsx     # 置信度徽章（高/中/低）
│       ├── SourceLink.tsx          # 来源链接组件
│       ├── EmptyState.tsx          # 空状态占位
│       ├── ErrorFallback.tsx       # 错误回退 UI
│       ├── Toast.tsx               # 轻提示
│       ├── Modal.tsx               # 模态框
│       ├── Panel.tsx               # 侧滑面板（移动端底部面板）
│       └── Tag.tsx                 # 标签/类型标识
│
├── lib/
│   ├── api.ts                      # API 客户端封装
│   ├── graph-utils.ts             # 图谱数据处理工具
│   ├── sse-client.ts              # SSE 订阅客户端
│   ├── dom-utils.ts               # DOM 工具
│   └── constants.ts               # 常量定义
│
├── hooks/
│   ├── useGraph.ts                 # 图谱数据获取/状态
│   ├── useGraphSSE.ts             # 图谱增量 SSE 订阅
│   ├── useTimeline.ts             # 时间轴数据
│   ├── useSearch.ts               # 搜索状态
│   ├── useDebounce.ts             # 防抖
│   ├── useLocalStorage.ts         # 本地存储
│   ├── useTheme.ts                # 主题切换
│   └── useMediaQuery.ts           # 媒体查询
│
└── types/
    ├── graph.ts                   # 图谱类型定义
    ├── timeline.ts                # 时间轴类型定义
    ├── api.ts                     # API 请求/响应类型
    └── common.ts                  # 通用类型
```

### 3.2 核心组件设计

#### 3.2.1 SearchBar (搜索入口)

```
┌─────────────────────────────────────────────┐
│  🔍  输入名词（中/英文）...           [搜索]  │
└─────────────────────────────────────────────┘
                      ↓
             ┌─────────────────┐
             │ 热门搜索：       │  ← 聚焦时弹出
             │ • 爱因斯坦      │
             │ • 区块链        │
             │ • CRISPR       │
             │                 │
             │ 搜索历史：       │
             │ • 神经网络   ✕  │
             │ • 量子计算   ✕  │
             └─────────────────┘
```

**交互规则：**
- 输入 200ms 防抖自动触发搜索建议
- Enter / 点击按钮触发导航至 `/search?q={term}`
- 焦点时展开 SuggestPanel（热门搜索 + 搜索历史）
- 失焦 300ms 后关闭（防误触）
- 在 `/search` 页时，SearchBar 展示当前搜索词，可修改
- **无障碍：** 搜索按钮 aria-label="搜索名词"，输入框可访问标签

#### 3.2.2 GraphCanvas (图谱主画布)

```
┌────────────────────────────────────────────────────┐
│                          [GraphControls]            │
│    ┌───────┐                                       │
│    │       │  ┌─────┐                              │
│    │   爱   ├──┤相对论│  ┌─────────┐               │
│    │       │  └─────┘  │ 引力波   │                │
│    │ 因斯  │           └─────────┘                │
│    │ 坦    ├──┐                                     │
│    │       │  │  ┌──────────┐                      │
│    └───────┘  └──┤米列娃·   │                      │
│                   │玛丽琦    │                      │
│                   └──────────┘                      │
│                             ┌──────────┐            │
│                             │ 光电效应  │            │
│                             └──────────┘            │
│                                       ┌─────────┐   │
│                                       │ E=mc²   │   │
│                                       └─────────┘   │
└────────────────────────────────────────────────────┘
```

**核心功能：**
- D3.js 力导向图布局（forceSimulation）
- 缩放（滚轮）+ 拖拽（单个节点 + 整体画布）
- 节点类型区分着色和图标：
  - 🟦 Person（人物）：圆形，品牌色
  - 🟩 Entity（实体/概念）：方角，绿色
  - 🟧 Event（事件）：菱形，橙色
- 边类型着色（`GraphLegend` 可切换）
- 点击节点 → 高亮 ego network + 展开侧边栏详情
- 悬浮节点 → `GraphTooltip` 显示名称 + 类型 + 置信度
- 增量节点以 **"冒出"动画**（scale + fade）加入

**技术实现：**
```typescript
// 使用 next/dynamic 延迟加载 D3.js 重量级组件
const GraphCanvas = dynamic(
  () => import('@/components/graph/GraphCanvas'),
  {
    loading: () => <GraphSkeleton />,
    ssr: false,  // D3.js 需要 DOM
  }
)
```

#### 3.2.3 GraphNodePanel (实体详情面板)

```
Desktop:
┌────────────────────────┐
│ 爱因斯坦               │  ← h3, bold
│ Person                 │  ← Tag: 类型标签
│ ───────────────────── │
│ 置信度: ⭐⭐⭐⭐⭐ 95%    │  ← ConfidenceBadge
│ 来源: Wikipedia / AI   │  ← SourceLink
│                        │
│ 知识点摘要              │
│ 阿尔伯特·爱因斯坦是     │  ← body
│ 德国出生的理论物理学家   │
│ ...                    │
│                        │
│ 关联关系                │
│ ┌────────────────────┐ │
│ │ 创  立 → 相对论     │ │  ← relation rows
│ │ 配  偶 → 米列娃     │ │
│ │ 影  响 → 量子力学   │ │
│ └────────────────────┘ │
└────────────────────────┘

Mobile (底部面板):
┌────────────────────────┐
│ ─── 拖拽手柄 ───       │  ← 可拖拽展开/收起
│ 爱因斯坦 · Person      │
│ 置信度: 95%            │
│ 知识点摘要...           │
│ 查看更多 →              │
└────────────────────────┘
```

#### 3.2.4 TimelineCompact (紧凑时间轴条)

```
Desk: < 768px:
┌──────────────────────────────────────────────────┐
│ 📅 演化时间轴                                     │
│ ┌────┬────┬────┬────┬────┬────┬────┬────┬────┬──┐│
│ │1879│1895│1905│1905│1915│1919│1921│1933│1939│...││  ← 关键年份
│ │出生│大. │光..│E=.│相..│验.│诺..│移..│原..│   ││  ← 事件标题
│ └────┴────┴────┴────┴────┴────┴────┴────┴────┴──┘│
│    ← [滑动区域] →       🔍 展开完整时间轴 →       │
└──────────────────────────────────────────────────┘

Mobile:
┌────────────────────────────────────┐
│ 📅 演化时间轴                       │
│ ← [水平滑动区域] →                 │
│ 1879 → 1905 → 1915 → 1921 → 1933  │
└────────────────────────────────────┘
```

#### 3.2.5 Landing Page (首页)

```
┌─────────────────────────────────────────────┐
│ [Logo] Logos                       [主题切换] │  ← NavBar
├─────────────────────────────────────────────┤
│                                             │
│  ┌───────────────────────────────────────┐  │
│  │                                       │  │
│  │  给你的好奇心                          │  │  ← Display 字号
│  │  装一张知识地图                         │  │
│  │                                       │  │
│  │  搜一个名词，自动构建关系图谱            │  │  ← Body 18px
│  │  与演化时间轴                           │  │
│  │                                       │  │
│  │  ┌─────────────────────────────┐      │  │
│  │  │ 🔍 输入名词探索...     [搜索]│      │  │  ← 搜索栏
│  │  └─────────────────────────────┘      │  │     居中，最大宽 560px
│  │                                       │  │
│  │  试试：爱因斯坦 · 区块链 · CRISPR     │  │  ← 热门预置标签
│  │                                       │  │
│  └───────────────────────────────────────┘  │
│                                             │
│ ──── 三功能卡片区 ────                      │
│ ┌────────┐ ┌────────┐ ┌────────┐          │
│ │ 🔗     │ │ 📅     │ │ 🤖     │          │
│ │ 关系图谱│ │ 演化时间│ │ AI 问答│          │
│ │ 自动呈..│ │ 轴关键..│ │ 追问.. │          │
│ └────────┘ └────────┘ └────────┘          │
│                                             │
│ ──── <使用场景 案例区> ────                  │
│ ┌──────────────────────────┐               │
│ │ "用 Logos 十五分钟       │               │  ← 引用卡片
│ │  理清了一个人物关系网"    │               │
│ │  — 林菀，科技记者         │               │
│ └──────────────────────────┘               │
│                                             │
│ ──── Footer ────                            │
│ Logos © 2026 · 知识探索平台                 │
└─────────────────────────────────────────────┘
```

#### 3.2.6 历史记录与重复搜索提示（匿名快照）

> 搜索成功后自动保存匿名快照；SearchBar 的 SuggestPanel 中已有"搜索历史"槽位，承载本地/服务端快照入口。

**HistoryList（历史记录列表）**
- 数据源：GET `/api/history`（匿名，按保存时间倒序）
- 每行：名词 / 解析实体 / 保存时间 / 删除按钮
- 点击行 → 跳转 `/history/{noun_id}` 详情页，仅加载已保存快照（不经过搜索流程）

**HistoryItem**
- 展示快照摘要（名词、实体名、时间），hover 高亮，可删除

**HistoryEmpty**
- 空状态："还没有搜索历史，快去搜索一个名词吧" + 搜索框引导

**DuplicateSearchDialog（重复搜索提示弹窗）**
- 触发：搜索词已存在历史快照
- 文案："已有「{term}」的历史结果（保存于 {时间}）"
- 两个动作：`查看历史快照`（直接加载已保存数据）/ `重新搜索`（重建最新数据并更新快照）
- 参考 DisambiguationDialog 的交互模式（Esc/背板关闭）

---

## 4. 交互设计

### 4.1 核心用户流程

```
┌─────────┐    ┌─────────┐    ┌─────────────────┐
│ 搜索名词 │ → │ 基线图谱 │ → │ 探索交互          │
│         │    │ 骨架展示 │    │ (点击/缩放/拖拽)  │
└─────────┘    └─────────┘    └─────────────────┘
                    │                  │
                    ↓                  ↓
               ┌────────────────┐  ┌─────────────────┐
               │ SSE 增量推送    │  │ 侧边栏实体详情    │
               │ 节点逐步冒出    │  │ 时间轴联动高亮    │
               └────────────────┘  └─────────────────┘

搜索成功 → 解析出实体 → 自动保存匿名快照（服务端）
                          ↓
再次搜索同词 ──→ 已有历史快照？──是──→ DuplicateSearchDialog
                          │                ├─ 查看历史快照 → 加载已保存图谱+时间轴
                          └─否             └─ 重新搜索 → 重建最新数据 + 更新快照
                             正常展示结果
```

### 4.2 增量图谱加载策略

**阶段一（0-500ms）：骨架屏**
- GraphCanvas 位置展示浅色圆形 + 连接线骨架
- 搜索栏显示加载状态

**阶段二（500ms-2s）：基线图谱**
- 5-10 个核心节点 + 边一次性渲染
- 节点以缩放淡入动画逐个出现（每个间隔 30ms）
- 时间轴展示 5 个关键节点

**阶段三（2s+）：SSE 增量**
```
SSE Event: {"type": "nodes_added", "nodes": [...], "edges": [...]}
→ GraphCanvas.addNodes(newNodes)  // 以"冒出"动画插入
→ 新节点从白色 → 逐渐着色（指示正在确认置信度）
→ 新边滑动连接到目标节点
```

### 4.3 时间轴与图谱联动

- 拖拽时间轴滑块 → 图谱节点透明度动态变化
  - 该时间点不存在的节点变淡（opacity 0.3）
  - 该时间点活跃的节点保持高亮
- 点击图谱节点 → 时间轴滚动至该节点关键年份
- 时间轴节点点击 → 图谱自动居中到相关节点并高亮 ego network

### 4.4 图谱交互模式

| 操作 | 效果 |
|------|------|
| 点击节点 | 高亮该节点及一度关系，其余节点半透明 |
| 双击节点 | 展开下一跳节点（请求 API depth+1） |
| 拖拽节点 | 力导向图重新布局 |
| 滚轮缩放 | 地图式缩放，节点大小自适应 |
| 空白拖拽 | 平移画布 |
| 悬浮节点 | 显示 Tooltip（名称 + 类型 + 置信度） |
| 框选（Shift+拖拽） | 批量选中节点 |
| 双击空白 | 重置视图居中 |

### 4.5 空状态 & 错误处理

| 场景 | 展示 | 动作 |
|------|------|------|
| 无搜索结果 | 空状态插图 + "未找到关于 '{term}' 的信息" | 建议尝试其他关键词 |
| 图谱构建失败 | ErrorFallback + 重试按钮 | 显示错误代码和重试 |
| SSE 断连 | Toast 提示"连接中断，正在重连" | 自动重试 3 次 |
| 网络离线 | 离线提示条 + 缓存数据展示 | 显示上次缓存内容 |
| 搜索为空 | 搜索栏保留输入，面板提示"请输入名词" | — |
| 无时间轴数据 | TimelineEmpty + "暂未找到时间线信息" | — |
| 历史列表为空 | HistoryEmpty + "还没有搜索历史，快去搜索一个名词吧" | 搜索框引导 |
| 加载历史快照失败 | ErrorFallback + 重试 | 显示错误并重试 |

---

## 5. Tailwind CSS 设计令牌

### 5.1 CSS 自定义属性 (`globals.css`)

```css
@layer base {
  :root {
    /* 色彩 */
    --color-primary: #475569;
    --color-on-primary: #FFFFFF;
    --color-accent: #2563EB;
    --color-background: #F8FAFC;
    --color-foreground: #1E293B;
    --color-card: #FFFFFF;
    --color-card-foreground: #1E293B;
    --color-muted: #EAEFF3;
    --color-muted-foreground: #64748B;
    --color-border: #E2E8F0;
    --color-destructive: #DC2626;
    --color-success: #16A34A;
    --color-warning: #D97706;

    /* 圆角 */
    --radius-sm: 4px;
    --radius-md: 8px;
    --radius-lg: 12px;
    --radius-xl: 16px;

    /* 间距 */
    --space-graph-xl: 80px;
    --space-graph-lg: 48px;
    --space-graph-md: 24px;
    --space-graph-sm: 12px;
    --space-graph-xs: 8px;
  }

  .dark {
    --color-primary: #818CF8;
    --color-on-primary: #0F172A;
    --color-accent: #60A5FA;
    --color-background: #0A0A0F;
    --color-foreground: #F1F5F9;
    --color-card: #18181B;
    --color-card-foreground: #E2E8F0;
    --color-muted: #27272A;
    --color-muted-foreground: #A1A1AA;
    --color-border: #3F3F46;
    --color-destructive: #F87171;
    --color-success: #4ADE80;
    --color-warning: #FBBF24;
  }
}
```

### 5.2 tailwind.config.ts 扩展

```typescript
import type { Config } from 'tailwindcss'

export default {
  darkMode: 'class',  // class 策略，由 ThemeToggle 控制
  content: ['./src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      colors: {
        brand: {
          primary: 'var(--color-primary)',
          'on-primary': 'var(--color-on-primary)',
          accent: 'var(--color-accent)',
        },
        surface: {
          DEFAULT: 'var(--color-background)',
          foreground: 'var(--color-foreground)',
          card: 'var(--color-card)',
          'card-foreground': 'var(--color-card-foreground)',
          muted: 'var(--color-muted)',
          'muted-foreground': 'var(--color-muted-foreground)',
        },
        border: 'var(--color-border)',
        destructive: 'var(--color-destructive)',
        success: 'var(--color-success)',
        warning: 'var(--color-warning)',
      },
      borderRadius: {
        sm: 'var(--radius-sm)',
        md: 'var(--radius-md)',
        lg: 'var(--radius-lg)',
        xl: 'var(--radius-xl)',
      },
      spacing: {
        'graph-xl': 'var(--space-graph-xl)',
        'graph-lg': 'var(--space-graph-lg)',
        'graph-md': 'var(--space-graph-md)',
        'graph-sm': 'var(--space-graph-sm)',
        'graph-xs': 'var(--space-graph-xs)',
      },
      animation: {
        'node-enter': 'node-enter 300ms ease-out',
        'node-appear': 'node-appear 500ms ease-out',
        'pulse-subtle': 'pulse-subtle 1.5s ease-in-out infinite',
      },
      keyframes: {
        'node-enter': {
          '0%': { opacity: '0', transform: 'scale(0.5)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
        'node-appear': {
          '0%': { opacity: '0', transform: 'scale(0.8)', filter: 'brightness(0.5)' },
          '50%': { opacity: '0.8', transform: 'scale(1.1)' },
          '100%': { opacity: '1', transform: 'scale(1)', filter: 'brightness(1)' },
        },
        'pulse-subtle': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.7' },
        },
      },
    },
  },
  plugins: [],
} satisfies Config
```

---

## 6. 响应式断点

| 断点 | 宽度 | 布局变化 |
|------|------|----------|
| 默认（移动端） | < 640px | 全宽图谱，搜索栏紧凑，实体详情为底部滑入面板，时间轴可折叠 |
| sm | ≥ 640px | 侧边栏开始可拖动，搜索栏扩展 |
| md | ≥ 768px | 侧边栏固定 320px 宽，时间轴水平可滚动 |
| lg | ≥ 1024px | 侧边栏 360px，图谱区域最大，全功能控制栏 |
| xl | ≥ 1280px | 最大内容宽 1440px，居中布局 |

---

## 7. 无障碍 (Accessibility)

| 类别 | 要求 | 实现方式 |
|------|------|----------|
| 对比度 | WCAG AA (4.5:1) | 主文字 #1E293B 在 #F8FAFC 上 → 15.2:1 ✓ |
| 键盘导航 | Tab 顺序 = 视觉顺序 | 搜索 → 图谱 → 控制栏 → 时间轴 → 面板 |
| 焦点指示 | 可见的 focus ring | 使用 `ring-2 ring-[var(--color-ring)]` 统一样式 |
| 图谱交互 | 节点可通过键盘聚焦 | Tab 在节点间移动，Enter 选择，Esc 取消高亮 |
| 图谱语义 | 图谱区域 `role="img"` + aria-label | aria-label="名词 {term} 的关系图谱，共 {n} 个节点" |
| 屏幕阅读器 | 使用 aria-live 区域 | SSE 增量更新时 aria-live="polite" 播报 |
| 减少动效 | 尊重 prefers-reduced-motion | 检测 media query，禁用节点动画 |
| 动态字体 | 支持系统字体缩放 | 使用 rem 单位，避免 px 固定值 |
| 颜色非唯一标识 | 边类型使用图标 + 文字 | 图例中每种关系同时显示色块和文字标签 |
| 跳转链接 | Skip to main content | 页面顶部隐藏的跳转链接 |
| 搜索 | 搜索按钮 aria-label | `aria-label="搜索名词，当前关键词：{term}"` |
| 模态/面板 | 焦点陷捕获 + Escape 关闭 | Panel 组件内置焦点管理 |

---

## 8. 性能优化

| 策略 | 适用范围 | 实现 |
|------|----------|------|
| next/dynamic | GraphCanvas (D3.js) | SSR off, loading skeleton |
| next/image | Landing 页配图 | 自动 WebP + lazy load |
| 组件延迟加载 | GraphNodePanel, TimelineFull | Suspense + fallback |
| 虚拟化 | 大型关系列表 | 使用 IntersectionObserver |
| SSE 限流 | 增量更新频率 | 500ms 节流，批量合并节点 |
| 缓存 | 搜索历史、最近查看 | localStorage |
| 防抖 | 搜索输入 | 200ms useDebounce |
| 图谱查询限深 | 图谱展开 | 默认 depth=1，最多 depth=3 |
| 节点上限 | 单个图谱 | 软上限 200 节点，超出提示折叠 |
| CSS contain | 图谱区域 | `contain: layout style paint` |
| 图片优化 | 图谱节点头像 | 使用 next/image，占位 blurDataURL |

---

## 9. 组件实现顺序（优先级）

### Phase 1a — 骨架和基础（第 1-2 天）
1. [ ] `app/layout.tsx` — 全局布局（NavBar + 主题）
2. [ ] `NavBar.tsx` + `ThemeToggle.tsx` — 导航栏
3. [ ] `SearchBar.tsx` — 搜索输入框
4. [ ] `app/page.tsx` — Landing Page 静态版本
5. [ ] `globals.css` + `tailwind.config.ts` — 设计令牌
6. [ ] `empty-state` / `error-boundary` / `skeleton` — 基础 UI 组件

### Phase 1b — 搜索结果页（第 3-4 天）
7. [ ] `app/search/page.tsx` — 搜索结果页布局
8. [ ] `GraphCanvas.tsx` — D3.js 力导向图画布（基础版）
9. [ ] `api.ts` + `useGraph.ts` — 图谱 API 调用
10. [ ] `GraphSkeleton.tsx` — 图谱加载骨架屏
11. [ ] `GraphNode.tsx` + `GraphEdge.tsx` — 节点/边渲染
12. [ ] `GraphControls.tsx` — 缩放/重置控制

### Phase 1c — 交互和详情（第 5-6 天）
13. [ ] `GraphTooltip.tsx` — 节点悬浮提示
14. [ ] `GraphNodePanel.tsx` — 实体详情侧边栏
15. [ ] `ConfidenceBadge.tsx` + `SourceLink.tsx` — 置信度/来源
16. [ ] `TimelineCompact.tsx` — 紧凑时间轴（vis-timeline）
17. [ ] `useGraphSSE.ts` — SSE 增量订阅
18. [ ] `GraphLegend.tsx` — 关系图例

### Phase 1d — 打磨（第 7-8 天）
19. [ ] 图谱动画（节点冒出、布局过渡）
20. [ ] 深色模式完整适配
21. [ ] 移动端响应式：底部面板、可折叠时间轴
22. [ ] 空状态 & 错误状态全覆盖
23. [ ] 键盘导航 & 屏幕阅读器支持
24. [ ] 性能优化（虚拟化、防抖、缓存）

---

## 10. API 集成规范

### 10.1 API 调用封装 (`lib/api.ts`)

```typescript
// 所有 API 调用走统一客户端
// 字段：后端 snake_case → 前端保留 snake_case（不做转换）

export async function searchNouns(query: string): Promise<SearchResult[]> {
  const res = await fetch(`/api/nouns?q=${encodeURIComponent(query)}`)
  if (!res.ok) throw new ApiError(await res.json())
  return res.json()
}

export async function fetchGraph(nounId: string, depth = 1): Promise<GraphResponse> {
  const res = await fetch(`/api/nouns/${nounId}/graph?depth=${depth}`)
  if (!res.ok) throw new ApiError(await res.json())
  return res.json()
}

export async function fetchTimeline(nounId: string): Promise<TimelineResponse> {
  const res = await fetch(`/api/nouns/${nounId}/timeline`)
  if (!res.ok) throw new ApiError(await res.json())
  return res.json()
}
```

### 10.2 SSE 客户端 (`lib/sse-client.ts`)

```typescript
export class SSEClient {
  private eventSource: EventSource | null = null

  subscribe(
    nounId: string,
    onNodesAdded: (nodes: GraphNode[], edges: GraphEdge[]) => void,
    onError?: (error: Event) => void
  ) {
    this.eventSource = new EventSource(`/api/events/graph-updates?noun_id=${nounId}`)

    this.eventSource.addEventListener('nodes_added', (e) => {
      const data = JSON.parse(e.data)
      onNodesAdded(data.nodes, data.edges)
    })

    this.eventSource.onerror = (e) => {
      onError?.(e)
      // 自动重连（内置）
    }
  }

  unsubscribe() {
    this.eventSource?.close()
    this.eventSource = null
  }
}
```

### 10.3 类型定义 (`types/graph.ts`)

```typescript
export interface GraphNode {
  id: string
  label: string
  type: 'person' | 'entity' | 'event'
  confidence: number
  summary?: string
  image_url?: string
  year?: number  // 人物生卒/事件时间
}

export interface GraphEdge {
  source: string
  target: string
  type: string           // 关系类型 label
  confidence: number
  source_url: string     // 数据来源链接
  evidence?: string      // 证据摘要
}

export interface GraphResponse {
  center: string
  nodes: GraphNode[]
  edges: GraphEdge[]
  depth: number
  has_more: boolean
}
```

---

## 11. 暗色模式策略

- **默认偏好**：跟随系统 `prefers-color-scheme: dark`（图谱场景推荐深色）
- **切换控制**：NavBar 右上角太阳/月亮图标按钮
- **持久化**：localStorage 记住用户选择
- **实现**：Tailwind `darkMode: 'class'` + next-themes

### 明暗差异对照

| 元素 | Light | Dark |
|------|-------|------|
| 页面背景 | slate-50 `#F8FAFC` | neutral-950 `#0A0A0F` |
| 卡片面板 | white `#FFFFFF` | zinc-900 `#18181B` |
| 边框 | slate-200 `#E2E8F0` | zinc-700 `#3F3F46` |
| 主文字 | slate-900 `#1E293B` | slate-100 `#F1F5F9` |
| 次要文字 | slate-500 `#64748B` | zinc-400 `#A1A1AA` |
| 图谱背景 | slate-50 `#F8FAFC` | neutral-950 `#0A0A0F` |
| 节点阴影 | shadow-md | ring-1 border glow |
| 模态遮罩 | black/50 | black/70 |

---

## 12. 附录：技术依赖

```json
{
  "dependencies": {
    "next": "^16.2.12",
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "d3": "^7.9.0",
    "vis-timeline": "^7.7.0",
    "lucide-react": "^0.400.0",
    "clsx": "^2.1.0",
    "tailwind-merge": "^2.3.0"
  },
  "devDependencies": {
    "typescript": "^5.5.0",
    "tailwindcss": "^3.4.0",
    "@types/d3": "^7.4.0",
    "eslint": "^8.57.0",
    "eslint-config-next": "^16.2.12"
  }
}
```

---

> **总结：** 本设计以 **图谱沉浸 + 内容优先 + 渐进式信息披露** 为核心理念，为 Logos 构建了完整的前端设计系统。深色模式作为主要模式，最大化图谱可视化的信息密度和视觉专注力；最小主义的 UI 风格确保用户注意力集中于知识探索本身。
