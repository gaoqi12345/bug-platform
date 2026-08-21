"""
系统配置接口（超管专用）
- GET  /system/email-settings  读取邮件配置
- PUT  /system/email-settings  保存邮件配置
- POST /system/email-test      发送测试邮件
"""
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from app.db.session import get_db
from app.api.v1.auth import get_current_user
from app.api.v1.users import require_super_admin
from app.models.user import User

router = APIRouter(prefix="/system", tags=["系统配置"])

# ── 读写 system_settings 的辅助函数 ─────────────────────────────

EMAIL_KEYS = [
    "email_enabled", "smtp_host", "smtp_port",
    "smtp_user", "smtp_password", "smtp_use_ssl", "email_from_name",
]

FEISHU_KEYS = [
    "feishu_group_notify_enabled", "feishu_private_notify_enabled",
    "feishu_app_id", "feishu_app_secret", "feishu_verification_token",
]


def _get_settings(db: Session, keys: list[str] | None = None) -> dict:
    from sqlalchemy import text
    key_list = keys or EMAIL_KEYS
    rows = db.execute(
        text("SELECT key, value FROM system_settings WHERE key = ANY(:keys)"),
        {"keys": key_list},
    ).fetchall()
    return {r.key: r.value for r in rows}


def _set_settings(db: Session, data: dict) -> None:
    from sqlalchemy import text
    for k, v in data.items():
        db.execute(
            text("""
                INSERT INTO system_settings (key, value)
                VALUES (:k, :v)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value,
                    updated_at = now()
            """),
            {"k": k, "v": str(v) if v is not None else ""},
        )
    db.commit()


# ── Schemas ──────────────────────────────────────────────────────

class EmailSettings(BaseModel):
    email_enabled:   bool   = False
    smtp_host:       str    = ""
    smtp_port:       int    = 465
    smtp_user:       str    = ""
    smtp_password:   str    = ""   # 空字符串表示不更改
    smtp_use_ssl:    bool   = True
    email_from_name: str    = "Bug Platform"


class EmailTestRequest(BaseModel):
    to_email: str


# ── 路由 ──────────────────────────────────────────────────────────

@router.get("/email-settings")
def get_email_settings(
    db: Session = Depends(get_db),
    _: User = Depends(require_super_admin),
):
    raw = _get_settings(db)
    return {
        "email_enabled":   raw.get("email_enabled",   "false").lower() == "true",
        "smtp_host":       raw.get("smtp_host",       ""),
        "smtp_port":       int(raw.get("smtp_port",   "465") or "465"),
        "smtp_user":       raw.get("smtp_user",       ""),
        "smtp_password":   "",    # 密码不回显，前端占位符处理
        "smtp_use_ssl":    raw.get("smtp_use_ssl",    "true").lower() == "true",
        "email_from_name": raw.get("email_from_name", "Bug Platform"),
        "has_password":    bool(raw.get("smtp_password", "")),  # 告知前端是否已设置密码
    }


@router.put("/email-settings")
def update_email_settings(
    payload: EmailSettings,
    db: Session = Depends(get_db),
    _: User = Depends(require_super_admin),
):
    raw = _get_settings(db)
    data = {
        "email_enabled":   str(payload.email_enabled).lower(),
        "smtp_host":       payload.smtp_host,
        "smtp_port":       str(payload.smtp_port),
        "smtp_user":       payload.smtp_user,
        "smtp_use_ssl":    str(payload.smtp_use_ssl).lower(),
        "email_from_name": payload.email_from_name,
    }
    # 密码为空时保留旧密码
    if payload.smtp_password:
        data["smtp_password"] = payload.smtp_password
    else:
        data["smtp_password"] = raw.get("smtp_password", "")

    _set_settings(db, data)

    # 清除 email_service 缓存，让下次发信立即用新配置
    from app.services.email_service import invalidate_cache
    invalidate_cache()

    return {"ok": True}


@router.post("/email-test")
def test_email(
    payload: EmailTestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """发送一封测试邮件，验证 SMTP 配置是否正确"""
    raw = _get_settings(db)
    host     = raw.get("smtp_host", "")
    port     = int(raw.get("smtp_port", "465") or "465")
    user     = raw.get("smtp_user", "")
    password = raw.get("smtp_password", "")
    use_ssl  = raw.get("smtp_use_ssl", "true").lower() == "true"
    from_name = raw.get("email_from_name", "Bug Platform")

    if not host or not user:
        raise HTTPException(status_code=400, detail="请先填写 SMTP 服务器和发件账号")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "[Bug Platform] SMTP 连接测试"
    msg["From"]    = formataddr((from_name, user))
    msg["To"]      = payload.to_email
    msg.attach(MIMEText(
        f"<p>这是一封测试邮件，由 <b>Bug Platform</b> 发送。</p>"
        f"<p>如果你收到此邮件，说明 SMTP 配置正确。</p>"
        f"<p style='color:#909399;font-size:12px;'>发送时间：{__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>",
        "html", "utf-8",
    ))

    try:
        if use_ssl:
            server = smtplib.SMTP_SSL(host, port, timeout=10)
        else:
            server = smtplib.SMTP(host, port, timeout=10)
            server.starttls()
        server.login(user, password)
        server.sendmail(user, [payload.to_email], msg.as_string())
        server.quit()
        return {"ok": True, "message": f"测试邮件已发送至 {payload.to_email}"}
    except smtplib.SMTPAuthenticationError:
        raise HTTPException(status_code=400, detail="SMTP 认证失败，请检查账号和密码（或授权码）")
    except smtplib.SMTPConnectError:
        raise HTTPException(status_code=400, detail=f"无法连接到 {host}:{port}，请检查服务器地址和端口")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"发送失败：{str(e)}")


# ── 飞书通知配置 ──────────────────────────────────────────────────

class FeishuSettings(BaseModel):
    group_notify_enabled:   bool = True     # 群通知总开关（默认开，兼容旧行为）
    private_notify_enabled: bool = False    # 个人私聊总开关（默认关）
    app_id:                 str  = ""
    app_secret:             str  = ""       # 空字符串表示不更改
    verification_token:     str  = ""       # 回调安全校验用（空表示不更改）


@router.get("/feishu-settings")
def get_feishu_settings(
    db: Session = Depends(get_db),
    _: User = Depends(require_super_admin),
):
    raw = _get_settings(db, FEISHU_KEYS)
    return {
        "group_notify_enabled":   raw.get("feishu_group_notify_enabled", "true").lower() == "true",
        "private_notify_enabled": raw.get("feishu_private_notify_enabled", "false").lower() == "true",
        "app_id":                 raw.get("feishu_app_id", ""),
        "app_secret":             "",
        "has_app_secret":         bool(raw.get("feishu_app_secret", "")),
        "verification_token":     "",
        "has_verification_token": bool(raw.get("feishu_verification_token", "")),
    }


@router.put("/feishu-settings")
def update_feishu_settings(
    payload: FeishuSettings,
    db: Session = Depends(get_db),
    _: User = Depends(require_super_admin),
):
    raw = _get_settings(db, FEISHU_KEYS)
    data = {
        "feishu_group_notify_enabled":   str(payload.group_notify_enabled).lower(),
        "feishu_private_notify_enabled": str(payload.private_notify_enabled).lower(),
        "feishu_app_id":                 payload.app_id,
    }
    # 密文字段为空时保留旧值
    data["feishu_app_secret"] = payload.app_secret or raw.get("feishu_app_secret", "")
    data["feishu_verification_token"] = payload.verification_token or raw.get("feishu_verification_token", "")

    _set_settings(db, data)

    # 清除 notify_service 缓存，让下次发送立即用新配置
    from app.services.notify_service import invalidate_cache as invalidate_feishu_cache
    invalidate_feishu_cache()

    return {"ok": True}
