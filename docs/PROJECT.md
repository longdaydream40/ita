# Idp Team Automation — 项目文档

> 版本：0.1.0 | 更新日期：2026-06-08

---

## 目录

1. [项目概述](#1-项目概述)
2. [技术栈与依赖](#2-技术栈与依赖)
3. [项目结构](#3-项目结构)
4. [核心模块详解](#4-核心模块详解)
5. [工作流程](#5-工作流程)
6. [安装与配置](#6-安装与配置)
7. [使用指南](#7-使用指南)
8. [产物与输出](#8-产物与输出)
9. [测试](#9-测试)
10. [安全设计](#10-安全设计)
11. [故障排查](#11-故障排查)
12. [作者与版权](#12-作者与版权)

---

## 1. 项目概述

**Idp Team Automation (ITA)** 是一个纯 Python 自动化工具，用于通过外部 IDP 服务批量创建 ChatGPT Team 成员账号，完成 Codex OAuth 授权获取 refresh token，并将结果推送至 Sub2API 管理平台。

### 1.1 核心特性

- **纯 HTTP 协议** — 不依赖 Selenium / Playwright / 浏览器自动化
- **单账号 & 批量模式** — 支持单次运行和多线程批量处理
- **交互式 TUI** — 终端仪表盘实时显示进度、成功/失败统计
- **自动重试** — 失败任务自动重试，可配置重试次数
- **日志脱敏** — 所有日志和产物文件自动脱敏敏感信息
- **健康检测** — 扫描 Sub2API 分组中的错误账号
- **重新授权** — 对错误账号重新执行 OAuth 流程并更新凭证

### 1.2 端到端流程

```
┌─────────────┐    ┌──────────────┐    ┌─────────────────┐    ┌──────────────┐    ┌────────────┐
│  IDP 生成    │───>│  SSO 会话    │───>│  Codex OAuth    │───>│  Token 交换  │───>│ Sub2API    │
│  账号        │    │  初始化      │    │  PKCE 授权      │    │              │    │ 推送       │
└─────────────┘    └──────────────┘    └─────────────────┘    └──────────────┘    └────────────┘
     Step 4             Step 5              Step 6-7             Step 8              Step 9
```

### 1.3 模块选择

TUI 启动后提供两个功能模块：

1. **注册账号** — 从零生成新账号，走完整 10 步流程
2. **重新补授权** — 从 Sub2API 读取错误账号，重新执行 OAuth 并更新凭证

---

## 2. 技术栈与依赖

### 2.1 运行环境

| 项目 | 要求 |
|---|---|
| Python | >= 3.10 |
| 操作系统 | Linux / macOS / Windows |
| 网络 | 需能访问 IDP、chatgpt.com、auth.openai.com |

### 2.2 依赖

| 包名 | 版本 | 用途 |
|---|---|---|
| `curl_cffi` | >= 0.7 | HTTP 客户端，支持 TLS 指纹模拟（`chrome110`），用于绕过 OpenAI 的 bot 检测 |

### 2.3 标准库使用

| 模块 | 用途 |
|---|---|
| `urllib.request` | IDP 和 Sub2API 的 HTTP 客户端 |
| `html.parser` | HTML 表单自动解析和填充 |
| `hashlib`, `base64`, `secrets` | PKCE / JWT 处理 |
| `threading`, `concurrent.futures` | 多线程批量执行 |
| `argparse` | CLI 参数解析 |
| `dataclasses` | 数据结构定义 |
| `pathlib`, `json` | 文件和数据处理 |

### 2.4 外部服务

| 服务 | 地址 | 用途 |
|---|---|---|
| IDP 服务 | `http://idp.fdvctte.info` | 账号生成、SSO 发起 |
| ChatGPT | `https://chatgpt.com` | NextAuth SSO |
| OpenAI Auth | `https://auth.openai.com` | OAuth 授权和 Token 交换 |
| Sub2API | 自部署 | 账号管理平台 |

---

## 3. 项目结构

```
ita/
├── .env.example                    # 环境变量模板
├── .gitignore                      # Git 忽略规则
├── README.md                       # 项目说明（中文）
├── pyproject.toml                  # Python 项目元数据
├── input.example.json              # JSON 输入格式示例
│
├── docs/                           # 文档目录
│   ├── API.md                      # 接口文档
│   ├── PROJECT.md                  # 项目文档（本文件）
│   └── assets/                     # 文档图片
│       ├── cain_qr.jpg
│       ├── pu_shengyou_qr.jpg
│       └── tui_running.png
│
├── lib/                            # 核心库
│   ├── __init__.py                 # 包初始化，导出公共模块
│   ├── batch_tui.py                # 批量多线程 TUI 仪表盘
│   ├── cli.py                      # 单账号 CLI 10 步编排
│   ├── codex_oauth.py              # PKCE/OAuth URL 生成、JWT 解析
│   ├── config.py                   # .env 加载、RuntimeConfig、参数合并
│   ├── errors.py                   # 异常层级定义
│   ├── idp_client.py               # IDP API HTTP 客户端
│   ├── logging_utils.py            # JSONL 日志 + 脱敏
│   ├── reauthorize_sub2api_errors.py  # 错误账号重新授权
│   ├── sso_http_flow.py            # 纯 HTTP SSO/OAuth 流程
│   ├── sub2api_export.py           # Sub2API 管理端 API 客户端
│   └── sub2api_health.py           # Sub2API 分组健康扫描
│
├── scripts/                        # 入口脚本（薄包装）
│   ├── run_batch_tui.py            # → lib.batch_tui.main()
│   ├── run_idp_codex.py            # → lib.cli.main()
│   ├── check_sub2api_group.py      # → lib.sub2api_health.main()
│   └── reauthorize_sub2api_errors.py  # → lib.reauthorize_sub2api_errors.main()
│
├── tests/                          # pytest 测试套件
│   ├── test_batch_tui_reauth.py
│   ├── test_codex_oauth.py
│   ├── test_idp_client.py
│   ├── test_independent_imports.py
│   ├── test_reauthorize_sub2api_errors.py
│   ├── test_sso_http_flow.py
│   ├── test_sub2api_export.py
│   └── test_sub2api_health.py
│
└── artifacts/                      # 运行产物（git-ignored）
    └── .gitkeep
```

---

## 4. 核心模块详解

### 4.1 `lib/config.py` — 配置管理

**职责：** 加载 `.env` 文件，合并 CLI 参数和环境变量，提供 `RuntimeConfig` 数据类。

**配置优先级：** CLI 参数 > 环境变量 > `.env` 文件默认值

**核心类：**

```python
@dataclass
class RuntimeConfig:
    # IDP 配置
    idp_base: str          # IDP 服务地址
    idp_token: str         # IDP 访问码
    idp_client_id: str     # OAuth client_id
    idp_channel_id: str    # 渠道 ID
    idp_domain: str        # 邮箱后缀

    # Codex OAuth 配置
    codex_client_id: str   # Codex OAuth client_id
    codex_redirect_uri: str  # 回调地址
    codex_scope: str       # 权限范围

    # Sub2API 配置
    sub2api_url: str       # 服务地址
    sub2api_email: str     # 管理员邮箱
    sub2api_password: str  # 管理员密码
    sub2api_group: str     # 分组 ID
    sub2api_model_whitelist: str  # 模型白名单
    sub2api_concurrency: int  # 并发额度
    sub2api_priority: int     # 优先级
    sub2api_rate_multiplier: float  # 倍率

    # 运行时配置
    artifact_dir: Path     # 产物输出目录
    timeout: float         # HTTP 超时秒数
    proxy: str             # HTTP 代理
    export_sub2api: bool   # 是否推送 Sub2API
```

**关键函数：**

- `load_dotenv()` — 解析 `.env` 文件，写入 `os.environ`
- `env_first(*names)` — 按优先级读取环境变量
- `RuntimeConfig.from_env_and_args(args)` — 从 argparse + env 构建配置
- `parse_int()`, `parse_float()`, `split_csv()` — 辅助解析函数

---

### 4.2 `lib/idp_client.py` — IDP API 客户端

**职责：** 与 IDP 服务通信，完成账号生成和 SSO 发起。

**核心类：**

```python
class IdpClient:
    def bootstrap(client_id) -> dict         # 获取渠道配置
    def me(token, page, page_size) -> dict   # 校验访问码、获取账号列表
    def generate_account(token, ...) -> GeneratedAccount  # 生成新账号
    def start_sso(token, account_id) -> str  # 发起 SSO，返回 start_url
```

**重试策略：** 4 次，5xx 自动重试，指数退避。

**日志事件：** `idp_request`, `idp_response`, `idp_error`

---

### 4.3 `lib/sso_http_flow.py` — SSO/OAuth HTTP 流程

**职责：** 驱动整个 SSO + OAuth 授权流程，纯 HTTP 实现。

**技术亮点：**

- **TLS 指纹模拟：** 使用 `curl_cffi` 的 `impersonate="chrome110"` 模拟 Chrome 浏览器
- **HTML 表单自动解析：** `_FormParser` 类解析 HTML，自动识别登录表单
- **表单字段启发式匹配：** 通过字段名判断 email/password/account_id 字段
- **多策略页面处理：** HTTP 重定向 → JSON continue URL → JS/Meta 重定向 → 表单提交 → workspace consent

**核心类：**

```python
class SSOHttpFlow:
    def prime_sso_session(start_url, account) -> str  # 初始化 SSO 会话
    def authorize_codex(oauth, account) -> dict        # 执行 Codex OAuth 授权
    def exchange_code(code, oauth) -> dict             # 交换 Token
    def run(start_url, oauth, account) -> dict         # 完整流程入口
```

**SSO 流程细节：**

1. 从 IDP `start_url` 获取 ChatGPT 登录页 URL
2. 加载登录页获取 NextAuth cookies
3. 调用 `/api/auth/csrf` 获取 CSRF token
4. 调用 `/api/auth/signin/openai` 获取 OpenAI 授权 URL
5. 驱动 OpenAI auth 页面：邮箱提交 → workspace consent → 表单自动填充
6. 跟踪重定向直到获得包含 `code` 和 `state` 的 callback URL
7. 用 authorization code 换取 token

**表单评分机制（`_form_score`）：**
- 含 email 字段 → +10
- 含 password 字段 → +10
- 含 account_id 字段 → +12
- action 含 login/signin/authorize/consent/sso → +3
- 有 submit 按钮 → +1

---

### 4.4 `lib/codex_oauth.py` — OAuth/PKCE 工具

**职责：** 生成 PKCE 授权 URL，解析回调 URL，解析 JWT token。

**核心函数：**

```python
def generate_oauth_start(redirect_uri, client_id, scope) -> OAuthStart
def parse_callback_url(callback_url, expected_state) -> dict
def jwt_claims_no_verify(token) -> dict          # 不验证签名的 JWT 解析
def token_config_from_response(token_resp) -> dict  # 从 token 响应提取完整配置
def public_token_result(token_config) -> dict       # 生成脱敏的公开结果
```

**OAuth 常量：**

| 常量 | 值 |
|---|---|
| `AUTH_URL` | `https://auth.openai.com/oauth/authorize` |
| `TOKEN_URL` | `https://auth.openai.com/oauth/token` |
| `DEFAULT_CLIENT_ID` | `app_EMoamEEZ73f0CkXaXp7hrann` |
| `DEFAULT_REDIRECT_URI` | `http://localhost:1455/auth/callback` |
| `DEFAULT_SCOPE` | `openid profile email offline_access` |

---

### 4.5 `lib/sub2api_export.py` — Sub2API 客户端

**职责：** 与 Sub2API 管理端通信，完成账号推送、更新、状态恢复。

**核心类：**

```python
class Sub2ApiExportProvider:
    def push(record: OAuthExportRecord) -> dict              # 创建新账号
    def update_account_credentials(account_id, record) -> dict  # 更新账号凭证
    def get_account(account_id) -> dict                      # 获取账号详情
    def clear_account_error(account_id) -> dict              # 清空错误状态
    def clear_account_rate_limit(account_id) -> dict         # 清空限流状态
    def enable_account_scheduling(account_id) -> dict        # 启用调度
    def restore_account_dispatch(account_id) -> dict         # 完整恢复操作
    def restore_account_dispatch_best_effort(account_id) -> dict  # 带重试的恢复
```

**写入节流机制：**
- 全局线程锁 `_SUB2API_WRITE_LOCK`
- POST/PUT/PATCH/DELETE 到 `/admin/` 路径时生效
- 最小间隔 180ms

**凭证构建（`build_credentials`）：**
- 从 `id_token` JWT 中提取 `chatgpt_account_id`, `chatgpt_user_id`, `plan_type`
- 自动设置 `model_mapping`（根据配置的白名单）
- 合并 `access_token`, `refresh_token`, `id_token`, `client_id`, `email`, `expires_at`

---

### 4.6 `lib/sub2api_health.py` — 分组健康扫描

**职责：** 扫描 Sub2API 指定分组中的错误账号。

**核心类：**

```python
class Sub2ApiHealthScanner:
    def list_accounts(group, page_size) -> list[dict]  # 分页获取全部账号
    def scan_group(group, page_size) -> dict            # 扫描并返回健康报告
```

**错误账号判断逻辑（`is_error_account`）：**
1. 存在 `error_message` / `last_error` / `error` → 错误
2. 状态文本含 `error`, `invalid`, `failed`, `inactive`, `disabled`, `paused`, `expired`, `unauthorized`, `401` → 错误
3. 状态文本不含 `active`, `ok`, `valid`, `healthy`, `normal`, `success` 且不是空 → 错误

**健康报告结构：**
```json
{
  "group": "5",
  "total": 88,
  "error_count": 23,
  "ok_count": 65,
  "status_counts": {"active": 65, "error": 23},
  "error_accounts": [
    {"id": 1, "name": "...", "email": "...", "status": "...", "error": "...", "group_ids": [5]}
  ]
}
```

---

### 4.7 `lib/reauthorize_sub2api_errors.py` — 错误账号重新授权

**职责：** 对 Sub2API 中的错误账号重新执行 OAuth 流程，更新凭证并恢复调度。

**流程：**
1. 扫描指定分组的错误账号
2. 对每个错误账号：
   - 从 Sub2API 获取账号详情（获取 email 等信息）
   - 重新执行完整的 IDP → SSO → OAuth 流程
   - 更新 Sub2API 账号凭证
   - 恢复调度状态（clear-error → clear-rate-limit → schedulable）

---

### 4.8 `lib/batch_tui.py` — 批量 TUI 仪表盘

**职责：** 多线程批量执行，提供实时 TUI 仪表盘。

**TUI 显示内容：**
- 模式、目标数量、线程数
- 成功/失败/运行中/等待中的计数
- 运行中任务表格（索引、状态、账号ID、邮箱、Sub2API ID、当前步骤）
- 最近成功/失败摘要
- 最近事件日志（最后 12 条）
- 每 250ms 自动刷新

**线程模型：**
- 使用 `concurrent.futures.ThreadPoolExecutor`
- 每个任务独立的 artifact 目录
- 失败自动重试（register 默认 5 次，reauth 默认 3 次）
- 最终输出统计摘要

---

### 4.9 `lib/cli.py` — 单账号 CLI 编排

**职责：** 编排单账号的 10 步完整流程。

**10 步流程：**

| 步骤 | 说明 | 输出 |
|---|---|---|
| 1 | 初始化运行环境 | 创建 artifact 目录 |
| 2 | 读取 IDP bootstrap | `bootstrap.json` |
| 3 | 校验 IDP 访问码 | `me.json` |
| 4 | 生成/复用账号 | `account.public.json` |
| 5 | 启动 SSO 会话 | `sso_start.public.json` |
| 6 | 生成 OAuth URL | `oauth_start.public.json` |
| 7 | 执行 SSO + OAuth | — |
| 8 | 获取 Token | `token.public.json` |
| 9 | 推送 Sub2API | `sub2api.public.json` |
| 10 | 写入最终结果 | `result.json` |

---

### 4.10 `lib/errors.py` — 异常体系

```python
IdpTeamAutomationError (base)
├── ConfigError        # 配置缺失或无效
├── IdpError           # IDP 请求/响应失败
├── OAuthFlowError     # SSO/OAuth 流程失败
└── Sub2ApiError       # Sub2API 请求/响应失败
```

**通用属性：**
- `stage: str` — 错误阶段标识
- `retryable: bool` — 是否可重试
- `data: dict` — 附加上下文（自动脱敏）

---

### 4.11 `lib/logging_utils.py` — 日志与脱敏

**`JsonlLogger`：** 追加写入 JSONL 格式日志文件。

**`redact()` 函数：** 递归脱敏。
- dict 中匹配敏感 key 的值替换为 `***REDACTED***`
- 字符串中的 `Bearer xxx`、长 base64 token 等模式被正则替换
- 递归处理嵌套 dict/list

---

## 5. 工作流程

### 5.1 注册账号流程

```
用户启动 TUI
  └─ 选择 "注册账号"
     └─ 输入数量、线程数
        └─ ThreadPoolExecutor 并发执行
           └─ 每个任务：
              1. IdpClient.bootstrap()     → 获取渠道配置
              2. IdpClient.me()            → 校验访问码
              3. IdpClient.generate_account() → 生成新账号
              4. IdpClient.start_sso()     → 获取 SSO start_url
              5. generate_oauth_start()    → 生成 PKCE 授权 URL
              6. SSOHttpFlow.run()         → 执行 SSO + OAuth
              7. Sub2ApiExportProvider.push() → 推送到 Sub2API
              8. 写入 result.json
```

### 5.2 重新授权流程

```
用户启动 TUI
  └─ 选择 "重新补授权"
     └─ 输入分组 ID、线程数
        └─ Sub2ApiHealthScanner.scan_group() → 获取错误账号列表
           └─ ThreadPoolExecutor 并发执行
              └─ 每个错误账号：
                 1. Sub2ApiExportProvider.get_account() → 获取账号详情
                 2. IdpClient.start_sso() → 重新发起 SSO
                 3. generate_oauth_start() → 生成新的 PKCE URL
                 4. SSOHttpFlow.run() → 执行 OAuth 流程
                 5. Sub2ApiExportProvider.update_account_credentials() → 更新凭证
                 6. Sub2ApiExportProvider.restore_account_dispatch() → 恢复调度
```

---

## 6. 安装与配置

### 6.1 安装

```bash
# 方式一：可编辑安装（推荐开发）
cd <项目目录>
python3 -m pip install -e .

# 方式二：仅安装依赖
python3 -m pip install 'curl_cffi>=0.7'
```

### 6.2 配置

```bash
cp .env.example .env
```

**必填配置：**

```env
IDP_TOKEN=your_idp_token_here
SUB2API_URL=https://sub2api.example.com
SUB2API_EMAIL=admin@example.com
SUB2API_PASSWORD=your_password
```

**可选配置：**

```env
# IDP 高级配置
IDP_BASE=http://idp.fdvctte.info    # 默认值
IDP_CLIENT_ID=                       # 自动选择
IDP_CHANNEL_ID=                      # 自动选择
IDP_DOMAIN=                          # 自动选择

# Codex OAuth 配置（通常使用默认值）
CODEX_CLIENT_ID=app_EMoamEEZ73f0CkXaXp7hrann
CODEX_REDIRECT_URI=http://localhost:1455/auth/callback
CODEX_SCOPE=openid profile email offline_access

# Sub2API 高级配置
SUB2API_GROUP=5
SUB2API_MODEL_WHITELIST=gpt-5.4,gpt-5.4-mini,gpt-5.5,gpt-image-2
SUB2API_CONCURRENCY=10
SUB2API_PRIORITY=1
SUB2API_RATE_MULTIPLIER=1

# HTTP 代理
HTTP_PROXY=http://127.0.0.1:7890
HTTPS_PROXY=http://127.0.0.1:7890

# 运行时
ARTIFACT_DIR=artifacts/idp_codex
REQUEST_TIMEOUT=30
```

---

## 7. 使用指南

### 7.1 统一 TUI（推荐）

```bash
# 交互式启动
python3 scripts/run_batch_tui.py

# 非交互注册
python3 scripts/run_batch_tui.py --mode register --count 10 --threads 3 --yes

# 指定重试次数
python3 scripts/run_batch_tui.py --mode register --count 10 --threads 3 --retries 5 --yes

# 不推送 Sub2API
python3 scripts/run_batch_tui.py --mode register --count 5 --threads 2 --no-sub2api --yes

# 非交互重新授权
python3 scripts/run_batch_tui.py --mode reauth --group 5 --threads 3 --yes

# 限制处理数量
python3 scripts/run_batch_tui.py --mode reauth --group 5 --threads 3 --limit 5 --yes

# 指定邮箱
python3 scripts/run_batch_tui.py --mode reauth --group 5 --threads 1 --email user@example.com --yes
```

### 7.2 单账号运行

```bash
# 生成新账号并推送
python3 scripts/run_idp_codex.py --timeout 60

# 复用已有 IDP 账号
python3 scripts/run_idp_codex.py --account-id 1638 --timeout 60

# 只获取 token，不推送
python3 scripts/run_idp_codex.py --timeout 60 --no-sub2api
```

### 7.3 Sub2API 健康检测

```bash
# 检测默认分组
python3 scripts/check_sub2api_group.py

# 指定分组
python3 scripts/check_sub2api_group.py --group 5

# 输出 JSON 并保存
python3 scripts/check_sub2api_group.py --group 5 --json --output artifacts/health.json
```

### 7.4 错误账号重新授权

```bash
# 干运行（不更新远端）
python3 scripts/reauthorize_sub2api_errors.py --group 5

# 实际执行
python3 scripts/reauthorize_sub2api_errors.py --group 5 --apply

# 限制数量
python3 scripts/reauthorize_sub2api_errors.py --group 5 --apply --limit 3

# 指定邮箱
python3 scripts/reauthorize_sub2api_errors.py --group 5 --apply --email user@example.com
```

---

## 8. 产物与输出

### 8.1 目录结构

**单账号产物：**
```
artifacts/idp_codex/
├── network.jsonl              # 所有 HTTP 请求/响应日志（脱敏）
├── bootstrap.json             # IDP bootstrap 响应
├── me.json                    # IDP me 响应
├── account.public.json        # 账号公开信息
├── sso_start.public.json      # SSO 启动信息
├── oauth_start.public.json    # OAuth 启动参数
├── token.private.json         # Token 完整数据（脱敏）
├── token.public.json          # Token 公开摘要
├── sub2api.public.json        # Sub2API 推送结果
└── result.json                # 最终结果
```

**批量产物：**
```
artifacts/batch_YYYYMMDD_HHMMSS/
├── summary.json               # 批次统计
├── task_0001/
│   ├── attempt_01/            # 第一次尝试
│   │   ├── network.jsonl
│   │   ├── result.json
│   │   └── ...
│   └── attempt_02/            # 第二次尝试（如果重试）
│       └── ...
└── task_0002/
    └── ...
```

**重新授权产物：**
```
artifacts/reauth_YYYYMMDD_HHMMSS/
├── reauth_summary.json        # 重新授权统计
├── account_000001/
│   └── attempt_01/
│       └── ...
└── account_000002/
    └── ...
```

### 8.2 关键产物说明

| 文件 | 内容 | 敏感度 |
|---|---|---|
| `network.jsonl` | 完整 HTTP 通信记录 | 已脱敏 |
| `token.private.json` | Token 完整数据 | 已脱敏 |
| `token.public.json` | 仅含布尔标志 | 安全 |
| `result.json` | 最终运行结果 | 已脱敏 |
| `summary.json` | 批次统计 | 安全 |

### 8.3 清理产物

```bash
# Linux/macOS
find artifacts -mindepth 1 ! -name .gitkeep -delete

# Windows PowerShell
Get-ChildItem -Path artifacts -Recurse -Exclude .gitkeep | Remove-Item -Recurse -Force
```

---

## 9. 测试

### 9.1 运行测试

```bash
python3 -m pytest -q
```

### 9.2 测试文件

| 文件 | 覆盖模块 |
|---|---|
| `test_codex_oauth.py` | `lib.codex_oauth` — PKCE 生成、JWT 解析、URL 解析 |
| `test_idp_client.py` | `lib.idp_client` — IDP 客户端、重试逻辑 |
| `test_sso_http_flow.py` | `lib.sso_http_flow` — 表单解析、SSO 流程 |
| `test_sub2api_export.py` | `lib.sub2api_export` — Sub2API 客户端、凭证构建 |
| `test_sub2api_health.py` | `lib.sub2api_health` — 健康扫描、错误判断 |
| `test_reauthorize_sub2api_errors.py` | `lib.reauthorize_sub2api_errors` — 重新授权 |
| `test_batch_tui_reauth.py` | `lib.batch_tui` — TUI 重新授权 |
| `test_independent_imports.py` | 各模块独立导入 |

### 9.3 测试配置

`pyproject.toml` 中的 pytest 配置：
```toml
[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

---

## 10. 安全设计

### 10.1 凭证保护

- **`.env` 文件** — 不提交到仓库（`.gitignore`）
- **日志脱敏** — `redact()` 函数自动替换敏感字段和模式
- **产物脱敏** — `token.private.json` 虽然名字含 "private"，但内容已脱敏
- **公开产物** — `token.public.json` 仅含布尔标志，不含实际 token

### 10.2 敏感字段识别

**自动脱敏的字段名：**
`authorization`, `access_token`, `refresh_token`, `id_token`, `token`, `password`, `secret`, `cookie`, `code`, `otp`

**自动脱敏的字符串模式：**
- `Bearer xxx` → `Bearer ***REDACTED***`
- 长 base64 编码字符串
- JWT token 格式

### 10.3 TLS 指纹模拟

使用 `curl_cffi` 的 `impersonate="chrome110"` 模拟 Chrome 浏览器的 TLS 指纹，避免被 OpenAI 的 bot 检测拦截。

---

## 11. 故障排查

### 11.1 常见错误

| 错误信息 | 原因 | 解决方案 |
|---|---|---|
| `缺少 IDP 访问码` | `IDP_TOKEN` 未配置 | 编辑 `.env` 填写 `IDP_TOKEN` |
| `缺少 Sub2API 配置` | Sub2API 相关变量未配置 | 填写 `SUB2API_URL`, `SUB2API_EMAIL`, `SUB2API_PASSWORD` |
| `IDP 请求失败` | IDP 服务不可用或 token 无效 | 检查 IDP 服务状态和 token |
| `ChatGPT NextAuth 未返回 csrfToken` | ChatGPT 服务异常或被限制 | 稍后重试，检查网络 |
| `纯 HTTP 流程遇到无法自动处理的页面` | OpenAI 登录流程变更 | 查看 `unhandled_*.html` 分析页面 |
| `OAuth token 响应缺少 refresh_token` | OAuth 授权失败 | 检查 scope 是否包含 `offline_access` |
| `Sub2API 登录成功但未返回 access_token` | Sub2API 版本不兼容 | 检查 Sub2API 服务版本 |
| `缺少 curl_cffi 依赖` | 未安装依赖 | `pip install 'curl_cffi>=0.7'` |

### 11.2 日志分析

```bash
# 查看网络日志
cat artifacts/idp_codex/network.jsonl | python3 -m json.tool

# 查看特定事件
grep '"idp_error"' artifacts/idp_codex/network.jsonl
grep '"sub2api_error"' artifacts/idp_codex/network.jsonl
grep '"oauth_http_error"' artifacts/idp_codex/network.jsonl
```

### 11.3 调试技巧

- 增大 `REQUEST_TIMEOUT`（如 60 秒）
- 使用 `--proxy` 配合抓包工具分析 HTTP 流量
- 查看 `artifacts/` 目录下的 HTML 文件（`unhandled_*.html`）
- 使用 `--no-sub2api` 只测试 OAuth 流程

---

## 12. 作者与版权

| 角色 | 作者 |
|---|---|
| iDP 协议作者 | @该隐 |
| 注册机作者 | @朴圣佑 |

**版权要求：** 二开请保留版权信息。

**联系方式：**

| IDP / API 点数购买 | 注册机相关 |
|---|---|
| 请联系 @该隐 | 请联系 @朴圣佑 |
| <img src="assets/cain_qr.jpg" width="200"> | <img src="assets/pu_shengyou_qr.jpg" width="200"> |
