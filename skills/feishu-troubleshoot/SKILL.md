---
name: feishu-troubleshoot
description: |
  飞书工具插件（AstrBot 版）问题排查指南。包含常见问题 FAQ。

---

# 飞书工具插件问题排查

## ❓ 常见问题（FAQ）

### API 返回权限错误（code=99991668 等）

**现象**：工具调用后返回 `code=99991668` 或类似权限错误。

**原因**：飞书应用未开通对应 API 的权限。

**解决步骤**：

1. 登录飞书开放平台：https://open.feishu.cn/app
2. 选择您的应用 → **权限管理**
3. 搜索并开启所需权限（参见 README 中的权限列表）
4. 创建应用版本 → 提交审核 → 发布

---

### 工具调用返回认证错误（code=99991663 等）

**现象**：工具调用后返回认证相关错误，或提示"获取 app_access_token 失败"。

**原因**：`app_id` 或 `app_secret` 配置错误。

**解决步骤**：

1. 登录飞书开放平台：https://open.feishu.cn/app
2. 选择您的应用 → **凭证与基础信息**
3. 核对 App ID 和 App Secret
4. 在 AstrBot 插件管理面板中更新配置

---

### 消息收发不工作

**说明**：本插件（飞书工具插件）**不处理**飞书消息的收发。

消息功能由 AstrBot 内置的飞书平台适配器负责，请检查：

1. AstrBot → 平台设置 → 飞书平台是否已正确配置
2. 飞书开放平台的机器人事件订阅是否已配置
3. 详情请参考 [AstrBot 文档](https://docs.astrbot.app/)

---

### 文档操作功能有限（create/update）

**说明**：未配置 MCP 服务时，`feishu_update_doc` 只支持 `append` 模式。

如需完整的文档操作功能（包括 Markdown 创建文档、多种更新模式），请配置 MCP 服务：

1. 参考 [Feishu MCP 项目](https://github.com/larksuite/feishu-mcp) 启动 MCP 服务
2. 在插件配置中填写 `mcp_base_url`

