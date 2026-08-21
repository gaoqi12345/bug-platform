import asyncio
import base64
import hashlib
import hmac
import json
import logging
import time

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

PRIORITY_COLOR = {"p0": "red", "p1": "orange", "p2": "yellow", "p3": "blue"}
PRIORITY_EMOJI = {"p0": "🔴", "p1": "🟠", "p2": "🟡", "p3": "🟢"}

# ── DB 配置缓存（60s TTL）──────────────────────────────────────────
# 与 email_service.py 同款模式：system_settings 表存运行时配置
_cfg_cache: dict = {}
_cfg_ts: float = 0.0
_CFG_TTL = 60.0


def _load_feishu_cfg() -> dict:
    """
    从 DB system_settings 读取飞书通知总开关 + 自建应用凭证，带 60s 缓存。
    键：
      feishu_group_notify_enabled   群通知总开关（默认 true，兼容旧行为）
      feishu_private_notify_enabled 私聊总开关（默认 false）
      feishu_app_id / feishu_app_secret / feishu_verification_token
    DB 读取失败时回退到 config.toml 的 [feishu] 段。
    """
    global _cfg_cache, _cfg_ts
    now = time.monotonic()
    if _cfg_cache and now - _cfg_ts < _CFG_TTL:
        return _cfg_cache
    try:
        from app.db.session import SessionLocal
        from sqlalchemy import text
        KEYS = [
            "feishu_group_notify_enabled", "feishu_private_notify_enabled",
            "feishu_app_id", "feishu_app_secret", "feishu_verification_token",
        ]
        db = SessionLocal()
        try:
            rows = db.execute(
                text("SELECT key, value FROM system_settings WHERE key = ANY(:keys)"),
                {"keys": KEYS},
            ).fetchall()
            raw = {r.key: r.value for r in rows}
        finally:
            db.close()
        _cfg_cache = {
            "group_notify_enabled":   raw.get("feishu_group_notify_enabled", "true").lower() == "true",
            "private_notify_enabled": raw.get("feishu_private_notify_enabled", "false").lower() == "true",
            "app_id":                 raw.get("feishu_app_id", ""),
            "app_secret":             raw.get("feishu_app_secret", ""),
            "verification_token":     raw.get("feishu_verification_token", ""),
        }
        _cfg_ts = now
    except Exception as e:
        logger.warning("读取飞书配置失败，使用 config.toml 兜底: %s", e)
        _cfg_cache = {
            "group_notify_enabled":   True,
            "private_notify_enabled": False,
            "app_id":                 settings.FEISHU_APP_ID,
            "app_secret":             settings.FEISHU_APP_SECRET,
            "verification_token":     settings.FEISHU_VERIFICATION_TOKEN,
        }
        _cfg_ts = now
    return _cfg_cache


def invalidate_cache() -> None:
    """保存新配置后调用，强制下次发送时重新读取"""
    global _cfg_ts
    _cfg_ts = 0.0


# ── 自建应用 tenant_access_token（进程内缓存，7200s 过期提前刷新）──

_token_cache: dict = {}
_token_ts: float = 0.0


async def _get_tenant_access_token() -> str | None:
    """获取自建应用 tenant_access_token，带进程内缓存（缓存 7000s）"""
    global _token_cache, _token_ts
    now = time.monotonic()
    if _token_cache.get("token") and (now - _token_ts) < 7000:
        return _token_cache["token"]

    cfg = _load_feishu_cfg()
    if not cfg["app_id"] or not cfg["app_secret"]:
        return None

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                json={"app_id": cfg["app_id"], "app_secret": cfg["app_secret"]},
            )
            data = resp.json()
            if data.get("code") != 0 or not data.get("tenant_access_token"):
                logger.warning("获取 tenant_access_token 失败: %s", data.get("msg"))
                return None
            _token_cache = {"token": data["tenant_access_token"]}
            _token_ts = now
            return _token_cache["token"]
    except Exception as e:
        logger.warning("获取 tenant_access_token 异常: %s", e)
        return None


def _gen_sign(timestamp: int, secret: str) -> str:
    """飞书官方 HMAC-SHA256 签名：key="{ts}\n{secret}"，msg=空字节"""
    string_to_sign = f"{timestamp}\n{secret}"
    code = hmac.new(
        key=string_to_sign.encode("utf-8"),
        msg=b"",
        digestmod=hashlib.sha256,
    ).digest()
    return base64.b64encode(code).decode()


def _card_body(bug_id: int, title: str, priority: str,
               description: str, assignee_open_id: str | None,
               assignee_name: str, reporter_name: str) -> tuple[dict, str]:
    """公共卡片头 + 描述区。返回 (header_dict, markdown_content)"""
    priority_emoji = PRIORITY_EMOJI.get(priority, "⚪")
    color = PRIORITY_COLOR.get(priority, "blue")
    at_str = (
        f"<at id={assignee_open_id}></at>"
        if assignee_open_id
        else assignee_name
    )
    header = {
        "title": {
            "tag": "plain_text",
            "content": f"🐛 [BUG-{bug_id}] {title}",
        },
        "template": color,
    }
    markdown = (
        f"**指派给：** {at_str}\n"
        f"**提交人：** {reporter_name}　"
        f"**优先级：** {priority_emoji} {priority.upper()}"
    )
    return header, markdown


def _build_card(bug_id: int, title: str, priority: str,
                description: str, assignee_open_id: str | None,
                assignee_name: str, reporter_name: str) -> dict:
    """群通知卡片（webhook 版，保持原样：仅 open_url 按钮）"""
    header, markdown = _card_body(
        bug_id, title, priority, description,
        assignee_open_id, assignee_name, reporter_name,
    )
    bug_url = f"{settings.APP_BASE_URL}/bugs/{bug_id}"

    return {
        "msg_type": "interactive",
        "card": {
            "schema": "2.0",
            "config": {"update_multi": False, "enable_forward": True},
            "header": header,
            "body": {
                "direction": "vertical",
                "padding": "12px 12px 12px 12px",
                "elements": [
                    {"tag": "markdown", "content": markdown},
                    {
                        "tag": "markdown",
                        "content": f"**描述：** {description[:150] if description else '(无描述)'}",
                        "margin": "8px 0px 8px 0px",
                    },
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "🔍 查看详情"},
                        "type": "primary",
                        "size": "medium",
                        "behaviors": [{"type": "open_url", "default_url": bug_url}],
                    },
                ],
            },
        },
    }


def _build_private_card(bug_id: int, title: str, priority: str,
                        description: str, assignee_name: str,
                        reporter_name: str, status: str) -> dict:
    """
    私聊卡片（自建应用版）：内容与群卡片一致，但带卡片交互按钮。
    callback value 由 feishu_callback.py 消费：
      action=start   → ASSIGNED → IN_PROGRESS（开始处理）
      action=resolve → IN_PROGRESS → RESOLVED（标记完成）
    按当前状态渲染可用按钮，其余状态仅保留查看详情。
    """
    header, markdown = _card_body(
        bug_id, title, priority, description,
        None, assignee_name, reporter_name,
    )
    bug_url = f"{settings.APP_BASE_URL}/bugs/{bug_id}"

    elements: list[dict] = [
        {"tag": "markdown", "content": markdown},
        {
            "tag": "markdown",
            "content": f"**描述：** {description[:150] if description else '(无描述)'}",
            "margin": "8px 0px 8px 0px",
        },
    ]

    # 状态动作按钮：仅在当前状态下合法时渲染
    if status in ("assigned", "reopened"):
        elements.append({
            "tag": "button",
            "text": {"tag": "plain_text", "content": "🛠 开始处理"},
            "type": "primary",
            "size": "medium",
            "behaviors": [{"type": "callback", "value": {"bug_id": bug_id, "action": "start"}}],
        })
    elif status == "in_progress":
        elements.append({
            "tag": "button",
            "text": {"tag": "plain_text", "content": "✅ 标记完成"},
            "type": "primary",
            "size": "medium",
            "behaviors": [{"type": "callback", "value": {"bug_id": bug_id, "action": "resolve"}}],
        })

    elements.append({
        "tag": "button",
        "text": {"tag": "plain_text", "content": "🔍 查看详情"},
        "type": "default",
        "size": "medium",
        "behaviors": [{"type": "open_url", "default_url": bug_url}],
    })

    return {
        "msg_type": "interactive",
        "card": {
            "schema": "2.0",
            "config": {"update_multi": False, "enable_forward": True},
            "header": header,
            "body": {
                "direction": "vertical",
                "padding": "12px 12px 12px 12px",
                "elements": elements,
            },
        },
    }


async def _send_webhook(payload: dict, max_retries: int = 3) -> None:
    if not settings.FEISHU_WEBHOOK_URL:
        return

    ts = int(time.time())
    if settings.FEISHU_WEBHOOK_SECRET:
        payload = {
            "timestamp": str(ts),
            "sign": _gen_sign(ts, settings.FEISHU_WEBHOOK_SECRET),
            **payload,
        }

    async with httpx.AsyncClient(timeout=10.0) as client:
        for attempt in range(max_retries):
            try:
                resp = await client.post(
                    settings.FEISHU_WEBHOOK_URL,
                    content=json.dumps(payload, ensure_ascii=False).encode(),
                    headers={"Content-Type": "application/json"},
                )
                data = resp.json()
                if data.get("code") == 0:
                    return
                logger.warning("飞书返回错误 attempt=%d code=%s msg=%s",
                               attempt + 1, data.get("code"), data.get("msg"))
            except Exception as e:
                logger.warning("飞书通知失败 attempt=%d: %s", attempt + 1, e)

            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # 1s, 2s, 4s


async def _send_private_message(open_id: str, card: dict, max_retries: int = 3) -> None:
    """
    通过自建应用向用户发送私聊卡片消息。
    POST /open-apis/im/v1/messages?receive_id_type=open_id
    """
    token = await _get_tenant_access_token()
    if not token:
        logger.warning("未配置飞书自建应用凭证，跳过私聊发送")
        return

    payload = {
        "receive_id": open_id,
        "msg_type": "interactive",
        "content": json.dumps(card["card"], ensure_ascii=False),
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        for attempt in range(max_retries):
            try:
                resp = await client.post(
                    "https://open.feishu.cn/open-apis/im/v1/messages",
                    params={"receive_id_type": "open_id"},
                    headers={"Authorization": f"Bearer {token}"},
                    json=payload,
                )
                data = resp.json()
                if data.get("code") == 0:
                    return
                logger.warning("飞书私聊发送失败 attempt=%d code=%s msg=%s",
                               attempt + 1, data.get("code"), data.get("msg"))
            except Exception as e:
                logger.warning("飞书私聊发送异常 attempt=%d: %s", attempt + 1, e)

            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)


def _bug_status_str(bug_or_enum) -> str:
    """
    兼容两种调用方式：
      _bug_status_str(bug)          → Bug 对象，取 bug.status 枚举值
      _bug_status_str(bug.priority) → 直接传 Priority/BugStatus 枚举值
    """
    value = getattr(bug_or_enum, "status", bug_or_enum)
    return value.value if hasattr(value, "value") else str(value)


async def notify_bug_assigned(bug_id: int, assignee_id: int, reporter_id: int) -> None:
    """
    async def，供 FastAPI BackgroundTasks 直接调用。
    接收 ID 而非 ORM 对象，内部开独立 Session，避免 DetachedInstanceError。
    群通知总开关 feishu_group_notify_enabled=false 时跳过（默认开，兼容旧行为）。
    """
    cfg = _load_feishu_cfg()
    if not cfg["group_notify_enabled"]:
        logger.info("群通知总开关已关闭，跳过飞书群通知 bug_id=%s", bug_id)
        return

    from app.db.session import SessionLocal
    from app.models.bug import Bug
    from app.models.user import User

    db = SessionLocal()
    try:
        bug = db.get(Bug, bug_id)
        assignee = db.get(User, assignee_id)
        reporter = db.get(User, reporter_id)
        if not bug or not assignee:
            return
        card = _build_card(
            bug_id=bug.id,
            title=bug.title,
            priority=_bug_status_str(bug.priority),
            description=bug.description or "",
            assignee_open_id=assignee.feishu_open_id,
            assignee_name=assignee.display_name,
            reporter_name=reporter.display_name if reporter else "未知",
        )
        await _send_webhook(card)
    finally:
        db.close()


async def notify_assignee_private(bug_id: int, assignee_id: int, reporter_id: int) -> None:
    """
    Bug 指派 → 向被指派人发送飞书个人私聊卡片（带状态操作按钮）。
    私聊总开关 feishu_private_notify_enabled=false 时跳过（默认关）。
    额外前提：自建应用凭证已配置 + 被指派人有 feishu_open_id。
    """
    cfg = _load_feishu_cfg()
    if not cfg["private_notify_enabled"]:
        return
    if not cfg["app_id"] or not cfg["app_secret"]:
        logger.info("未配置飞书自建应用，跳过私聊通知 bug_id=%s", bug_id)
        return

    from app.db.session import SessionLocal
    from app.models.bug import Bug
    from app.models.user import User

    db = SessionLocal()
    try:
        bug = db.get(Bug, bug_id)
        assignee = db.get(User, assignee_id)
        reporter = db.get(User, reporter_id)
        if not bug or not assignee or not assignee.feishu_open_id:
            return
        card = _build_private_card(
            bug_id=bug.id,
            title=bug.title,
            priority=_bug_status_str(bug.priority),
            description=bug.description or "",
            assignee_name=assignee.display_name,
            reporter_name=reporter.display_name if reporter else "未知",
            status=_bug_status_str(bug),
        )
        await _send_private_message(assignee.feishu_open_id, card)
        logger.info("飞书私聊通知已发送", extra={"bug_id": bug.id, "assignee_id": assignee.id})
    finally:
        db.close()
