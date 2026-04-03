# Copyright (c) 2026 html5syt
# SPDX-License-Identifier: MIT
#
# Feishu Wiki tools.

from __future__ import annotations

import json
from typing import Any

from pydantic import Field
from pydantic.dataclasses import dataclass

from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.agent.tool import FunctionTool, ToolExecResult
from astrbot.core.astr_agent_context import AstrAgentContext

from ..lark_client import get_lark_client


def _ok(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)


# ---------------------------------------------------------------------------
# feishu_wiki_space
# ---------------------------------------------------------------------------


@dataclass
class WikiSpaceTool(FunctionTool[AstrAgentContext]):
    """飞书知识库（Wiki）空间管理工具：列出、获取、创建知识空间。"""

    name: str = "feishu_wiki_space"
    description: str = (
        "飞书知识库（Wiki）空间管理工具（以机器人身份）。"
        "Actions: list（列出知识空间）, get（获取知识空间详情）, create（创建知识空间）。"
    )
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list", "get", "create"],
                    "description": "操作类型",
                },
                "space_id": {
                    "type": "string",
                    "description": "知识空间 ID（action=get 时必填）",
                },
                "name": {
                    "type": "string",
                    "description": "知识空间名称（action=create 时可选）",
                },
                "description": {
                    "type": "string",
                    "description": "知识空间描述（action=create 时可选）",
                },
                "page_size": {
                    "type": "number",
                    "description": "每页数量（action=list，默认 10，最大 50）",
                },
                "page_token": {"type": "string", "description": "分页标记"},
            },
            "required": ["action"],
        }
    )

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs: Any
    ) -> ToolExecResult:
        client = get_lark_client()
        action = kwargs.get("action")

        try:
            if action == "list":
                params: dict = {}
                if kwargs.get("page_size"):
                    params["page_size"] = kwargs["page_size"]
                if kwargs.get("page_token"):
                    params["page_token"] = kwargs["page_token"]
                res = await client.get("/open-apis/wiki/v2/spaces", params=params)
                client.check(res, "wiki_space.list")
                return _ok(res.get("data", {}))

            elif action == "get":
                space_id = kwargs.get("space_id", "")
                if not space_id:
                    return _ok({"error": "space_id is required for 'get' action"})
                res = await client.get(f"/open-apis/wiki/v2/spaces/{space_id}")
                client.check(res, "wiki_space.get")
                return _ok(res.get("data", {}))

            elif action == "create":
                data: dict = {}
                if kwargs.get("name"):
                    data["name"] = kwargs["name"]
                if kwargs.get("description"):
                    data["description"] = kwargs["description"]
                res = await client.post("/open-apis/wiki/v2/spaces", data)
                client.check(res, "wiki_space.create")
                return _ok(res.get("data", {}))

            else:
                return _ok({"error": f"Unknown action: {action}"})

        except Exception as e:
            return _ok({"error": str(e)})


# ---------------------------------------------------------------------------
# feishu_wiki_space_node
# ---------------------------------------------------------------------------


@dataclass
class WikiSpaceNodeTool(FunctionTool[AstrAgentContext]):
    """飞书知识库节点管理工具：列出、获取、创建、移动、复制知识库节点。"""

    name: str = "feishu_wiki_space_node"
    description: str = (
        "飞书知识库节点管理工具（以机器人身份）。"
        "Actions: list（列出节点）, get（获取节点详情）, "
        "create（创建节点）, move（移动节点）, copy（复制节点）。"
    )
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list", "get", "create", "move", "copy"],
                    "description": "操作类型",
                },
                "space_id": {
                    "type": "string",
                    "description": "知识空间 ID（action=list/create/move/copy 时必填）",
                },
                "node_token": {
                    "type": "string",
                    "description": "节点 token（action=get/move/copy 时必填）",
                },
                "token": {
                    "type": "string",
                    "description": "节点 token（action=get 时可用，与 node_token 等效）",
                },
                "obj_type": {
                    "type": "string",
                    "enum": ["doc", "sheet", "mindnote", "bitable", "file", "docx", "slides", "wiki"],
                    "description": "节点类型（action=create 时必填；action=get 时可选）",
                },
                "obj_token": {
                    "type": "string",
                    "description": "文档 token（action=create 时必填，与 obj_type 对应的文档 token）",
                },
                "parent_node_token": {
                    "type": "string",
                    "description": "父节点 token（action=list/create 时可选，不填则在根节点操作）",
                },
                "target_parent_node_token": {
                    "type": "string",
                    "description": "目标父节点 token（action=move/copy 时可选）",
                },
                "page_size": {"type": "number", "description": "每页数量（最大 50）"},
                "page_token": {"type": "string", "description": "分页标记"},
            },
            "required": ["action"],
        }
    )

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs: Any
    ) -> ToolExecResult:
        client = get_lark_client()
        action = kwargs.get("action")
        space_id = kwargs.get("space_id", "")
        node_token = kwargs.get("node_token", "") or kwargs.get("token", "")

        try:
            if action == "list":
                if not space_id:
                    return _ok({"error": "space_id is required for 'list' action"})
                params: dict = {}
                if kwargs.get("parent_node_token"):
                    params["parent_node_token"] = kwargs["parent_node_token"]
                if kwargs.get("page_size"):
                    params["page_size"] = kwargs["page_size"]
                if kwargs.get("page_token"):
                    params["page_token"] = kwargs["page_token"]
                res = await client.get(
                    f"/open-apis/wiki/v2/spaces/{space_id}/nodes", params=params
                )
                client.check(res, "wiki_space_node.list")
                return _ok(res.get("data", {}))

            elif action == "get":
                if not node_token:
                    return _ok({"error": "node_token (or token) is required for 'get' action"})
                params = {"token": node_token}
                if kwargs.get("obj_type"):
                    params["obj_type"] = kwargs["obj_type"]
                res = await client.get(
                    "/open-apis/wiki/v2/spaces/get_node", params=params
                )
                client.check(res, "wiki_space_node.get")
                return _ok(res.get("data", {}))

            elif action == "create":
                if not space_id:
                    return _ok({"error": "space_id is required for 'create' action"})
                if not kwargs.get("obj_type"):
                    return _ok({"error": "obj_type is required for 'create' action"})
                if not kwargs.get("obj_token"):
                    return _ok({"error": "obj_token is required for 'create' action"})
                data: dict = {
                    "obj_type": kwargs["obj_type"],
                    "obj_token": kwargs["obj_token"],
                }
                if kwargs.get("parent_node_token"):
                    data["parent_node_token"] = kwargs["parent_node_token"]
                res = await client.post(
                    f"/open-apis/wiki/v2/spaces/{space_id}/nodes", data
                )
                client.check(res, "wiki_space_node.create")
                return _ok(res.get("data", {}))

            elif action == "move":
                if not space_id or not node_token:
                    return _ok({"error": "space_id and node_token are required for 'move' action"})
                data = {}
                if kwargs.get("target_parent_node_token"):
                    data["target_parent_node_token"] = kwargs["target_parent_node_token"]
                res = await client.post(
                    f"/open-apis/wiki/v2/spaces/{space_id}/nodes/{node_token}/move",
                    data,
                )
                client.check(res, "wiki_space_node.move")
                return _ok(res.get("data", {}))

            elif action == "copy":
                if not space_id or not node_token:
                    return _ok({"error": "space_id and node_token are required for 'copy' action"})
                data = {}
                if kwargs.get("target_parent_node_token"):
                    data["target_parent_node_token"] = kwargs["target_parent_node_token"]
                res = await client.post(
                    f"/open-apis/wiki/v2/spaces/{space_id}/nodes/{node_token}/copy",
                    data,
                )
                client.check(res, "wiki_space_node.copy")
                return _ok(res.get("data", {}))

            else:
                return _ok({"error": f"Unknown action: {action}"})

        except Exception as e:
            return _ok({"error": str(e)})
