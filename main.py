# Copyright (c) 2026 html5syt
# SPDX-License-Identifier: MIT
#
# AstrBot 飞书工具插件 (Feishu Tools Plugin)
#
# 将飞书/Lark 全套 OpenAPI 工具注册为 AstrBot LLM 工具（FunctionTool），
# 让 AI 助手能够直接操作飞书的日历、任务、多维表格、文档、云盘、知识库、电子表格等。
#
# 已移除（由 AstrBot 平台层处理）：
#   - 飞书消息读写（使用 AstrBot 内置飞书平台适配器）
#   - 流式卡片输出（由其他插件实现）
#   - 权限管理（由 AstrBot 内置权限系统处理）
#   - 分群组配置（可使用 AstrBot 内置自定义规则代替）

from __future__ import annotations

from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig

from openclaw_lark import LarkAPIClient, set_lark_client
from openclaw_lark.tools import (
    CalendarCalendarTool,
    CalendarEventTool,
    CalendarEventAttendeeTool,
    CalendarFreebusyTool,
    TaskTaskTool,
    TaskTasklistTool,
    TaskCommentTool,
    TaskSubtaskTool,
    BitableAppTool,
    BitableTableTool,
    BitableRecordTool,
    BitableFieldTool,
    BitableViewTool,
    FetchDocTool,
    CreateDocTool,
    UpdateDocTool,
    DriveFileTool,
    DocCommentsTool,
    DocMediaTool,
    WikiSpaceTool,
    WikiSpaceNodeTool,
    SheetTool,
    SearchDocWikiTool,
    GetUserTool,
    SearchUserTool,
    ChatTool,
)


@register(
    "astrbot_plugin_feishu_tools",
    "html5syt",
    "为 AstrBot 提供飞书/Lark 全套工具：文档、多维表格、电子表格、日历、任务、云盘、知识库等。",
    "1.0.0",
    "https://github.com/html5syt/astrbot-openclaw-lark",
)
class FeishuToolsPlugin(Star):
    """飞书工具 AstrBot 插件。

    此插件将飞书 Open API 中的核心功能封装为 LLM 工具（FunctionTool），
    注册到 AstrBot 的工具系统中，让 AI 助手可以直接操作飞书的各项功能。

    依赖 httpx 进行异步 HTTP 请求。
    配置项请在插件管理面板中填写（app_id、app_secret 等）。
    """

    def __init__(self, context: Context, config: AstrBotConfig) -> None:
        super().__init__(context)
        self.config = config

        app_id: str = config.get("app_id", "")
        app_secret: str = config.get("app_secret", "")
        domain: str = config.get("domain", "feishu")
        mcp_base_url: str = config.get("mcp_base_url", "")
        mcp_uat: str = config.get("mcp_user_access_token", "")

        if not app_id or not app_secret:
            logger.warning(
                "[feishu_tools] app_id 或 app_secret 未配置，飞书工具将无法正常工作。"
                "请在插件管理面板中填写飞书应用凭据。"
            )

        client = LarkAPIClient(
            app_id=app_id,
            app_secret=app_secret,
            domain=domain,
            mcp_base_url=mcp_base_url,
            mcp_user_access_token=mcp_uat,
        )
        set_lark_client(client)

        self.context.add_llm_tools(
            # 日历
            CalendarCalendarTool(),
            CalendarEventTool(),
            CalendarEventAttendeeTool(),
            CalendarFreebusyTool(),
            # 任务
            TaskTaskTool(),
            TaskTasklistTool(),
            TaskCommentTool(),
            TaskSubtaskTool(),
            # 多维表格
            BitableAppTool(),
            BitableTableTool(),
            BitableRecordTool(),
            BitableFieldTool(),
            BitableViewTool(),
            # 文档
            FetchDocTool(),
            CreateDocTool(),
            UpdateDocTool(),
            # 云盘
            DriveFileTool(),
            DocCommentsTool(),
            DocMediaTool(),
            # 知识库
            WikiSpaceTool(),
            WikiSpaceNodeTool(),
            # 电子表格
            SheetTool(),
            # 搜索
            SearchDocWikiTool(),
            # 用户/群聊
            GetUserTool(),
            SearchUserTool(),
            ChatTool(),
        )

        logger.info(
            f"[feishu_tools] 插件已加载，共注册 {len(self._get_registered_tools())} 个飞书工具。"
            f"域名：{domain}，MCP：{'已配置' if mcp_base_url else '未配置'}。"
        )

    def _get_registered_tools(self) -> list[str]:
        return [
            "feishu_calendar_calendar",
            "feishu_calendar_event",
            "feishu_calendar_event_attendee",
            "feishu_calendar_freebusy",
            "feishu_task_task",
            "feishu_task_tasklist",
            "feishu_task_comment",
            "feishu_task_subtask",
            "feishu_bitable_app",
            "feishu_bitable_app_table",
            "feishu_bitable_app_table_record",
            "feishu_bitable_app_table_field",
            "feishu_bitable_app_table_view",
            "feishu_fetch_doc",
            "feishu_create_doc",
            "feishu_update_doc",
            "feishu_drive_file",
            "feishu_doc_comments",
            "feishu_doc_media",
            "feishu_wiki_space",
            "feishu_wiki_space_node",
            "feishu_sheet",
            "feishu_search_doc_wiki",
            "feishu_get_user",
            "feishu_search_user",
            "feishu_chat",
        ]

    async def terminate(self) -> None:
        """插件卸载时清理资源。"""
        logger.info("[feishu_tools] 插件已卸载。")
