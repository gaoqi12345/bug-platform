from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.db.session import get_db
from app.models.user import User
from app.core.security import verify_password, create_access_token, decode_token, hash_password
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["认证"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    try:
        user_id = decode_token(token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Token 无效或已过期")
    user = db.get(User, user_id)
    if not user or user.deactivated_at:
        raise HTTPException(status_code=401, detail="用户不存在或已停用")
    return user


@router.post("/login")
def login(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    client_ip = request.client.host if request.client else "unknown"
    user = db.query(User).filter(User.email == form.username).first()
    if not user or not verify_password(form.password, user.password_hash):
        logger.warning("登录失败", extra={
            "email": form.username,
            "client_ip": client_ip,
            "reason": "邮箱或密码错误",
        })
        raise HTTPException(status_code=401, detail="邮箱或密码错误")
    logger.info("登录成功", extra={
        "user_id": user.id,
        "email": user.email,
        "client_ip": client_ip,
    })
    return {
        "access_token": create_access_token(user.id),
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "display_name": user.display_name,
            "email": user.email,
            "is_super_admin": user.is_super_admin,
        },
    }


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "display_name": current_user.display_name,
        "email": current_user.email,
        "is_super_admin": current_user.is_super_admin,
        "feishu_open_id": current_user.feishu_open_id,
    }


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """修改当前用户密码，需要验证旧密码"""
    if not verify_password(payload.old_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="旧密码不正确")
    if len(payload.new_password) < 6:
        raise HTTPException(status_code=400, detail="新密码至少 6 位")
    if payload.old_password == payload.new_password:
        raise HTTPException(status_code=400, detail="新密码不能与旧密码相同")
    current_user.password_hash = hash_password(payload.new_password)
    db.commit()
    logger.info("密码修改成功", extra={"user_id": current_user.id})
    return {"ok": True}
