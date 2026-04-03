# 飞书工具插件（AstrBot Feishu Tools Plugin）

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-%3E%3D3.10-blue.svg)](https://www.python.org/)
[![AstrBot Version](https://img.shields.io/badge/astrbot-%3E%3D4.5.0-green.svg)](https://github.com/AstrBotDevs/AstrBot)

[English](./README.en.md) | **中文**

---

这是将飞书/Lark Open API 集成到 [AstrBot](https://github.com/AstrBotDevs/AstrBot) 的工具插件。它将飞书的日历、任务、多维表格、电子表格、文档、云盘、知识库等功能封装为 LLM 工具（FunctionTool），让 AI 助手可以直接操作你的飞书工作区。

> **关于原始版本**：本插件是 [OpenClaw Lark 插件](https://github.com/html5syt/astrbot-openclaw-lark) TypeScript 版的 Python 改写版本，专门适配 AstrBot 平台。
> - 消息收发使用 AstrBot 内置的[飞书平台适配器](https://docs.astrbot.app/)，无需重复配置；
> - 权限管理由 AstrBot 自身处理；
> - 已移除流式卡片输出、OAuth 用户授权、分群组配置等原插件功能。

---

## 功能特性

| 类别 | 工具名称 | 主要能力 |
|------|---------|----------|
| 📅 日历 | `feishu_calendar_calendar` | 查询日历列表、获取日历信息、主日历 |
| 📅 日历 | `feishu_calendar_event` | 日程的创建/查询/更新/删除/搜索/回复/实例 |
| 📅 日历 | `feishu_calendar_event_attendee` | 参会人管理 |
| 📅 日历 | `feishu_calendar_freebusy` | 用户忙闲查询 |
| ✅ 任务 | `feishu_task_task` | 任务的创建/查询/更新/完成 |
| ✅ 任务 | `feishu_task_tasklist` | 清单管理及清单内任务查询 |
| ✅ 任务 | `feishu_task_comment` | 任务评论管理 |
| ✅ 任务 | `feishu_task_subtask` | 子任务管理 |
| 📊 多维表格 | `feishu_bitable_app` | 多维表格应用的创建/查询/更新/复制 |
| 📊 多维表格 | `feishu_bitable_app_table` | 数据表管理 |
| 📊 多维表格 | `feishu_bitable_app_table_record` | 记录（行）的增删改查及批量操作 |
| 📊 多维表格 | `feishu_bitable_app_table_field` | 字段（列）管理 |
| 📊 多维表格 | `feishu_bitable_app_table_view` | 视图管理 |
| 📄 文档 | `feishu_fetch_doc` | 获取云文档内容（Markdown）|
| 📄 文档 | `feishu_create_doc` | 创建云文档 |
| 📄 文档 | `feishu_update_doc` | 更新云文档内容 |
| 🗂️ 云盘 | `feishu_drive_file` | 文件列表/元数据/复制/移动/删除/创建文件夹 |
| 🗂️ 云盘 | `feishu_doc_comments` | 文档评论管理 |
| 🗂️ 云盘 | `feishu_doc_media` | 文档媒体资源下载 |
| 📚 知识库 | `feishu_wiki_space` | 知识空间管理 |
| 📚 知识库 | `feishu_wiki_space_node` | 知识库节点管理 |
| 📈 电子表格 | `feishu_sheet` | 读写/追加数据、表格信息、创建 |
| 🔍 搜索 | `feishu_search_doc_wiki` | 文档与知识库统一搜索 |
| 👤 用户 | `feishu_get_user` | 获取用户信息 |
| 👤 用户 | `feishu_search_user` | 搜索用户 |
| 💬 群聊 | `feishu_chat` | 搜索/获取群聊、查询群成员 |

---

## 安装

### 方式一：通过 AstrBot WebUI 安装（推荐）

1. 打开 AstrBot WebUI → 插件市场
2. 搜索 `feishu_tools` 或通过 GitHub 地址安装
3. 安装完成后，在插件配置页面填写飞书应用凭据

### 方式二：手动安装

```bash
cd AstrBot/data/plugins
git clone https://github.com/html5syt/astrbot-openclaw-lark astrbot_plugin_feishu_tools
```

---

## 配置

在 AstrBot 插件管理面板中，找到本插件，填写以下配置：

| 配置项 | 必填 | 说明 |
|--------|------|------|
| `app_id` | ✅ | 飞书应用的 App ID |
| `app_secret` | ✅ | 飞书应用的 App Secret |
| `domain` | ❌ | 飞书域名，`feishu`（国内）或 `lark`（海外），默认 `feishu` |
| `mcp_base_url` | ❌ | 飞书 MCP 服务地址（可选，用于更完整的文档操作支持） |
| `mcp_user_access_token` | ❌ | MCP 服务的用户访问令牌（可选） |

### 创建飞书应用

1. 访问[飞书开放平台](https://open.feishu.cn/app)
2. 创建企业自建应用
3. 在「凭证与基础信息」中获取 `App ID` 和 `App Secret`
4. 在「权限管理」中开启所需权限（参见下方权限列表）
5. 将应用发布到工作区

### 推荐应用权限

根据你需要使用的工具开启对应权限：

<details>
<summary>📅 日历相关权限</summary>

- `calendar:calendar:readonly` - 查询日历
- `calendar:calendar` - 管理日历
- `calendar:acl` - 管理日历权限

</details>

<details>
<summary>✅ 任务相关权限</summary>

- `task:task:write` - 管理任务（包含写权限）
- `task:task:read` - 读取任务

</details>

<details>
<summary>📊 多维表格相关权限</summary>

- `bitable:app` - 管理多维表格
- `bitable:app:readonly` - 查看多维表格

</details>

<details>
<summary>📄 文档/云盘相关权限</summary>

- `docx:document` - 管理文档
- `docx:document:readonly` - 读取文档
- `drive:drive` - 管理云盘文件
- `drive:drive:readonly` - 查看云盘文件

</details>

<details>
<summary>📚 知识库相关权限</summary>

- `wiki:wiki:readonly` - 查看知识库
- `wiki:wiki` - 管理知识库

</details>

<details>
<summary>📈 电子表格相关权限</summary>

- `sheets:spreadsheet` - 管理电子表格
- `sheets:spreadsheet:readonly` - 读取电子表格

</details>

<details>
<summary>🔍 搜索权限</summary>

- `docs:doc:search` - 搜索文档

</details>

<details>
<summary>👤 用户/群聊权限</summary>

- `contact:user.base:readonly` - 获取用户基本信息
- `contact:user.phone:readonly` - 获取用户手机号（可选）
- `im:chat:readonly` - 查看群聊信息

</details>

### 连接飞书消息（平台适配器）

本插件**不处理**消息的收发。接收/发送飞书消息请使用 AstrBot 内置的飞书平台适配器：

1. 打开 AstrBot WebUI → 平台设置
2. 添加飞书平台，填写 App ID、App Secret、Verification Token 等
3. 在飞书开放平台配置机器人事件订阅地址

详情请参考 [AstrBot 飞书平台适配器文档](https://docs.astrbot.app/)。

---

## 文档操作说明

### 基本用法（REST API）

不配置 MCP 服务时，文档操作通过飞书 Docx REST API 实现：
- `feishu_fetch_doc`：返回纯文本内容
- `feishu_create_doc`：创建空白文档（可指定标题）
- `feishu_update_doc`：仅支持 `append`（追加文本）模式

### 高级用法（配置 MCP 服务）

配置 MCP 服务后，文档操作功能更强大：
- `feishu_fetch_doc`：返回 Lark-flavored Markdown 格式内容
- `feishu_create_doc`：支持从 Markdown 创建有内容的文档
- `feishu_update_doc`：支持 7 种更新模式（append/overwrite/replace_range 等）

如需使用 MCP 服务，请参考 [Feishu MCP 项目](https://github.com/larksuite/feishu-mcp)。

---

## 安全说明

本插件使用飞书**应用访问令牌**（App Access Token）调用 API，即以机器人身份操作。

请注意：
- **妥善保管** App Secret，不要提交到公开代码仓库
- 根据最小权限原则，只开启实际需要的 API 权限
- 定期审查插件的操作日志

---

## 开发 & 贡献

本插件基于 [AstrBot 插件开发指南](https://docs.astrbot.app/dev/star/plugin-new.html) 开发。

欢迎提交 Issue 和 Pull Request。

---

## 许可证

MIT License © 2026 html5syt

本软件运行时会调用飞书/Lark 开放平台 API，使用这些 API 需遵守以下协议：
- [飞书用户服务协议](https://www.feishu.cn/terms)
- [飞书隐私政策](https://www.feishu.cn/privacy)
- [Lark 用户服务协议](https://www.larksuite.com/user-terms-of-service)
- [Lark 隐私政策](https://www.larksuite.com/privacy-policy)
