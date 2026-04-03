# AstrBot Feishu Tools Plugin

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-%3E%3D3.10-blue.svg)](https://www.python.org/)
[![AstrBot Version](https://img.shields.io/badge/astrbot-%3E%3D4.5.0-green.svg)](https://github.com/AstrBotDevs/AstrBot)

**English** | [中文](./README.md)

---

A Feishu/Lark Open API integration plugin for [AstrBot](https://github.com/AstrBotDevs/AstrBot). It wraps Feishu's calendar, tasks, multidimensional tables, spreadsheets, documents, cloud drive, wiki, and more as LLM tools (FunctionTool), enabling AI assistants to directly operate your Feishu workspace.

---

## Features

| Category | Tool Name | Capabilities |
|----------|-----------|-------------|
| 📅 Calendar | `feishu_calendar_calendar` | List calendars, get calendar info, primary calendar |
| 📅 Calendar | `feishu_calendar_event` | Create/list/get/update/delete/search/reply events |
| 📅 Calendar | `feishu_calendar_event_attendee` | Manage event attendees |
| 📅 Calendar | `feishu_calendar_freebusy` | Query user free/busy status |
| ✅ Tasks | `feishu_task_task` | Create/get/list/update tasks |
| ✅ Tasks | `feishu_task_tasklist` | Manage task lists |
| ✅ Tasks | `feishu_task_comment` | Manage task comments |
| ✅ Tasks | `feishu_task_subtask` | Manage subtasks |
| 📊 Bitable | `feishu_bitable_app` | Create/get/list/patch/copy bitable apps |
| 📊 Bitable | `feishu_bitable_app_table` | Manage data tables |
| 📊 Bitable | `feishu_bitable_app_table_record` | CRUD records with batch operations |
| 📊 Bitable | `feishu_bitable_app_table_field` | Manage fields (columns) |
| 📊 Bitable | `feishu_bitable_app_table_view` | Manage views |
| 📄 Docs | `feishu_fetch_doc` | Get document content |
| 📄 Docs | `feishu_create_doc` | Create documents |
| 📄 Docs | `feishu_update_doc` | Append or replace document content |
| 🗂️ Drive | `feishu_drive_file` | List/meta/copy/move/delete/create folder |
| 🗂️ Drive | `feishu_doc_comments` | Manage document comments |
| 🗂️ Drive | `feishu_doc_media` | Download document media resources |
| 📚 Wiki | `feishu_wiki_space` | Manage wiki spaces |
| 📚 Wiki | `feishu_wiki_space_node` | Manage wiki nodes |
| 📈 Sheets | `feishu_sheet` | Read/write/append data, create spreadsheets |
| 🔍 Search | `feishu_search_doc_wiki` | Search docs and wiki |
| 👤 Users | `feishu_get_user` | Get user information |
| 👤 Users | `feishu_search_user` | Search users |
| 💬 Chat | `feishu_chat` | Search/get chats, list members |

---

## Installation

### Option 1: Via AstrBot WebUI (Recommended)

1. Open AstrBot WebUI → Plugin Market
2. Search for `feishu_tools` or install via GitHub URL
3. After installation, fill in your Feishu app credentials in the plugin settings

### Option 2: Manual Installation

```bash
cd AstrBot/data/plugins
git clone https://github.com/html5syt/astrbot-openclaw-lark astrbot_plugin_feishu_tools
```

---

## Configuration

In the AstrBot plugin management panel, find this plugin and fill in the following settings:

| Setting | Required | Default | Description |
|---------|----------|---------|-------------|
| `app_id` | ✅ | — | Feishu App ID |
| `app_secret` | ✅ | — | Feishu App Secret |
| `domain` | ❌ | `feishu` | Domain: `feishu` (China) or `lark` (International) |
| `auth_mode` | ❌ | `tenant` | Auth mode: `tenant` (bot identity) or `user` (user OAuth) |

### Creating a Feishu App

1. Visit [Feishu Open Platform](https://open.feishu.cn/app)
2. Create an enterprise self-built app
3. Get `App ID` and `App Secret` from "Credentials & Basic Info"
4. Enable required permissions in "Permission Management" (see permission list below)
5. Publish the app to your workspace

### Recommended Permissions

<details>
<summary>📅 Calendar Permissions</summary>

- `calendar:calendar:readonly` - Read calendars
- `calendar:calendar` - Manage calendars
- `calendar:acl` - Manage calendar permissions

</details>

<details>
<summary>✅ Task Permissions</summary>

- `task:task:write` - Manage tasks
- `task:task:read` - Read tasks

</details>

<details>
<summary>📊 Bitable Permissions</summary>

- `bitable:app` - Manage bitables
- `bitable:app:readonly` - Read bitables

</details>

<details>
<summary>📄 Doc/Drive Permissions</summary>

- `docx:document` - Manage documents
- `docx:document:readonly` - Read documents
- `drive:drive` - Manage drive files
- `drive:drive:readonly` - Read drive files

</details>

<details>
<summary>📚 Wiki Permissions</summary>

- `wiki:wiki:readonly` - Read wikis
- `wiki:wiki` - Manage wikis

</details>

<details>
<summary>📈 Sheets Permissions</summary>

- `sheets:spreadsheet` - Manage spreadsheets
- `sheets:spreadsheet:readonly` - Read spreadsheets

</details>

<details>
<summary>🔍 Search Permissions</summary>

- `docs:doc:search` - Search documents

</details>

<details>
<summary>👤 User/Chat Permissions</summary>

- `contact:user.base:readonly` - Read basic user info
- `im:chat:readonly` - Read chat information

</details>

### Connecting Feishu Messages (Platform Adapter)

This plugin **does not handle** message sending/receiving. For Feishu messaging, use AstrBot's built-in Feishu platform adapter:

1. Open AstrBot WebUI → Platform Settings
2. Add Feishu platform, fill in App ID, App Secret, Verification Token, etc.
3. Configure bot event subscription URL in Feishu Open Platform

See [AstrBot Feishu Platform Adapter Documentation](https://docs.astrbot.app/) for details.

---

## Authentication Modes

The plugin supports two authentication modes. Set the default in plugin config, or switch at any time with commands:

### Tenant (Bot) Mode — Default

AI tools call the Feishu API as the bot. Suitable for most automation scenarios.

### User OAuth Mode

AI tools call the Feishu API as a specific user. Suitable for accessing personal data (e.g., personal calendar, private documents).

To use user OAuth mode, authorize first:

```
/feishu login
```

After authorization, AI tools will operate Feishu as your user identity. If a tool encounters a permission error, it will prompt you to run `/feishu login` to re-authorize.

### Command Reference

| Command | Description |
|---------|-------------|
| `/feishu auth` | Show current auth mode and token status |
| `/feishu auth tenant` | Switch to tenant (bot) mode |
| `/feishu auth user` | Switch to user OAuth mode |
| `/feishu login` | Start OAuth authorization (Device Flow) — sends an auth link |
| `/feishu logout` | Revoke the current user's OAuth authorization |

---

## Document Operations

Document operations are implemented directly via the Feishu Docx v1 REST API — no external MCP server required:

- `feishu_fetch_doc`: Returns plain text content with optional `offset`/`limit` pagination
- `feishu_create_doc`: Creates a document with optional title and initial text content
- `feishu_update_doc`: Supports `append` (add to end) and `replace_all`/`overwrite` (clear and rewrite)

---

## Security Notes

- **Keep App Secret secure** — never commit it to public repositories
- Only enable the permissions you actually need (principle of least privilege)
- User OAuth tokens are stored encrypted in AstrBot's KV store and are never exposed to the AI layer

---

## Development & Contributing

This plugin is developed following the [AstrBot Plugin Development Guide](https://docs.astrbot.app/dev/star/plugin-new.html).

Issues and Pull Requests are welcome.

---

## License

MIT License © 2026 html5syt

This software calls Feishu/Lark Open Platform APIs at runtime. Usage of these APIs requires compliance with:
- [Feishu Terms of Service](https://www.feishu.cn/terms)
- [Feishu Privacy Policy](https://www.feishu.cn/privacy)
- [Lark Terms of Service](https://www.larksuite.com/user-terms-of-service)
- [Lark Privacy Policy](https://www.larksuite.com/privacy-policy)
