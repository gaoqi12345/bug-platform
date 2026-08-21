from sqlalchemy import Column, Integer, String, Boolean, DateTime, func
from app.db.session import Base


class User(Base):
    __tablename__ = "users"

    id             = Column(Integer, primary_key=True, index=True)
    email          = Column(String(255), unique=True, nullable=False, index=True)
    display_name   = Column(String(100), nullable=False)
    password_hash  = Column(String(255), nullable=False)
    feishu_open_id = Column(String(50), nullable=True)
    is_super_admin = Column(Boolean, default=False, nullable=False)
    deactivated_at = Column(DateTime(timezone=True), nullable=True)
    created_at     = Column(DateTime(timezone=True), server_default=func.now())

    # 邮件通知订阅偏好（方案A：用户自主选择，默认全部开启）
    email_notify_assigned       = Column(Boolean, default=True,  nullable=False, server_default="true")
    email_notify_status_changed = Column(Boolean, default=True,  nullable=False, server_default="true")
    email_notify_commented      = Column(Boolean, default=True,  nullable=False, server_default="true")
    email_notify_mentioned      = Column(Boolean, default=True,  nullable=False, server_default="true")
