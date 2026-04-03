# Copyright (c) 2026 html5syt
# SPDX-License-Identifier: MIT
#
# Feishu Wiki tools.

from __future__ import annotations

from typing import Any

from astrbot.api import FunctionTool

from ..lark_client import get_lark_client
from ._common import ok, make_tool


# ---------------------------------------------------------------------------
# feishu_wiki_space
# ---------------------------------------------------------------------------


async def _wiki_space(event: Any, **kw: Any) -> str:
    client = get_lark_client()
    action = kw.get("action")

    try:
        if action == "list":
            params: dict = {}
            if kw.get("page_size"):
                params["page_size"] = kw["page_size"]
            if kw.get("page_token"):
                params["page_token"] = kw["page_token"]
            res = await client.get("/open-apis/wiki/v2/spaces", params=params)
            client.check(res, "wiki_space.list")
            return ok(res.get("data", {}))

        elif action == "get":
            space_id = kw.get("space_id", "")
            if not space_id:
                return ok({"error": "space_id is required for 'get' action"})
            res = await client.get(f"/open-apis/wiki/v2/spaces/{space_id}")
            client.check(res, "wiki_space.get")
            return ok(res.get("data", {}))

        elif action == "create":
            data: dict = {}
            if kw.get("name"):
                data["name"] = kw["name"]
            if kw.get("description"):
                data["description"] = kw["description"]
            res = await client.post("/open-apis/wiki/v2/spaces", data)
            client.check(res, "wiki_space.create")
            return ok(res.get("data", {}))

        else:
            return ok({"error": f"Unknown action: {action}"})

    except Exception as e:
        return ok({"error": str(e)})


WikiSpaceTool: FunctionTool = make_tool(
    name="feishu_wiki_space",
    description=(
        "飞书知识库（Wiki）空间管理工具（以机器人身份）。"
        "Actions: list（列出知识空间）, get（获取知识空间详情）, create（创建知识空间）。"
    ),
    parameters={
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
    },
    handler=_wiki_space,
)


# ---------------------------------------------------------------------------
# feishu_wiki_space_node
# ---------------------------------------------------------------------------


async def _wiki_space_node(event: Any, **kw: Any) -> str:
    client = get_lark_client()
    action = kw.get("action")
    space_id = kw.get("space_id", "")
    node_token = kw.get("node_token", "") or kw.get("token", "")

    try:
        if action == "list":
            if not space_id:
                return ok({"error": "space_id is required for 'list' action"})
            params: dict = {}
            if kw.get("parent_node_token"):
                params["parent_node_token"] = kw["parent_node_token"]
            if kw.get("page_size"):
                params["page_size"] = kw["page_size"]
            if kw.get("page_token"):
                params["page_token"] = kw["page_token"]
            res = await client.get(
                f"/open-apis/wiki/v2/spaces/{space_id}/nodes", params=params
            )
            client.check(res, "wiki_space_node.list")
            return ok(res.get("data", {}))

        elif action == "get":
            if not node_token:
                return ok({"error": "node_token (or token) is required for 'get' action"})
            params = {"token": node_token}
            if kw.get("obj_type"):
                params["obj_type"] = kw["obj_type"]
            res = await client.get(
                "/open-apis/wiki/v2/spaces/get_node", params=params
            )
            client.check(res, "wiki_space_node.get")
            return ok(res.get("data", {}))

        elif action == "create":
            if not space_id:
                return ok({"error": "space_id is required for 'create' action"})
            if not kw.get("obj_type"):
                return ok({"error": "obj_type is required for 'create' action"})
            if not kw.get("obj_token"):
                return ok({"error": "obj_token is required for 'create' action"})
            data: dict = {
                "obj_type": kw["obj_type"],
                "obj_token": kw["obj_token"],
            }
            if kw.get("parent_node_token"):
                data["parent_node_token"] = kw["parent_node_token"]
            res = await client.post(
                f"/open-apis/wiki/v2/spaces/{space_id}/nodes", data
            )
            client.check(res, "wiki_space_node.create")
            return ok(res.get("data", {}))

        elif action == "move":
            if not space_id or not node_token:
                return ok({"error": "space_id and node_token are required for 'move' action"})
            data = {}
            if kw.get("target_parent_node_token"):
                data["target_parent_node_token"] = kw["target_parent_node_token"]
            res = await client.post(
                f"/open-apis/wiki/v2/spaces/{space_id}/nodes/{node_token}/move",
                data,
            )
            client.check(res, "wiki_space_node.move")
            return ok(res.get("data", {}))

        elif action == "copy":
            if not space_id or not node_token:
                return ok({"error": "space_id and node_token are required for 'copy' action"})
            data = {}
            if kw.get("target_parent_node_token"):
                data["target_parent_node_token"] = kw["target_parent_node_token"]
            res = await client.post(
                f"/open-apis/wiki/v2/spaces/{space_id}/nodes/{node_token}/copy",
                data,
            )
            client.check(res, "wiki_space_node.copy")
            return ok(res.get("data", {}))

        else:
            return ok({"error": f"Unknown action: {action}"})

    except Exception as e:
        return ok({"error": str(e)})


WikiSpaceNodeTool: FunctionTool = make_tool(
    name="feishu_wiki_space_node",
    description=(
        "飞书知识库节点管理工具（以机器人身份）。"
        "Actions: list（列出节点）, get（获取节点详情）, "
        "create（创建节点）, move（移动节点）, copy（复制节点）。"
    ),
    parameters={
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
    },
    handler=_wiki_space_node,
)
