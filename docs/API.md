# Idp Team Automation — 接口文档

> 版本：0.1.0 | 更新日期：2026-06-08

本文档记录 ITA 项目对接的全部外部 HTTP API、请求/响应格式、认证方式及错误处理策略。

---

## 目录

1. [IDP 服务 API](#1-idp-服务-api)
2. [ChatGPT / OpenAI Auth API](#2-chatgpt--openai-auth-api)
3. [Codex OAuth API](#3-codex-oauth-api)
4. [Sub2API 管理端 API](#4-sub2api-管理端-api)
5. [内部数据结构](#5-内部数据结构)
6. [错误处理与重试策略](#6-错误处理与重试策略)
7. [日志与脱敏](#7-日志与脱敏)

---

## 1. IDP 服务 API

**基地址：** `http://idp.fdvctte.info`（可通过 `IDP_BASE` 配置）

**通用请求头：**

| Header | 值 |
|---|---|
| `Accept` | `application/json, text/plain, */*` |
| `Content-Type` | `application/json`（POST 请求） |
| `User-Agent` | `Mozilla/5.0 IdpTeamAutomation/0.1` |

**认证方式：** 请求体中携带 `token` 字段（即 `IDP_TOKEN`），非 Bearer Header。

**重试策略：** 最多 4 次尝试，5xx 错误自动重试，指数退避 `min(3.0, 0.5 * attempt)` 秒。

**客户端实现：** `lib/idp_client.py` → `IdpClient` 类

---

### 1.1 GET /api/user/bootstrap

获取 IDP 服务的渠道和域名配置。

**请求参数：**

| 参数 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `client_id` | Query | string | 否 | OAuth client_id，不填返回全部 |

**响应示例：**

```json
{
  "channels": [
    {"id": 1, "name": "default"}
  ],
  "domains_by_channel": {
    "1": ["example.com", "test.org"]
  }
}
```

**错误场景：**
- 返回非 dict → 抛出 `IdpError("IDP bootstrap 返回格式异常")`

---

### 1.2 POST /api/user/me

校验 IDP 访问码并获取当前用户信息及已有账号列表。

**请求体：**

```json
{
  "token": "string (必填)",
  "page": 1,
  "page_size": 20,
  "client_id": "string (可选)",
  "q": "string (可选, 搜索关键词)"
}
```

**响应示例：**

```json
{
  "customer": {
    "id": 123,
    "email": "admin@example.com"
  },
  "accounts": {
    "items": [
      {
        "id": 1638,
        "email": "user@example.com",
        "password": "***",
        "name": "John Doe",
        "given_name": "John",
        "family_name": "Doe",
        "channel_id": "1",
        "channel_name": "default"
      }
    ],
    "total": 50,
    "page": 1
  }
}
```

**错误场景：**
- 返回非 dict → 抛出 `IdpError("IDP me 返回格式异常")`

---

### 1.3 POST /api/user/generate

生成一个新的 IDP 账号（消耗 API 点数）。

**请求体：**

```json
{
  "token": "string (必填)",
  "channel_id": 0,
  "client_id": "string (可选)",
  "domain": "string (可选, 邮箱后缀)",
  "email": "string (可选, 指定邮箱或前缀)",
  "given_name": "string (可选, 名)",
  "family_name": "string (可选, 姓)"
}
```

**响应示例：**

```json
{
  "account": {
    "id": 1638,
    "email": "generated_user@example.com",
    "password": "plaintext_password",
    "name": "John Doe",
    "given_name": "John",
    "family_name": "Doe",
    "channel_id": "1",
    "channel_name": "default"
  }
}
```

**响应字段解析（`GeneratedAccount` 数据类）：**

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | int | IDP 账号 ID，用于后续 `start-sso` |
| `email` | string | 生成的邮箱地址（必有） |
| `password` | string | 明文密码（可能为空） |
| `name` | string | 全名 |
| `given_name` | string | 名 |
| `family_name` | string | 姓 |
| `channel_id` | string | 渠道 ID |
| `channel_name` | string | 渠道名称 |

**错误场景：**
- `account` 中无 `email` → `IdpError("IDP 生成账号未返回 email")`
- 返回格式异常 → `IdpError("IDP 生成账号返回格式异常")`

---

### 1.4 POST /api/user/start-sso

为指定 IDP 账号发起 SSO 登录流程，返回 ChatGPT SSO 起始 URL。

**请求体：**

```json
{
  "token": "string (必填)",
  "account_id": 1638
}
```

**响应示例：**

```json
{
  "start_url": "https://chatgpt.com/api/auth/signin/openai?connection=conn_xxx&..."
}
```

**错误场景：**
- 无 `start_url` → `IdpError("IDP start-sso 未返回 start_url")`

---

## 2. ChatGPT / OpenAI Auth API

以下端点用于 SSO 会话初始化（`lib/sso_http_flow.py` → `SSOHttpFlow` 类）。

**HTTP 客户端：** `curl_cffi`，使用 `impersonate="chrome110"` 模拟 Chrome TLS 指纹。

**重试策略：** 最多 3 次，指数退避 `min(3.0, 0.5 * attempt)` 秒。

---

### 2.1 GET https://chatgpt.com/api/auth/csrf

获取 NextAuth CSRF Token。

**响应：**

```json
{
  "csrfToken": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
}
```

**错误场景：**
- 无 `csrfToken` → `OAuthFlowError("ChatGPT NextAuth 未返回 csrfToken")`

---

### 2.2 POST https://chatgpt.com/api/auth/signin/openai

初始化 OpenAI SSO Provider 登录。

**Query 参数：**

| 参数 | 说明 |
|---|---|
| `connection` | IDP connection 标识，从 `start_url` 解析 |
| `connection_provider` | `"2"`（conn_ 前缀）或 `"1"` |

**请求体（form-encoded）：**

| 字段 | 说明 |
|---|---|
| `csrfToken` | 从 2.1 获取 |
| `callbackUrl` | 固定 `"/"` |
| `json` | 固定 `"true"` |

**响应：**

```json
{
  "url": "https://auth.openai.com/..."
}
```

**错误场景：**
- 无 `url` → `OAuthFlowError("ChatGPT NextAuth signin 未返回授权 URL")`

---

### 2.3 POST https://auth.openai.com/api/accounts/authorize/continue

OpenAI 登录页面的邮箱/用户名提交步骤。

**请求头：**

| Header | 值 |
|---|---|
| `accept` | `application/json` |
| `content-type` | `application/json` |
| `origin` | `https://auth.openai.com` |
| `referer` | `https://auth.openai.com/log-in-or-create-account` |

**请求体：**

```json
{
  "username": {
    "value": "user@example.com",
    "kind": "email"
  },
  "screen_hint": "login_or_signup"
}
```

**响应：** JSON 包含 `continue_url` / `redirect_url` / `url` 等跳转字段。

---

### 2.4 POST https://auth.openai.com/api/accounts/workspace/select

工作区同意/选择步骤（出现在 workspace consent 页面）。

**请求头：**

| Header | 值 |
|---|---|
| `accept` | `application/json` |
| `content-type` | `application/json` |
| `origin` | `https://auth.openai.com` |

**请求体：**

```json
{
  "workspace_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
}
```

**workspace_id 提取逻辑：** 从 HTML 页面中正则匹配以下模式：
- `\"workspaces\",[\d+],{...},\"id\",\"<UUID>\"`
- `\"id\",\"<UUID>\",\"name\",\"kind\",\"personal`
- `"workspace_id": "<UUID>"`

---

## 3. Codex OAuth API

**实现位置：** `lib/codex_oauth.py`

---

### 3.1 GET https://auth.openai.com/oauth/authorize

OAuth 2.0 授权端点（Authorization Code + PKCE）。

**请求参数（Query）：**

| 参数 | 说明 | 示例值 |
|---|---|---|
| `client_id` | OAuth 客户端 ID | `app_EMoamEEZ73f0CkXaXp7hrann` |
| `response_type` | 固定 | `code` |
| `redirect_uri` | 回调地址 | `http://localhost:1455/auth/callback` |
| `scope` | 权限范围 | `openid profile email offline_access` |
| `state` | 防 CSRF 随机字符串 | `secrets.token_urlsafe(16)` |
| `code_challenge` | SHA256(code_verifier) 的 Base64URL | S256 方法 |
| `code_challenge_method` | 固定 | `S256` |
| `id_token_add_organizations` | 固定 | `true` |
| `codex_cli_simplified_flow` | 固定 | `true` |

**PKCE 生成流程：**
1. `state = secrets.token_urlsafe(16)`
2. `code_verifier = secrets.token_urlsafe(64)`
3. `code_challenge = base64url(sha256(code_verifier)).rstrip("=")`

---

### 3.2 POST https://auth.openai.com/oauth/token

OAuth Token 交换端点。

**请求体（form-encoded）：**

| 字段 | 说明 |
|---|---|
| `grant_type` | `authorization_code` |
| `client_id` | OAuth 客户端 ID |
| `code` | 授权码（从回调 URL 解析） |
| `redirect_uri` | 回调地址 |
| `code_verifier` | PKCE code_verifier |

**响应示例：**

```json
{
  "access_token": "eyJ...",
  "refresh_token": "v1.Mj...",
  "id_token": "eyJ...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "scope": "openid profile email offline_access"
}
```

**Token 解析（`token_config_from_response`）：**

从 `id_token` 的 JWT payload 中提取：

| 提取路径 | 输出字段 |
|---|---|
| `claims.email` | `email` |
| `claims["https://api.openai.com/auth"].chatgpt_account_id` | `account_id` |
| `claims["https://api.openai.com/auth"].user_id` | `user_id` |
| `claims["https://api.openai.com/auth"].chatgpt_plan_type` | `plan_type` |

---

## 4. Sub2API 管理端 API

**基地址：** `{SUB2API_URL}/api/v1`

**认证方式：** Bearer Token（通过 `/auth/login` 获取）

**通用请求头：**

| Header | 值 |
|---|---|
| `Accept` | `application/json, text/plain, */*` |
| `Content-Type` | `application/json` |
| `User-Agent` | `Mozilla/5.0 IdpTeamAutomation/0.1` |
| `Origin` | Sub2API 基地址 |
| `Referer` | Sub2API 基地址 + `/` |

**重试策略：** 最多 8 次尝试：
- 429 → 尊重 `Retry-After`，否则 `min(30, 1.5 * attempt + random(0.2, 1.2))` 秒
- 5xx → `min(10, 0.8 * attempt + random(0.1, 0.8))` 秒
- 网络错误（SSL/超时/连接重置）→ `min(5, 0.5 * attempt)` 秒

**写入节流：** 全局锁 + 180ms 最小间隔（仅 POST/PUT/PATCH/DELETE 到 `/admin/` 路径生效）

**客户端实现：** `lib/sub2api_export.py` → `Sub2ApiExportProvider` 类

---

### 4.1 POST /api/v1/auth/login

管理员登录，获取 Bearer Token。

**请求体：**

```json
{
  "email": "admin@example.com",
  "password": "password"
}
```

**响应：**

```json
{
  "access_token": "eyJ..."
}
```

**Token 提取逻辑：** 依次尝试 `access_token` → `token` → `accessToken`。

**注意：** 每次 Sub2API 操作都会重新登录，不缓存 Token。

---

### 4.2 GET /api/v1/admin/accounts

获取账号列表（分页）。

**请求头：** `Authorization: Bearer {token}`

**Query 参数：**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `page` | int | 否 | 页码，默认 1 |
| `page_size` | int | 否 | 每页数量，默认 100，最大 500 |
| `group` | string | 否 | 分组 ID 过滤 |

**响应：**

```json
{
  "items": [
    {
      "id": 1,
      "name": "user@example.com",
      "status": "active",
      "error_message": "",
      "credentials": {
        "email": "user@example.com",
        "access_token": "...",
        "refresh_token": "...",
        "expires_at": 1720000000
      },
      "account_groups": [
        {"group_id": 5}
      ],
      "extra": {},
      "concurrency": 10,
      "priority": 1,
      "schedulable": true
    }
  ],
  "total": 88,
  "pages": 9
}
```

**分页遍历逻辑：**
1. 按 `pages` 判断是否到最后一页
2. 按 `total` 判断是否已获取全部
3. 当返回的 `items` 数量 < `page_size` 时停止

---

### 4.3 POST /api/v1/admin/accounts

创建新账号（推送 OAuth 记录）。

**请求头：** `Authorization: Bearer {token}`

**请求体（`build_account_payload` 构建）：**

```json
{
  "name": "user@example.com",
  "platform": "openai",
  "type": "oauth",
  "credentials": {
    "access_token": "eyJ...",
    "refresh_token": "v1.Mj...",
    "id_token": "eyJ...",
    "client_id": "app_EMoamEEZ73f0CkXaXp7hrann",
    "email": "user@example.com",
    "chatgpt_account_id": "account_xxx",
    "chatgpt_user_id": "user_xxx",
    "plan_type": "team",
    "expires_at": 1720000000,
    "model_mapping": {
      "gpt-5.4": "gpt-5.4",
      "gpt-5.4-mini": "gpt-5.4-mini",
      "gpt-5.5": "gpt-5.5",
      "gpt-image-2": "gpt-image-2"
    }
  },
  "extra": {
    "idp_team_automation_managed": true,
    "idp_team_automation_source": "idp_codex",
    "idp_team_automation_codex_managed": true,
    "idp_team_automation_codex_source": "idp_team_automation",
    "idp_team_automation_email": "user@example.com",
    "email": "user@example.com"
  },
  "concurrency": 10,
  "priority": 1,
  "rate_multiplier": 1.0,
  "auto_pause_on_expired": true,
  "group_ids": [5]
}
```

**响应：**

```json
{
  "id": 42,
  "name": "user@example.com",
  "platform": "openai",
  "status": "active"
}
```

---

### 4.4 GET /api/v1/admin/accounts/{id}

获取单个账号详情。

**请求头：** `Authorization: Bearer {token}`

**响应：** 同 4.2 中单个 item 的结构。

---

### 4.5 PUT /api/v1/admin/accounts/{id}

更新账号（用于重新授权场景）。

**请求头：** `Authorization: Bearer {token}`

**请求体：** 与 4.3 相同结构，额外设置：
- `status`: `"active"`
- `error_message`: `""`
- `schedulable`: `true`
- `temp_unschedulable_reason`: `""`
- `temp_unschedulable_until`: `null`
- `overload_until`: `null`
- `rate_limited_at`: `null`
- `rate_limit_reset_at`: `null`

**保留策略：** 从现有账号数据中保留 `name`, `platform`, `type`, `concurrency`, `priority`, `rate_multiplier`, `auto_pause_on_expired`, `group_ids` 以及非 legacy 的 `extra` 字段。

---

### 4.6 POST /api/v1/admin/accounts/{id}/clear-error

清空账号错误状态。

**请求头：** `Authorization: Bearer {token}`

**请求体：** `{}`

---

### 4.7 POST /api/v1/admin/accounts/{id}/clear-rate-limit

清空账号限流状态。

**请求头：** `Authorization: Bearer {token}`

**请求体：** `{}`

---

### 4.8 POST /api/v1/admin/accounts/{id}/schedulable

启用账号调度。

**请求头：** `Authorization: Bearer {token}`

**请求体：** `{}`

---

### 4.9 恢复调度组合操作

`restore_account_dispatch(account_id)` 依次调用：
1. `clear-error` → 清空错误
2. `clear-rate-limit` → 清空限流
3. `schedulable` → 启用调度

`restore_account_dispatch_best_effort(account_id, attempts=4)` 在上述基础上增加：
- 最多重试 4 次
- 每次调用后检查 `schedulable=true` 或账号状态看起来已恢复
- 失败时通过 `get_account` 检查当前状态

---

## 5. 内部数据结构

### 5.1 OAuthExportRecord

Sub2API 导出使用的账号记录：

```python
@dataclass(frozen=True)
class OAuthExportRecord:
    account_id: str          # IDP 账号 ID 或 email
    email: str               # 邮箱地址
    secret: dict[str, Any]   # 包含 access_token, refresh_token, id_token, client_id, expired, account_id, user_id
    metadata: dict[str, Any] # 包含 email, source, generated_account_id 等
```

### 5.2 OAuthStart

OAuth PKCE 启动参数：

```python
@dataclass(frozen=True)
class OAuthStart:
    auth_url: str        # 完整的授权 URL
    state: str           # 防 CSRF state 参数
    code_verifier: str   # PKCE code_verifier
    redirect_uri: str    # 回调地址
    client_id: str       # OAuth 客户端 ID
    scope: str           # 权限范围
```

### 5.3 Sub2ApiConfig

Sub2API 连接配置：

```python
@dataclass(frozen=True)
class Sub2ApiConfig:
    url: str               # Sub2API 服务地址
    email: str             # 管理员邮箱
    password: str          # 管理员密码
    group: str = ""        # 分组 ID（逗号分隔）
    model_whitelist: str = ""  # 模型白名单（逗号分隔）
    concurrency: int = 10      # 并发额度
    priority: int = 1          # 优先级
    rate_multiplier: float = 1.0  # 倍率
```

### 5.4 GeneratedAccount

IDP 生成的账号数据：

```python
@dataclass(frozen=True)
class GeneratedAccount:
    id: int               # IDP 账号 ID
    email: str            # 邮箱
    password: str         # 明文密码
    name: str = ""        # 全名
    given_name: str = ""  # 名
    family_name: str = "" # 姓
    channel_id: str = ""  # 渠道 ID
    channel_name: str = "" # 渠道名称
    raw: dict | None      # 原始响应数据
```

### 5.5 AccountHealth

Sub2API 账号健康状态：

```python
@dataclass(frozen=True)
class AccountHealth:
    id: int           # Sub2API 账号 ID
    name: str         # 账号名称
    email: str        # 邮箱
    status: str       # 状态文本
    error: str        # 错误信息
    group_ids: list[int]  # 所属分组
```

---

## 6. 错误处理与重试策略

### 6.1 异常层级

```
IdpTeamAutomationError (base)
├── ConfigError        # 配置缺失或无效
├── IdpError           # IDP 请求/响应失败
├── OAuthFlowError     # SSO/OAuth 流程失败
└── Sub2ApiError       # Sub2API 请求/响应失败
```

**通用属性：**

| 属性 | 类型 | 说明 |
|---|---|---|
| `stage` | str | 错误发生的阶段标识 |
| `retryable` | bool | 是否可重试 |
| `data` | dict | 附加上下文数据（自动脱敏） |

### 6.2 各组件重试参数

| 组件 | 最大尝试 | 退避策略 | 可重试条件 |
|---|---|---|---|
| IDP Client | 4 | `min(3, 0.5 * attempt)` | 5xx / 网络异常 |
| SSO HTTP Flow | 3 | `min(3, 0.5 * attempt)` | SSL/超时/连接重置/空回复 |
| Sub2API Client | 8 | 429: 尊重 Retry-After 或 `min(30, 1.5*a + rand)`；5xx: `min(10, 0.8*a + rand)`；网络: `min(5, 0.5*a)` | 429 / 5xx / SSL / 超时 / 连接重置 |
| Batch TUI (register) | 5 (可配置) | 同上各组件内部重试 | 组件抛出 `retryable=True` |
| Batch TUI (reauth) | 3 (可配置) | 同上 | 组件抛出 `retryable=True` |

### 6.3 网络瞬态错误识别

以下错误被识别为瞬态（可重试）：
- SSL: `ssl.SSLEOFError`, `ssl.SSLError`
- 超时: `TimeoutError`, `socket.timeout`
- 连接: `ConnectionResetError`, `ConnectionAbortedError`
- curl 特定: `curl: (52)` (empty reply)
- 文本匹配: `"timed out"`, `"connection reset"`, `"temporarily unavailable"`

---

## 7. 日志与脱敏

### 7.1 JSONL 日志

**实现：** `lib/logging_utils.py` → `JsonlLogger`

日志文件：`{artifact_dir}/network.jsonl`

每行格式：
```json
{"ts": "2026-06-08T12:00:00Z", "event": "idp_request", "data": {...}}
```

**事件类型：**

| 事件 | 说明 |
|---|---|
| `run_start` | 单账号运行开始 |
| `run_success` | 单账号运行成功 |
| `idp_request` | IDP API 请求 |
| `idp_response` | IDP API 响应 |
| `idp_error` | IDP API 错误 |
| `oauth_http_request` | OAuth HTTP 请求 |
| `oauth_http_response` | OAuth HTTP 响应 |
| `oauth_http_error` | OAuth HTTP 错误 |
| `sub2api_request` | Sub2API 请求 |
| `sub2api_response` | Sub2API 响应 |
| `sub2api_error` | Sub2API 错误 |
| `sub2api_retry` | Sub2API 重试 |

### 7.2 脱敏规则

**敏感字段名匹配（自动替换为 `***REDACTED***`）：**

`authorization`, `access_token`, `refresh_token`, `id_token`, `token`, `password`, `secret`, `cookie`, `code`, `otp`

**敏感字符串模式（正则替换）：**

- `Bearer xxx` → `Bearer ***REDACTED***`
- 长 base64 token → `***REDACTED***`
- email 地址中的密码部分

**公开结果文件：** `token.public.json` 只包含布尔标志（`has_access_token`, `has_refresh_token`），不包含实际 token 值。
