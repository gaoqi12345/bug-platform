"""
邮件通知服务（方案A：用户订阅偏好）
- 配置从数据库 system_settings 表读取，带 60s 进程内缓存
- EMAIL_ENABLED=false 时静默跳过
- 支持 SSL/TLS，使用标准库 smtplib + email
- 3 种触发场景：指派、状态变更、评论
"""
import asyncio
import smtplib
import logging
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from string import Template

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── DB 配置缓存（60s TTL） ──────────────────────────────────────────
_cfg_cache: dict = {}
_cfg_ts: float = 0.0
_CFG_TTL = 60.0


def _load_email_cfg() -> dict:
    """从 DB 读取邮件配置，带 60s 缓存"""
    global _cfg_cache, _cfg_ts
    now = time.monotonic()
    if _cfg_cache and now - _cfg_ts < _CFG_TTL:
        return _cfg_cache
    try:
        from app.db.session import SessionLocal
        from sqlalchemy import text
        KEYS = ["email_enabled", "smtp_host", "smtp_port",
                "smtp_user", "smtp_password", "smtp_use_ssl", "email_from_name"]
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
            "enabled":    raw.get("email_enabled",   "false").lower() == "true",
            "host":       raw.get("smtp_host",       ""),
            "port":       int(raw.get("smtp_port",   "465") or "465"),
            "user":       raw.get("smtp_user",       ""),
            "password":   raw.get("smtp_password",   ""),
            "use_ssl":    raw.get("smtp_use_ssl",    "true").lower() == "true",
            "from_name":  raw.get("email_from_name", "Bug Platform"),
        }
        _cfg_ts = now
    except Exception as e:
        logger.warning("读取邮件配置失败，使用 .env 兜底: %s", e)
        # 兜底：使用 .env 中的配置
        _cfg_cache = {
            "enabled":   settings.EMAIL_ENABLED,
            "host":      settings.SMTP_HOST,
            "port":      settings.SMTP_PORT,
            "user":      settings.SMTP_USER,
            "password":  settings.SMTP_PASSWORD,
            "use_ssl":   settings.SMTP_USE_SSL,
            "from_name": settings.EMAIL_FROM_NAME,
        }
        _cfg_ts = now
    return _cfg_cache


def invalidate_cache() -> None:
    """保存新配置后调用，强制下次发信时重新读取"""
    global _cfg_ts
    _cfg_ts = 0.0

# ── HTML 邮件模板基础骨架 ───────────────────────────────────────────
_BASE_HTML = Template("""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<style>
  body{margin:0;padding:0;background:#f5f7fa;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}
  .wrap{max-width:600px;margin:32px auto;background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.08)}
  .header{background:$header_color;padding:24px 32px}
  .header h2{margin:0;color:#fff;font-size:18px;font-weight:700}
  .header p{margin:4px 0 0;color:rgba(255,255,255,.8);font-size:13px}
  .body{padding:28px 32px}
  .field{display:flex;gap:8px;margin-bottom:12px;font-size:14px}
  .field-label{color:#909399;min-width:72px;flex-shrink:0}
  .field-value{color:#1d2129;font-weight:500}
  .badge{display:inline-block;padding:2px 10px;border-radius:12px;font-size:12px;font-weight:600}
  .badge-p0{background:#fff0f0;color:#f56c6c}
  .badge-p1{background:#fff7e6;color:#e6a23c}
  .badge-p2{background:#ecf5ff;color:#409eff}
  .badge-p3{background:#f4f4f5;color:#909399}
  .badge-status{background:#f0f9eb;color:#67c23a}
  .desc{background:#f8f9fc;border-left:4px solid $header_color;border-radius:4px;padding:12px 16px;margin:16px 0;font-size:13px;color:#606266;line-height:1.7}
  .btn{display:inline-block;margin-top:20px;padding:10px 28px;background:$header_color;color:#fff!important;border-radius:6px;text-decoration:none;font-size:14px;font-weight:600}
  .footer{padding:16px 32px;border-top:1px solid #f0f2f5;font-size:12px;color:#c0c4cc;text-align:center}
</style>
</head>
<body>
<div class="wrap">
  <div class="header">
    <h2>$header_title</h2>
    <p>$header_sub</p>
  </div>
  <div class="body">
    $body_content
    <a href="$bug_url" class="btn">查看 Bug 详情</a>
  </div>
  <div class="footer">此邮件由 Bug Platform 自动发送 · <a href="$app_url/profile" style="color:#c0c4cc">管理通知偏好</a></div>
</div>
</body>
</html>""")

PRIORITY_BADGE = {
    "p0": '<span class="badge badge-p0">P0 紧急</span>',
    "p1": '<span class="badge badge-p1">P1 高</span>',
    "p2": '<span class="badge badge-p2">P2 中</span>',
    "p3": '<span class="badge badge-p3">P3 低</span>',
}

STATUS_LABEL = {
    "new": "新建", "assigned": "已指派", "in_progress": "处理中",
    "resolved": "待验证", "closed": "已关闭", "rejected": "已拒绝", "reopened": "重新打开",
}
STATUS_COLOR = {
    "new": "#909399", "assigned": "#409eff", "in_progress": "#e6a23c",
    "resolved": "#67c23a", "closed": "#67c23a", "rejected": "#f56c6c", "reopened": "#e6a23c",
}


def _fields(*pairs) -> str:
    """渲染字段行列表"""
    rows = ""
    for label, value in pairs:
        rows += f'<div class="field"><span class="field-label">{label}</span><span class="field-value">{value}</span></div>'
    return rows


def _build_assigned_html(bug_id: int, title: str, priority: str,
                          description: str, reporter_name: str) -> str:
    app_url   = settings.APP_BASE_URL
    bug_url   = f"{app_url}/bugs/{bug_id}"
    badge     = PRIORITY_BADGE.get(priority, priority)
    desc_text = (description or "（无描述）")[:200].replace("<", "&lt;").replace(">", "&gt;")
    body = (
        _fields(
            ("Bug ID",  f"BUG-{bug_id}"),
            ("标题",    f"<strong>{title}</strong>"),
            ("优先级",  badge),
            ("提交人",  reporter_name),
        )
        + f'<div class="desc">{desc_text}</div>'
    )
    return _BASE_HTML.substitute(
        header_color="#409EFF",
        header_title="有一个 Bug 指派给了你",
        header_sub=f"BUG-{bug_id} · {title[:40]}",
        body_content=body,
        bug_url=bug_url,
        app_url=app_url,
    )


def _build_status_changed_html(bug_id: int, title: str, old_status: str,
                                 new_status: str, operator_name: str) -> str:
    app_url    = settings.APP_BASE_URL
    bug_url    = f"{app_url}/bugs/{bug_id}"
    color      = STATUS_COLOR.get(new_status, "#409EFF")
    old_label  = STATUS_LABEL.get(old_status, old_status)
    new_label  = STATUS_LABEL.get(new_status, new_status)
    body = _fields(
        ("Bug ID",  f"BUG-{bug_id}"),
        ("标题",    f"<strong>{title}</strong>"),
        ("状态变更", f'{old_label} &nbsp;→&nbsp; <span class="badge badge-status">{new_label}</span>'),
        ("操作人",  operator_name),
    )
    return _BASE_HTML.substitute(
        header_color=color,
        header_title="你的 Bug 状态已更新",
        header_sub=f"BUG-{bug_id} · {old_label} → {new_label}",
        body_content=body,
        bug_url=bug_url,
        app_url=app_url,
    )


def _build_commented_html(bug_id: int, title: str,
                            commenter_name: str, comment_text: str) -> str:
    app_url  = settings.APP_BASE_URL
    bug_url  = f"{app_url}/bugs/{bug_id}"
    comment  = comment_text[:300].replace("<", "&lt;").replace(">", "&gt;")
    body = (
        _fields(
            ("Bug ID", f"BUG-{bug_id}"),
            ("标题",   f"<strong>{title}</strong>"),
            ("评论人", commenter_name),
        )
        + f'<div class="desc">{comment}</div>'
    )
    return _BASE_HTML.substitute(
        header_color="#67C23A",
        header_title=f"{commenter_name} 评论了你的 Bug",
        header_sub=f"BUG-{bug_id} · {title[:40]}",
        body_content=body,
        bug_url=bug_url,
        app_url=app_url,
    )


# ── 底层发送 ────────────────────────────────────────────────────────
def _send_email_sync(to_email: str, to_name: str, subject: str, html: str) -> None:
    """同步发送，供 asyncio.to_thread 包装"""
    cfg = _load_email_cfg()
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = formataddr((cfg["from_name"], cfg["user"]))
    msg["To"]      = formataddr((to_name, to_email))
    msg.attach(MIMEText(html, "html", "utf-8"))

    if cfg["use_ssl"]:
        server = smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=10)
    else:
        server = smtplib.SMTP(cfg["host"], cfg["port"], timeout=10)
        server.starttls()

    try:
        server.login(cfg["user"], cfg["password"])
        server.sendmail(cfg["user"], [to_email], msg.as_string())
        logger.info("邮件发送成功", extra={"to": to_email, "subject": subject})
    finally:
        server.quit()


async def _send(to_email: str, to_name: str, subject: str, html: str) -> None:
    cfg = _load_email_cfg()
    if not cfg["enabled"] or not cfg["host"]:
        return
    try:
        await asyncio.to_thread(_send_email_sync, to_email, to_name, subject, html)
    except Exception as e:
        logger.warning("邮件发送失败: %s → %s", to_email, e)


# ── 三个公开通知函数 ────────────────────────────────────────────────
async def notify_email_assigned(bug_id: int, assignee_id: int, reporter_id: int) -> None:
    """Bug 指派通知 → 发给被指派人（需开启 email_notify_assigned）"""
    from app.db.session import SessionLocal
    from app.models.bug import Bug
    from app.models.user import User

    db = SessionLocal()
    try:
        bug      = db.get(Bug, bug_id)
        assignee = db.get(User, assignee_id)
        reporter = db.get(User, reporter_id)
        if not bug or not assignee:
            return
        if not assignee.email_notify_assigned:
            return
        html = _build_assigned_html(
            bug_id=bug.id,
            title=bug.title,
            priority=bug.priority.value if hasattr(bug.priority, "value") else bug.priority,
            description=bug.description or "",
            reporter_name=reporter.display_name if reporter else "未知",
        )
        await _send(
            assignee.email, assignee.display_name,
            f"[BUG-{bug.id}] 有一个 Bug 指派给了你：{bug.title[:40]}",
            html,
        )
    finally:
        db.close()


async def notify_email_status_changed(bug_id: int, operator_id: int,
                                       old_status: str, new_status: str) -> None:
    """状态变更通知 → 发给提交人（需开启 email_notify_status_changed，且操作人≠提交人）"""
    from app.db.session import SessionLocal
    from app.models.bug import Bug
    from app.models.user import User

    db = SessionLocal()
    try:
        bug      = db.get(Bug, bug_id)
        operator = db.get(User, operator_id)
        if not bug:
            return
        reporter = db.get(User, bug.reporter_id) if bug.reporter_id else None
        if not reporter:
            return
        if reporter.id == operator_id:
            return   # 自己改自己的不通知
        if not reporter.email_notify_status_changed:
            return
        html = _build_status_changed_html(
            bug_id=bug.id,
            title=bug.title,
            old_status=old_status,
            new_status=new_status,
            operator_name=operator.display_name if operator else "未知",
        )
        await _send(
            reporter.email, reporter.display_name,
            f"[BUG-{bug.id}] 状态更新：{STATUS_LABEL.get(old_status, old_status)} → {STATUS_LABEL.get(new_status, new_status)}",
            html,
        )
    finally:
        db.close()


async def notify_email_commented(bug_id: int, commenter_id: int, comment_text: str) -> None:
    """评论通知 → 发给提交人+被指派人（去重，排除评论者自身，需开启 email_notify_commented）"""
    from app.db.session import SessionLocal
    from app.models.bug import Bug
    from app.models.user import User

    db = SessionLocal()
    try:
        bug       = db.get(Bug, bug_id)
        commenter = db.get(User, commenter_id)
        if not bug or not commenter:
            return

        recipients: dict[int, User] = {}
        for uid in filter(None, [bug.reporter_id, bug.assignee_id]):
            if uid != commenter_id:
                u = db.get(User, uid)
                if u and u.email_notify_commented:
                    recipients[uid] = u

        html = _build_commented_html(
            bug_id=bug.id,
            title=bug.title,
            commenter_name=commenter.display_name,
            comment_text=comment_text,
        )
        subject = f"[BUG-{bug.id}] {commenter.display_name} 评论了：{bug.title[:40]}"
        for user in recipients.values():
            await _send(user.email, user.display_name, subject, html)
    finally:
        db.close()
