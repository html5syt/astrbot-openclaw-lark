# AstrBot Feishu Tools Plugin

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-%3E%3D3.10-blue.svg)](https://www.python.org/)
[![AstrBot Version](https://img.shields.io/badge/astrbot-%3E%3D4.5.0-green.svg)](https://github.com/AstrBotDevs/AstrBot)

**English** | [中文](./README.md)

---

This is a Feishu/Lark Open API integration plugin for [AstrBot](https://github.com/AstrBotDevs/AstrBot). It wraps Feishu's calendar, tasks, multidimensional tables, spreadsheets, documents, cloud drive, wiki, and more as LLM tools (FunctionTool), enabling AI assistants to directly operate your Feishu workspace.

> **About the original version**: This plugin is a Python rewrite of the [OpenClaw Lark Plugin](https://github.com/html5syt/astrbot-openclaw-lark) TypeScript version, specifically adapted for the AstrBot platform.
> - Messaging uses AstrBot's built-in [Feishu platform adapter](https://docs.astrbot.app/)
> - Permission management is handled by AstrBot itself
> - Removed: streaming card output, OAuth user authorization, per-group configuration

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
| 📄 Docs | `feishu_fetch_doc` | Get document content (Markdown) |
| 📄 Docs | `feishu_create_doc` | Create documents |
| 📄 Docs | `feishu_update_doc` | Update document content |
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

| Setting | Required | Description |
|---------|----------|-------------|
| `app_id` | ✅ | Feishu App ID |
| `app_secret` | ✅ | Feishu App Secret |
| `domain` | ❌ | Domain: `feishu` (China) or `lark` (International), default `feishu` |
| `mcp_base_url` | ❌ | Feishu MCP server URL (optional, for richer document operations) |
| `mcp_user_access_token` | ❌ | User access token for MCP server (optional) |

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

### Connecting Feishu Messages (Platform Adapter)

This plugin **does not handle** message sending/receiving. For Feishu messaging, use AstrBot's built-in Feishu platform adapter:

1. Open AstrBot WebUI → Platform Settings
2. Add Feishu platform, fill in App ID, App Secret, Verification Token, etc.
3. Configure bot event subscription URL in Feishu Open Platform

See [AstrBot Feishu Platform Adapter Documentation](https://docs.astrbot.app/) for details.

---

## Document Operation Notes

### Basic Usage (REST API)

Without MCP service configured, document operations use the Feishu Docx REST API:
- `feishu_fetch_doc`: Returns plain text content
- `feishu_create_doc`: Creates empty document (with optional title)
- `feishu_update_doc`: Only supports `append` mode (append text)

### Advanced Usage (With MCP Service)

With MCP service configured, document operations are much more powerful:
- `feishu_fetch_doc`: Returns Lark-flavored Markdown content
- `feishu_create_doc`: Supports creating documents from Markdown
- `feishu_update_doc`: Supports 7 update modes (append/overwrite/replace_range, etc.)

See [Feishu MCP Project](https://github.com/larksuite/feishu-mcp) for MCP setup.

---

## Security Notes

This plugin uses Feishu **App Access Token** (bot identity) for API calls.

Please note:
- **Keep App Secret secure** and never commit it to public repositories
- Only enable the permissions you actually need (principle of least privilege)
- Regularly review plugin operation logs

---

## Development & Contributing

This plugin is developed following the [AstrBot Plugin Development Guide](https://docs.astrbot.app/dev/star/plugin-new.html).

Issues and Pull Requests are welcome.

---

## License

MIT License © 2026 html5syt

This software calls Feishu/Lark Open Platform APIs at runtime. Usage of these APIs requires compliance with:
- [Feishu Privacy Policy](https://www.feishu.cn/privacy)
- [Feishu Terms of Service](https://www.feishu.cn/terms)
- [Lark Privacy Policy](https://www.larksuite.com/privacy-policy)
- [Lark Terms of Service](https://www.larksuite.com/user-terms-of-service)
