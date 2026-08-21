"""
feishu_callback.py — 飞书卡片交互回调（card.action.trigger）

两种投递模式共用同一套处理逻辑：
  - HTTP 模式：POST /api/v1/feishu/callback（生产部署，需公网可达 URL）
  - WebSocket 长连接模式：main.py lifespan 中启动 lark-oapi ws.Client（本地开发推荐）

按钮 value 约定（见 notify_service._build_private_card）：
  {"bug_id": <int>, "action": "start" | "resolve"}
    start   → ASSIGNED/REOPENED → IN_PROGRESS（开始处理）
    resolve → IN_PROGRESS → RESOLVED（标记完成）

安全：请求来源通过 header.token 与配置的 verification_token 比对校验。
身份：回调携带 operator.open_id，映射到 users.feishu_open_id 后走正常
      RBAC（check_permission）+ 流转规则（validate_transition）校验。
"""
import json
import logging
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.core.logging import get_logger
from app.models.enums import BugStatus
from app.services.notify_service import (
    _build_private_card,
    _bug_status_str,
    _load_feishu_cfg,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/feishu", tags=["飞书回调"])

# 按钮 action → 目标状态
_ACTION_TO_STATUS = {
    "start": BugStatus.IN_PROGRESS,   # 开始处理
    "resolve": BugStatus.RESOLVED,    # 标记完成
}


def _verify_token(header_token: Optional[str]) -> bool:
    """校验回调来源：header.token 与配置的 Verification Token 一致"""
    cfg = _load_feishu_cfg()
    expected = cfg.get("verification_token", "")
    if not expected:
        logger.warning("未配置 feishu_verification_token，跳过回调校验")
        return True
    return bool(header_token) and header_token == expected


def _build_response(toast_type: str, content: str, card: Optional[dict] = None) -> dict:
    """构造飞书回调响应（新版 card.action.trigger 格式）"""
    resp = {"code": 0, "data": {"toast": {"type": toast_type, "content": content}}}
    if card is not None:
        resp["data"]["card"] = card
    return resp


def _find_user_by_open_id(db, open_id: str):
    from app.models.user import User
    return db.query(User).filter(User.feishu_open_id == open_id).first()


def handle_card_action(event: dict, db) -> dict:
    """
    处理单次卡片按钮点击。event 为飞书回调的 event 对象（含 operator / action）。
    db 由调用方传入（HTTP 模式用请求 Session，WebSocket 模式开独立 Session）。
    返回飞书回调响应 dict。
    """
    operator = event.get("operator") or {}
    action = event.get("action") or {}
    value = action.get("value") or {}

    open_id = operator.get("open_id")
    bug_id = value.get("bug_id")
    act = value.get("action")

    if not open_id:
        return _build_response("error", "无法识别操作人，请先绑定飞书账号")
    if not bug_id or act not in _ACTION_TO_STATUS:
        return _build_response("error", "无效的卡片操作")

    user = _find_user_by_open_id(db, open_id)
    if not user:
        return _build_response("error", "飞书账号未绑定系统用户，请联系管理员")

    from app.services.transition_service import apply_bug_transition

    try:
        bug, old_status = apply_bug_transition(
            db, int(bug_id), user, _ACTION_TO_STATUS[act],
        )
    except Exception as e:
        from fastapi import HTTPException
        if isinstance(e, HTTPException):
            logger.info("飞书卡片回调流转失败 bug_id=%s action=%s: %s",
                        bug_id, act, e.detail)
            return _build_response("error", str(e.detail))
        logger.error("飞书卡片回调处理异常 bug_id=%s action=%s", bug_id, act, exc_info=True)
        return _build_response("error", "处理失败，请稍后重试或到系统操作")

    # 成功后更新卡片：按新状态渲染可用按钮
    from app.models.user import User
    reporter = db.get(User, bug.reporter_id) if bug.reporter_id else None
    new_card = _build_private_card(
        bug_id=bug.id,
        title=bug.title,
        priority=_bug_status_str(bug.priority),
        description=bug.description or "",
        assignee_name=user.display_name,
        reporter_name=reporter.display_name if reporter else "未知",
        status=_bug_status_str(bug),
    )["card"]

    status_label = {
        "in_progress": "处理中", "resolved": "待验证",
    }.get(_bug_status_str(bug), _bug_status_str(bug))
    return _build_response("success", f"BUG-{bug.id} 已更新为「{status_label}」", new_card)


def parse_ws_event(data) -> Optional[dict]:
    """
    WebSocket 模式：把 lark-oapi 的 P2CardActionTrigger 对象序列化为 dict。
    返回 event 子对象；解析失败返回 None。
    """
    try:
        import lark_oapi as lark
        event_dict = json.loads(lark.JSON.marshal(data))
        return event_dict.get("event") or {}
    except Exception as e:
        logger.error("解析飞书 WebSocket 回调失败: %s", e, exc_info=True)
        return None


# ── HTTP 回调端点（生产模式）────────────────────────────────────────────

@router.post("/callback")
async def feishu_callback(request: Request):
    """
    HTTP 回调入口。飞书开放平台在用户点击卡片按钮时 POST 到此地址。
    1. 校验 header.token
    2. 处理卡片动作
    3. 3 秒内返回响应（toast + 可选 card 即时更新）
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"code": 400, "msg": "无效请求体"})

    header = body.get("header") or {}
    if header.get("event_type") not in ("card.action.trigger",):
        # 非卡片回调事件（如 url_verification 等），直接确认
        return {"code": 0}

    if not _verify_token(header.get("token")):
        logger.warning("飞书回调校验失败: token 不匹配")
        return JSONResponse(status_code=401, content={"code": 401, "msg": "回调校验失败"})

    from app.db.session import SessionLocal
    db = SessionLocal()
    try:
        resp = handle_card_action(body.get("event") or {}, db)
        return resp
    finally:
        db.close()


# ── WebSocket 长连接处理器（本地开发模式）────────────────────────────────

def build_ws_event_handler():
    """
    构建 lark-oapi WebSocket 事件分发器，注册 card.action.trigger。
    供 main.py lifespan 启动长连接时调用。
    """
    try:
        import lark_oapi as lark
        from lark_oapi.event.callback.model.p2_card_action_trigger import (
            P2CardActionTriggerResponse,
        )
    except ImportError:
        logger.warning("未安装 lark-oapi，飞书长连接回调不可用")
        return None

    def _on_card_action(data):
        event = parse_ws_event(data)
        if not event:
            return P2CardActionTriggerResponse(
                {"toast": {"type": "error", "content": "回调解析失败"}}
            )
        from app.db.session import SessionLocal
        db = SessionLocal()
        try:
            resp = handle_card_action(event, db)
        finally:
            db.close()
        return P2CardActionTriggerResponse(resp.get("data", {}))

    handler = (
        lark.EventDispatcherHandler.builder("", "")
        .register_p2_card_action_trigger(_on_card_action)
        .build()
    )
    return handler
