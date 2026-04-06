# LLM Wiki — 个人知识库应用

基于 [llm-wiki 模式](./llm-wiki.md) 构建的个人 Wiki 应用。自动采集浏览记录、邮件、AI 对话历史，通过 LLM 增量编译成结构化知识库，支持本地搜索与溯源链接。

---

## 核心理念

不是 RAG（每次重新检索），而是**增量编译的持久 Wiki**：LLM 把你所有的信息源持续整合成结构化 Markdown 文件，知识随时间复利增长。搜索时直接查询已编译的 Wiki，同时可溯源回原始位置。

---

## 功能需求

### 1. 数据采集（连接器架构）

每个数据源是独立的连接器插件，统一接口，用户按需授权。


| 连接器                           | 授权方式                | 采集内容                   |
| ----------------------------- | ------------------- | ---------------------- |
| Gmail                         | OAuth2 (Google API) | 邮件全量，含 thread_id       |
| Google Docs                   | OAuth2 (Google API) | 文档正文，含 webViewLink     |
| Chrome 浏览记录                   | 本地文件权限              | URL、标题、访问时间，可选抓取正文     |
| ChatGPT                       | 浏览器扩展自动采集           | 对话历史，含 conversation_id |
| Claude.ai                     | 浏览器扩展自动采集           | 对话历史，含 conversation_id |
| （可扩展）Outlook / Notion / Slack | OAuth2 / API Token  | —                      |


**连接器统一接口：**

```python
class Connector:
    name: str
    auth_type: str  # "oauth2" | "local_db" | "extension"

    def authenticate(self) -> bool
    def fetch_new_items(self, since: datetime) -> list[Item]
    def test_connection(self) -> bool
```

**统一数据格式：**

```python
@dataclass
class Item:
    source: str       # "gmail" | "chatgpt" | "claude" | "chrome"
    type: str         # "email" | "conversation" | "visit"
    title: str
    body: str
    timestamp: datetime
    source_url: str   # 原始链接，用于溯源
    metadata: dict    # 来源特有字段（结构化提取结果）
```

---

### 2. 浏览器扩展（ChatGPT / Claude.ai 自动同步）

Chrome 扩展，注入 `chatgpt.com` 和 `claude.ai`，自动读取对话并同步到本地。

```
Chrome Extension (llm-wiki-sync)
├── background.js        ← Service Worker：去重、批处理、推送到本地 API
├── content/
│   ├── universal.js     ← 通用内容脚本：捕获页面访问 + AI 对话（ChatGPT/Claude.ai）
│   └── api-hook.js      ← 拦截 XHR/fetch，补充捕获动态加载的对话内容
└── popup/               ← 扩展弹窗：显示同步统计
```

工作流：

1. 用户打开 ChatGPT / Claude.ai
2. Content script 读取 IndexedDB 中的对话列表
3. 对比上次同步时间戳，找出新对话
4. `POST http://localhost:8765/sync` 发送到本地 app
5. 写入 `raw.db`

原始链接格式：

- ChatGPT：`https://chatgpt.com/c/{conversation_id}`
- Claude.ai：`https://claude.ai/chat/{conversation_id}`

---

### 3. 本地数据库（raw.db）

SQLite，存储所有采集到的原始数据。

```sql
CREATE TABLE items (
    id          TEXT PRIMARY KEY,
    source      TEXT,
    type        TEXT,
    title       TEXT,
    body        TEXT,
    timestamp   DATETIME,
    source_url  TEXT,     -- 原始链接（核心字段）
    metadata    JSON,     -- 结构化提取结果
    ingested    BOOLEAN DEFAULT FALSE
);
```

---

### 4. LLM 摄取引擎（手动触发）

用户点击「开始摄取」后执行，调用已配置的 LLM 处理未摄取内容。

**流程：**

1. 查询 `raw.db WHERE ingested = FALSE`
2. 按主题 / 时间聚类（相关内容合并处理）
3. 对每个 cluster：LLM 分析内容、识别 Wiki 主题、更新或新建 Markdown 页面
4. 标记 `ingested = TRUE`
5. 更新 `wiki/index.md` 和 `wiki/log.md`
6. 重建搜索索引
7. 返回摄取报告（新建 N 页，更新 M 页，跳过 K 条）

**LLM 提供商：可在设置页切换**

- Claude API（默认，`claude-sonnet-4-6`）
- OpenAI GPT-4o
- 本地 Ollama（例如本机已启动的 Qwen 系列模型）
- 统一接口，支持扩展

---

### 5. 结构化信息提取

摄取时 LLM 先对内容做**意图分类**，再按模板提取结构化字段，存入 `metadata`。


| 分类                                           | 提取字段                  |
| -------------------------------------------- | --------------------- |
| `application_phd` / `application_internship` | 姓名、学校、学位、研究方向、时长、联系方式 |
| `newsletter`                                 | 主题、要点列表               |
| `meeting_request`                            | 发起人、议题、时间             |
| `ai_conversation`                            | 讨论主题、结论、待办事项          |
| `article`                                    | 主题、要点列表               |
| `document`                                   | 主题、要点列表、文档类型          |
| `general`                                    | 通用摘要                  |


**示例——申请邮件提取结果：**

```json
{
  "type": "application_internship",
  "applicant": "吕晟",
  "institution": "港大",
  "degree": "PhD在读",
  "research_areas": ["多模态", "声学", "感知", "空间智能"],
  "duration": "6个月",
  "email": "lusheng@hku.hk",
  "source_url": "https://mail.google.com/mail/u/0/#inbox/18e4f..."
}
```

---

### 6. Wiki 层（Obsidian Vault）

LLM 生成和维护的 Markdown 文件，作为 Obsidian Vault 使用。

```
wiki/
├── index.md              ← 全局目录（LLM 维护）
├── log.md                ← 摄取日志（append-only）
├── topics/               ← 主题知识页（按 LLM 提取的 topic 命名）
└── people/               ← 人物 / 联系人页
    └── applicants.md     ← 申请者结构化列表
```

每个页面带 YAML frontmatter（供 Obsidian Dataview 查询）：

```yaml
---
title: PhD/实习申请者
sources: [gmail]
source_count: 8
last_updated: 2026-04-06
tags: [people, applications]
---
```

**溯源引用格式（每条知识点附来源）：**

```markdown
`useMemo` 应只用于真正大的计算场景。[^1][^2]

[^1]: [ChatGPT 对话 · 2026-04-05](https://chatgpt.com/c/67a3f2b1-...)
[^2]: [Chrome · React 官方文档](https://react.dev/reference/react/useMemo)
```

**申请者页面示例：**

```markdown
| 姓名 | 学校 | 类型 | 研究方向 | 时长 | 原始邮件 |
|------|------|------|----------|------|----------|
| 吕晟 | 港大 | PhD在读 | 多模态/声学/感知/空间智能 | 6个月 | [📧](gmail链接) |
```

---

### 7. 溯源链接（Source Attribution）

每条搜索结果必须返回原始来源链接。


| 来源        | 链接格式                                                  |
| --------- | ----------------------------------------------------- |
| Gmail     | `https://mail.google.com/mail/u/0/#inbox/{thread_id}` |
| ChatGPT   | `https://chatgpt.com/c/{conversation_id}`             |
| Claude.ai | `https://claude.ai/chat/{conversation_id}`            |
| Chrome    | 原始页面 URL                                              |


搜索索引同样存储 `source_url`，命中时直接返回，无需回查 raw.db。

---

### 8. 本地搜索

```
索引内容: wiki/*.md 文件（按 heading 分块，每块约 400 字）
方案: SQLite FTS5 全文检索，CJK 字符逐字分词（插入空格 tokenize）
查询: 自动 AND 语义，命中后交由 LLM 合成自然语言答案
```

**搜索结果示例——「申请 PhD 实习的同学」：**

```
找到 3 位申请者（来自 Gmail）

吕晟 · 港大 · PhD在读
多模态 / 声学 / 感知 / 空间智能 · 6个月
📧 lusheng@hku.hk  →  [原始邮件](gmail链接)

张三 · 清华 · 本科
CV / NLP · 3个月
📧 zhangsan@tsinghua.edu  →  [原始邮件](gmail链接)

来源: wiki/people/applicants.md · 最后更新 2026-04-06
```

---

### 9. Web UI 控制台

本地 Web 应用（FastAPI + React），用于管理连接器、触发摄取、执行搜索。

**页面：**


| 页面        | 功能                                         |
| --------- | ------------------------------------------ |
| Dashboard | 待摄取数量（按来源分类）、摄取历史记录、「开始摄取」按钮               |
| Search    | 自然语言搜索框、结构化结果卡片、溯源链接                       |
| Wiki      | 浏览 wiki 页面（内嵌或跳转 Obsidian）                 |
| Sources   | 连接器列表、授权状态、上次同步时间                          |
| Settings  | LLM 提供商切换（Claude / GPT-4o / Ollama）、API Key / 本地模型配置、过滤规则 |


---

## 架构总览

```
┌─────────────────────────────────────────────────────┐
│                   连接器层                            │
│  Gmail(OAuth2)  Chrome(本地文件)  ChatGPT/Claude(扩展)│
└──────────────────────┬──────────────────────────────┘
                       ↓ 统一 Item 格式
              raw.db (SQLite, 含 source_url)
                       ↓ 手动触发
         LLM 摄取引擎（分类 → 提取 → 聚类 → 写 Wiki）
                       ↓
         Obsidian Vault (wiki/ markdown，带溯源角标)
                       ↓
    本地搜索索引 (SQLite FTS5，含 source_url)
                       ↓
              Web UI 控制台（搜索 + 管理）
```

---

## 技术栈


| 层       | 方案                                                    |
| ------- | ----------------------------------------------------- |
| 后端      | Python 3.9+ + FastAPI                                 |
| 数据库     | SQLite（raw.db + search.db FTS5）                      |
| LLM     | Claude API (`claude-sonnet-4-6`) / OpenAI GPT-4o / 本地 Ollama（可切换） |
| Gmail   | `google-auth-oauthlib` + `googleapiclient`            |
| 正文抓取    | `trafilatura`                                         |
| 浏览器扩展   | Chrome Extension (Manifest V3)                        |
| 凭证存储    | macOS Keychain (`keyring`)                            |
| 前端      | React + TailwindCSS                                   |
| Wiki 前端 | Obsidian                                              |


---

## 开发阶段


| 阶段      | 内容                                                                  | 状态   |
| ------- | ------------------------------------------------------------------- | ---- |
| Phase 1 | FastAPI 后端 + raw.db + Gmail 连接器 + 结构化提取 + Web UI 骨架 + Onboarding 向导 | ✅ 完成 |
| Phase 2 | Chrome 历史连接器 + LLM 摄取引擎 + Wiki 写入 + Obsidian 集成                     | ✅ 完成 |
| Phase 3 | 浏览器扩展（ChatGPT + Claude.ai 自动同步）                                     | ✅ 完成 |
| Phase 4 | 本地搜索索引（FTS5 CJK）+ 溯源链接 + 搜索结果 UI                                    | ✅ 完成 |


---

## 安装与启动

### 前提条件

| 依赖 | 版本要求 | 说明 |
|------|---------|------|
| Python | 3.10+ | 3.9 可运行但会有 deprecation 警告 |
| Node.js | 18+ | 前端构建 |
| Chrome / Chromium | 任意 | 浏览器扩展 + Chrome 历史连接器 |
| Anthropic / OpenAI API Key | — | 使用云端模型时需要 |
| Ollama（可选） | 本地运行 | 使用本地模型时需要先启动 Ollama 服务并准备好模型 |

---

### 第一步：配置环境变量

```bash
cp .env.example .env
```

用编辑器打开 `.env`，填写以下字段：

```ini
# LLM 提供商，三选一
LLM_PROVIDER=claude          # 或 openai / ollama

# Anthropic Claude API Key（https://console.anthropic.com/）
# 注意：账户需要有余额，新账户默认为零
ANTHROPIC_API_KEY=sk-ant-api03-xxxxxxxx...

# OpenAI API Key（可选，与 Claude 二选一）
OPENAI_API_KEY=sk-...

# Ollama（本地模型，可选）
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen3.5-27b

# Google OAuth 凭据（Gmail 连接器必填，见下方步骤）
GOOGLE_CLIENT_ID=xxxxxxxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-xxxxxxxx
```

---

### 第二步：配置 Google OAuth（可选，Gmail / Google Docs 连接器需要）

> 如果不使用 Gmail 或 Google Docs，跳过此步骤。

**1. 创建 Google Cloud 项目**

1. 打开 [Google Cloud Console](https://console.cloud.google.com/)
2. 新建项目，或使用已有项目

**2. 启用 Gmail API / Google Docs API / Google Drive API**

1. 左侧菜单 → **API 和服务** → **库**
2. 搜索 `Gmail API`，点击启用
3. 搜索 `Google Docs API`，点击启用
4. 搜索 `Google Drive API`，点击启用

> **为什么 Google Docs 还需要 Google Drive API？**
>
> 当前项目的 `GoogleDocsConnector` 会先通过 **Google Drive API** 列出最近修改的 Google Docs 文档，再通过 **Google Docs API** 读取正文内容。
> 因此如果只启用了 Google Docs API、没有启用 Google Drive API，授权虽然会成功，但同步时仍会失败。

**3. 配置 OAuth 同意屏幕**

1. 左侧菜单 → **API 和服务** → **OAuth 同意屏幕**
2. 用户类型选 **外部**，填写应用名称（如 `llm wiki`）
3. 在 **测试用户** 部分，添加你自己的 Gmail 地址
4. 保存

**4. 创建 OAuth 凭据**

1. 左侧菜单 → **API 和服务** → **凭据** → **创建凭据** → **OAuth 2.0 客户端 ID**
2. 应用类型选 **Web 应用**
3. 在 **已获授权的重定向 URI** 中添加：
   ```
   http://localhost:8765/connectors/gmail/callback
   http://localhost:8765/connectors/googledocs/callback
   ```
4. 创建完成后，把 **客户端 ID** 和 **客户端密钥** 填入 `.env`

> 也可以下载 JSON 凭据文件，重命名为 `gmail_credentials.json` 放入 `data/` 目录，效果相同。

---

### 第三步：一键启动

```bash
chmod +x start.sh
./start.sh
```

脚本会自动完成：
- 创建 Python 虚拟环境（`.venv/`）并安装依赖
- 安装前端 npm 依赖
- 启动后端 API（`http://localhost:8765`）
- 启动前端开发服务器（`http://localhost:5173`）

首次启动会自动跳转到 **Onboarding 向导**，引导完成各数据源授权。

---

### 第四步：安装浏览器扩展（ChatGPT / Claude.ai 自动同步）

扩展负责实时捕获你在 ChatGPT 和 Claude.ai 上的对话，推送到本地服务器。

1. Chrome 地址栏输入 `chrome://extensions`
2. 开启右上角 **开发者模式**
3. 点击 **加载已解压的扩展程序**
4. 选择项目根目录下的 `extension/` 文件夹
5. 打开 ChatGPT 或 Claude.ai，扩展会在后台自动同步对话

---

### 第五步：连接数据源

打开 `http://localhost:5173` → **数据源** 页面：

| 数据源 | 操作 |
|--------|------|
| Gmail | 点击「授权」→ 弹出 Google OAuth 页面 → 登录并允许 |
| Google Docs | 点击「授权」→ 弹出 Google OAuth 页面 → 登录并允许 |
| Chrome 历史 | macOS 需在「系统设置 → 隐私与安全 → 完全磁盘访问」中授权终端/IDE |
| ChatGPT / Claude.ai | 安装扩展后，打开对应网站即自动激活 |

授权完成后，点击各数据源的 **「同步」** 按钮拉取数据。

> **注意**：Gmail 首次同步无时间限制，会拉取全部历史邮件，数量多时耗时较长。后续同步只拉增量，速度很快。
>
> **Google Docs 补充说明：**
> - 首次授权成功后，本地会生成 `data/googledocs_token.json`
> - Google Docs 与 Gmail 可以共用同一个 OAuth Client
> - 如果你刚启用了 `Google Drive API`，可能需要等待 2–5 分钟让配置生效后再重试同步

---

### 第六步：摄取与搜索

1. 打开 **Dashboard** 页面，查看待处理数量
2. 点击 **「开始摄取」**，LLM 将自动分类、提取、写入 wiki
3. 完成后进入 **搜索** 页面，用自然语言查询知识库

---

### 手动启动（不用 start.sh）

```bash
# 后端
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn backend.main:app --host 0.0.0.0 --port 8765 --reload

# 前端（另开终端）
cd frontend
npm install
npm run dev
```

---

### 常见问题

**Q: 启动后提示 "加载中..." 一直不消失**
检查后端是否正常运行：`curl http://localhost:8765/health` 应返回 `{"status":"ok"}`。

**Q: Gmail 授权报错 `redirect_uri_mismatch`**
Google Cloud Console 中的重定向 URI 必须与代码一致：`http://localhost:8765/connectors/gmail/callback` 或 `http://localhost:8765/connectors/googledocs/callback`，注意不能有末尾斜杠。

**Q: Google Docs 已授权成功，但同步时报 403 / `Google Drive API has not been used in project ... before or it is disabled`**
Google Docs 连接器依赖 **Google Drive API + Google Docs API**。请在 Google Cloud Console 中确认两个 API 都已启用；如果刚启用 `Google Drive API`，请等待几分钟让配置生效后再重试。

**Q: Google Docs 已授权成功，但还是读不到文档**
请优先检查：
1. 本地是否已生成 `data/googledocs_token.json`
2. Google Cloud 项目里是否同时启用了 `Google Docs API` 和 `Google Drive API`
3. 是否使用了与 `.env` 中 `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` 对应的同一个 Google Cloud 项目

**Q: Gmail 授权报错 `access_denied`（应用未验证）**
应用处于测试模式时，需要在 Google Cloud Console → OAuth 同意屏幕 → 测试用户中，手动添加你的 Gmail 地址。

**Q: LLM 分类报错 `credit balance too low`**
Anthropic 账户余额为零。前往 [console.anthropic.com/settings/billing](https://console.anthropic.com/settings/billing) 充值，或在设置页切换到有余额的 OpenAI key。

**Q: Chrome 历史连接器报错「未找到 History 文件」**
macOS 需要在「系统设置 → 隐私与安全 → 完全磁盘访问」中将运行本应用的终端（Terminal / iTerm2）加入允许列表。

**Q: Python 3.9 显示大量 FutureWarning**
不影响功能，但建议升级到 Python 3.10+：`brew install python@3.10`，然后重建虚拟环境。

---

## 项目结构

```
llm-wiki-app/
├── backend/
│   ├── main.py                  ← FastAPI 入口
│   ├── llm.py                   ← LLM 统一客户端（Claude / OpenAI / Ollama 可切换）
│   ├── config.py                ← 配置（读取 .env）
│   ├── connectors/
│   │   ├── base.py              ← Connector 抽象基类
│   │   ├── gmail.py             ← Gmail OAuth2 连接器
│   │   ├── googledocs.py        ← Google Docs 连接器
│   │   └── chrome.py            ← Chrome 历史连接器（Phase 2）
│   ├── ingest/
│   │   ├── engine.py            ← 摄取主流程
│   │   ├── classifier.py        ← LLM 分类 + 结构化提取
│   │   └── wiki_writer.py       ← 写 Markdown wiki 页面
│   ├── db/
│   │   └── raw.py               ← SQLite 操作（items + sync_state）
│   └── routers/
│       ├── connectors.py        ← 连接器 API + OAuth 回调 + 扩展接收端点
│       ├── ingest.py            ← 摄取触发 API
│       ├── search.py            ← 搜索 API（FTS + LLM 答案合成）
│       └── settings_router.py   ← 设置 API（支持持久化到 .env）
├── frontend/src/
│   ├── App.jsx                  ← 路由 + 首次启动检测
│   └── pages/
│       ├── Onboarding.jsx       ← 授权向导（首次启动自动显示）
│       ├── Dashboard.jsx        ← 待摄取统计 + 摄取触发
│       ├── Sources.jsx          ← 连接器授权管理
│       └── Settings.jsx         ← LLM 切换 + API Key
├── wiki/                        ← Obsidian Vault 根目录
├── data/                        ← raw.db + OAuth tokens（本地，不入 git）
├── .env.example                 ← 配置模板
└── start.sh                     ← 一键启动脚本
```

---

## 隐私说明

- 全部数据本地存储，不上传任何内容到第三方
- Gmail OAuth token 仅存本地 Keychain
- Chrome History 只读访问（复制到独立 SQLite，不修改原文件）
- LLM API 调用：仅发送待处理内容，不存储在 LLM 服务商侧
