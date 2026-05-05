#!/usr/bin/env python3
"""
ScreenPlan QQ Bot — Lightweight AI Agent via OneBot v11 WebSocket.

Acts as a WebSocket SERVER that NapCatQQ connects TO (reverse WS).
Receives QQ messages, uses DeepSeek function-calling for admin queries.

Dependencies (pip install):
    websockets
    httpx
"""

import asyncio
import json
import logging
import os
import re
import time
from collections import defaultdict
from datetime import date

import httpx
import websockets
from websockets.asyncio.server import serve

# ─── Config (env vars) ────────────────────────────────────

SPBOT_LISTEN_HOST = os.environ.get("SPBOT_LISTEN_HOST", "0.0.0.0")
SPBOT_LISTEN_PORT = int(os.environ.get("SPBOT_LISTEN_PORT", "3001"))
SPBOT_COMMAND_PREFIX = os.environ.get("SPBOT_PREFIX", "/")
SPBOT_ADMIN_TOKEN = os.environ.get("SPBOT_ADMIN_TOKEN", "")
SCREENPLAN_HOST = os.environ.get("SPBOT_SCREENPLAN_HOST", "http://localhost:5051")
SCREENPLAN_API = f"{SCREENPLAN_HOST}/api/admin"
LLM_API_KEY = os.environ.get("SPBOT_LLM_KEY", "") or os.environ.get("DEEPSEEK_API_KEY", "")
LLM_API_BASE = os.environ.get("SPBOT_LLM_BASE", "https://api.deepseek.com/v1")
LLM_MODEL = os.environ.get("SPBOT_LLM_MODEL", "deepseek-chat")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("spbot")

# ─── DeepSeek Function Definitions ────────────────────────

FUNCTIONS = [
    {
        "type": "function",
        "function": {
            "name": "query_user_list",
            "description": "列出所有已注册用户及其ID、邮箱和显示名称。用于当你需要知道有哪些用户时调用。",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_user_usage",
            "description": "查询指定用户的屏幕使用摘要（今日或指定日期）。包含总时长、学习/娱乐/其他占比、各设备详情。",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "integer", "description": "用户ID"},
                    "date": {"type": "string", "description": "日期 YYYY-MM-DD，默认今天"},
                },
                "required": ["user_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_user_timeline",
            "description": "查询指定用户的时间线详情，包含各设备的活动事件列表。",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "integer", "description": "用户ID"},
                    "date": {"type": "string", "description": "日期 YYYY-MM-DD，默认今天"},
                },
                "required": ["user_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_server_status",
            "description": "查询 ScreenPlan 服务器状态，包含运行时间、用户数、设备数、今日事件数。",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]

SYSTEM_PROMPT = """你是一个友好、博学的 AI 助手，通过 QQ 消息为用户服务。你同时具备 ScreenPlan 管理员权限，可以查询关联用户的屏幕使用数据。

你的双重身份：
★ 通用 AI 助手 —— 回答知识问答、闲聊、编程建议、日常问题等，像一个正常的 AI 助手一样对话
★ ScreenPlan 管理员 —— 当用户询问屏幕时间、使用情况、时间线、用户列表、服务器状态时，调用相应的函数获取真实数据

调函数的判断标准（满足其一即调用）：
- 消息中提到"屏幕"、"用了多久"、"屏幕时间"、"使用情况"、"学了多久"、"在用哪些应用"
- 消息中提到某个用户名并怀疑在询问使用数据
- 消息中提到"时间线"、"活动事件"、"设备列表"
- 消息中提到"有哪些用户"、"用户列表"、"注册用户"
- 消息中提到"服务器"、"系统状态"、"运行时间"
- 消息中出现了明确的用户ID（如"用户1"、"ID:3"）

通用对话规则：
- 对于知识问答、编程问题、闲聊等非 ScreenPlan 话题，直接用自己的知识回答，不要调函数
- 回复保持友好、简洁，用中文
- 不要编造屏幕使用数据——涉及数据必须调函数
- 如果函数返回"User not found"，如实告知用户

ScreenPlan 数据输出规则：
- QQ 不支持 Markdown 表格和加粗。严禁使用 **bold**、| 表格 |、### 标题
- 纯文本分行 + 空格缩进排列，每项独立一行
- 时长用「小时 分钟」如 "5h33min"
- 百分比紧接数据，如 "学习78% 娱乐14% 其他8%"
- 数据回复控制在 15 行以内
- 如果用户说"我"/"我的"，不知道该查谁时询问ID或名字

格式示例：
━━ zmy（2026-05-05）━━
总屏幕时间：6h05min  重叠：3h19min
  Mac（macOS）：5h33min | 学习78% 娱乐14% 其他8%
  Tab（Android）：2h27min | 学习22% 娱乐69% 其他9%"""

# ─── Conversation History ─────────────────────────────────

MAX_HISTORY_ROUNDS = 15      # keep last 15 exchange rounds
HISTORY_EXPIRE_SECONDS = 1800  # 30 min inactivity clears history
_history: dict[str, list[dict]] = defaultdict(list)
_last_active: dict[str, float] = {}


def _chat_key(msg: dict) -> str:
    """Derive a per-chat key for storing conversation history."""
    mt = msg.get("message_type", "private")
    if mt == "group":
        return f"g_{msg.get('group_id', '0')}"
    uid = msg.get("user_id") or msg.get("sender", {}).get("user_id", "0")
    return f"p_{uid}"


def _expire_old(ck: str):
    now = time.time()
    if ck in _last_active and (now - _last_active[ck]) > HISTORY_EXPIRE_SECONDS:
        _history.pop(ck, None)
        _last_active.pop(ck, None)


def _trim_history(ck: str):
    h = _history[ck]
    max_msgs = MAX_HISTORY_ROUNDS * 2  # user + assistant per round
    if len(h) > max_msgs:
        _history[ck] = h[-max_msgs:]


# ─── HTTP helpers ─────────────────────────────────────────

def admin_api(path: str) -> dict:
    """Call ScreenPlan admin API."""
    headers = {"Authorization": f"Bearer {SPBOT_ADMIN_TOKEN}"}
    try:
        r = httpx.get(f"{SCREENPLAN_API}/{path}", headers=headers, timeout=30)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPError as e:
        log.error(f"Admin API error: {e}")
        return {"error": str(e)}


async def call_llm(messages: list, data_mode: bool = False) -> str:
    """Call DeepSeek chat/completions with function calling.
    
    data_mode=True → low temperature for factual responses (ScreenPlan queries)
    data_mode=False → higher temperature for natural conversation
    """
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "tools": FUNCTIONS,
        "tool_choice": "auto",
        "temperature": 0.1 if data_mode else 0.7,
        "max_tokens": 2048,
    }

    async with httpx.AsyncClient(timeout=60) as client:
        for attempt in range(3):
            try:
                r = await client.post(
                    f"{LLM_API_BASE}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                r.raise_for_status()
                return r.json()["choices"][0]["message"]
            except Exception as e:
                log.warning(f"LLM call attempt {attempt+1} failed: {e}")
                await asyncio.sleep(1)
        return {"content": "抱歉，AI 服务暂时不可用，请稍后重试。"}


# ─── Function executors ───────────────────────────────────

def execute_function(name: str, args: dict) -> str:
    """Execute a tool/function call and return result as JSON string."""
    if name == "query_user_list":
        data = admin_api("users")
        if "error" in data:
            return f"错误: {data['error']}"
        lines = [f"共 {data['count']} 个注册用户："]
        for u in data.get("users", []):
            lines.append(f"  ID:{u['id']}  {u['display_name']} ({u['email']})")
        return "\n".join(lines)

    if name == "query_user_usage":
        uid = args["user_id"]
        dt = args.get("date", date.today().isoformat())
        data = admin_api(f"usage/{uid}?date={dt}")
        if "error" in data:
            return f"错误: {data['error']}"
        name = data.get("display_name", f"用户{uid}")
        total = data.get("total_minutes_all_devices", 0)
        devs = data.get("devices", [])
        lines = [f"{name}（{dt}）屏幕使用报告："]
        lines.append(f"  总使用时间：{total:.0f} 分钟（{total/60:.1f}h）")
        if data.get("overlap_minutes", 0) > 0:
            lines.append(f"  多设备重叠：{data['overlap_minutes']:.0f} 分钟")
        for d in devs:
            lines.append(
                f"  {d['device_name']}（{d['platform']}）：{d['total_minutes']:.0f}min "
                f"学习 {d['learning_pct']:.0f}% / 娱乐 {d['entertainment_pct']:.0f}%"
            )
        return "\n".join(lines)

    if name == "query_user_timeline":
        uid = args["user_id"]
        dt = args.get("date", date.today().isoformat())
        data = admin_api(f"timeline/{uid}?date={dt}")
        if "error" in data:
            return f"错误: {data['error']}"
        name = data.get("display_name", f"用户{uid}")
        devs = data.get("devices", [])
        total_events = sum(d["event_count"] for d in devs)
        lines = [f"{name}（{dt}）时间线：共 {total_events} 个活动事件"]
        for d in devs:
            lines.append(f"  {d['device_name']}（{d['platform']}）：{d['event_count']} 事件")
            # Show last 5 events as preview
            events = d.get("events", [])[-5:]
            for ev in events:
                ts = ev["timestamp"].split("T")[1][:5] if "T" in ev["timestamp"] else ev["timestamp"]
                lines.append(f"    {ts}  {ev['app_name']} [{ev['category']}]")
        return "\n".join(lines)

    if name == "query_server_status":
        data = admin_api("health")
        if "error" in data:
            return f"错误: {data['error']}"
        uptime_h = data.get("uptime_seconds", 0) / 3600
        return (
            f"ScreenPlan 服务器状态：\n"
            f"  状态：{data.get('status', 'unknown')}\n"
            f"  版本：v{data.get('version', '?')}\n"
            f"  运行时间：{uptime_h:.1f} 小时\n"
            f"  注册用户：{data.get('user_count', 0)} 人\n"
            f"  注册设备：{data.get('device_count', 0)} 台\n"
            f"  今日事件：{data.get('today_events', 0)} 条"
        )

    return f"未知函数: {name}"


# ─── Message handler ──────────────────────────────────────

async def handle_message(msg: dict):
    """Process an incoming OneBot message event."""
    msg_type = msg.get("message_type", "private")
    raw = msg.get("raw_message", msg.get("message", ""))
    user_id = msg.get("user_id") or msg.get("sender", {}).get("user_id", "unknown")
    group_id = msg.get("group_id")

    # Only respond to commands starting with prefix in groups
    if msg_type == "group" and group_id:
        if not raw.strip().startswith(SPBOT_COMMAND_PREFIX):
            return  # ignore non-command messages in groups
        query = raw[len(SPBOT_COMMAND_PREFIX):].strip()
    else:
        query = raw.strip()

    if not query:
        return

    log.info(f"Processing: [{user_id}] {query[:80]}")

    ck = _chat_key(msg)
    _expire_old(ck)
    _last_active[ck] = time.time()

    # Build messages: system prompt + history + current query
    history = _history.get(ck, [])
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": f"用户ID {user_id} 说：{query}"})

    used_functions = False

    # LLM conversation loop (handle function calls)
    for round_num in range(5):  # max 5 tool call rounds
        response = await call_llm(messages, data_mode=used_functions)
        messages.append(response)

        if response.get("tool_calls"):
            used_functions = True
            for tc in response["tool_calls"]:
                func = tc["function"]
                fname = func["name"]
                try:
                    fargs = json.loads(func["arguments"])
                except Exception:
                    fargs = {}
                log.info(f"  → calling {fname}({fargs})")
                result = execute_function(fname, fargs)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result,
                })
        elif response.get("content"):
            reply = response["content"]
            # Store in history
            h = _history[ck]
            h.append({"role": "user", "content": query})
            h.append({"role": "assistant", "content": reply})
            _trim_history(ck)
            await send_reply(msg, reply)
            return

    # Fallback: LLM didn't produce final text content
    _history[ck].append({"role": "user", "content": query})
    _history[ck].append({"role": "assistant", "content": "抱歉，处理超时，请稍后重试。"})
    _trim_history(ck)
    await send_reply(msg, "抱歉，处理超时，请稍后重试。")


# ─── OneBot sender ────────────────────────────────────────

# Map of connected NapCatQQ clients: {self_id: websocket}
_ws_clients: dict[str, websockets.WebSocketServerProtocol] = {}


async def send_reply(msg: dict, text: str):
    """Send a reply back via the appropriate WebSocket connection."""
    # Find a connected client (usually there is only one)
    if not _ws_clients:
        log.warning("No NapCatQQ client connected, cannot send reply")
        return

    ws = next(iter(_ws_clients.values()))

    msg_type = msg.get("message_type", "private")
    send_payload = {
        "action": "send_msg",
        "params": {
            "message_type": msg_type,
            "message": text,
        },
    }
    if msg_type == "group":
        send_payload["params"]["group_id"] = msg.get("group_id")
    else:
        send_payload["params"]["user_id"] = msg.get("user_id") or msg.get("sender", {}).get("user_id")

    try:
        await ws.send(json.dumps(send_payload, ensure_ascii=False))
    except Exception as e:
        log.error(f"Failed to send reply: {e}")


async def handle_ws_connection(ws: websockets.WebSocketServerProtocol):
    """Handle a single NapCatQQ WebSocket connection."""
    peer = ws.remote_address
    log.info(f"NapCatQQ connected from {peer}")

    try:
        async for raw in ws:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            post_type = data.get("post_type", "")

            # Handle meta_event: identify the bot's self_id
            if post_type == "meta_event":
                meta_type = data.get("meta_event_type", "")
                if meta_type == "lifecycle":
                    self_id = str(data.get("self_id", ""))
                    if self_id:
                        _ws_clients[self_id] = ws
                        log.info(f"Bot self_id: {self_id}")
                continue

            # Handle message events
            if post_type == "message":
                msg_type = data.get("message_type", "")
                if msg_type in ("group", "private"):
                    asyncio.create_task(handle_message(data))

    except websockets.exceptions.ConnectionClosed:
        log.info(f"NapCatQQ disconnected: {peer}")
    except Exception as e:
        log.error(f"WS error: {e}")
    finally:
        # Clean up
        for k, v in list(_ws_clients.items()):
            if v is ws:
                del _ws_clients[k]


async def ws_server():
    """Start WebSocket server for NapCatQQ to connect to."""
    addr = (SPBOT_LISTEN_HOST, SPBOT_LISTEN_PORT)
    log.info(f"WebSocket server listening on ws://{SPBOT_LISTEN_HOST}:{SPBOT_LISTEN_PORT}")
    async with serve(handle_ws_connection, SPBOT_LISTEN_HOST, SPBOT_LISTEN_PORT) as server:
        await asyncio.Future()  # run forever


# ─── Main ─────────────────────────────────────────────────

async def main():
    if not SPBOT_ADMIN_TOKEN:
        log.fatal("SPBOT_ADMIN_TOKEN not set. Please configure your environment.")
        return
    if not LLM_API_KEY:
        log.fatal("SPBOT_LLM_KEY not set. Please configure your environment.")
        return
    await ws_server()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Shutting down")
