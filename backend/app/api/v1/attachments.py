from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel
from app.db.session import get_db
from app.api.v1.auth import get_current_user
from app.core.rbac import check_permission, has_permission
from app.models.user import User
from app.models.bug import Bug, BugAttachment

router = APIRouter(prefix="/bugs", tags=["附件"])
images_router = APIRouter(prefix="/images", tags=["富文本图片"])


class PresignRequest(BaseModel):
    filename: str
    content_type: str


class ConfirmUploadRequest(BaseModel):
    object_key: str
    file_name: str
    file_size: Optional[int] = None
    content_type: Optional[str] = None


@router.post("/{bug_id}/attachments/presign")
def presign_upload(
    bug_id: int,
    payload: PresignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    bug = db.get(Bug, bug_id)
    if not bug:
        raise HTTPException(status_code=404, detail="Bug 不存在")
    check_permission(db, current_user.id, bug.project_id, "attachment.upload")
    from app.services.storage_service import generate_upload_presign
    try:
        return generate_upload_presign(bug_id, payload.filename, payload.content_type)
    except ValueError as e:
        raise HTTPException(status_code=415, detail=str(e))


@router.post("/{bug_id}/attachments/confirm")
def confirm_upload(
    bug_id: int,
    payload: ConfirmUploadRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    bug = db.get(Bug, bug_id)
    if not bug:
        raise HTTPException(status_code=404, detail="Bug 不存在")
    check_permission(db, current_user.id, bug.project_id, "attachment.upload")
    attachment = BugAttachment(
        bug_id=bug_id,
        file_name=payload.file_name,
        object_key=payload.object_key,
        file_size=payload.file_size,
        content_type=payload.content_type,
        uploaded_by=current_user.id,
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    return {
        "id": attachment.id,
        "file_name": attachment.file_name,
        "object_key": attachment.object_key,
        "file_size": attachment.file_size,
        "uploaded_at": str(attachment.uploaded_at),
    }


@router.get("/{bug_id}/attachments")
def list_attachments(
    bug_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    bug = db.get(Bug, bug_id)
    if not bug:
        raise HTTPException(status_code=404, detail="Bug 不存在")
    check_permission(db, current_user.id, bug.project_id, "attachment.view")
    return [
        {
            "id": a.id,
            "file_name": a.file_name,
            "file_size": a.file_size,
            "content_type": a.content_type,
            "uploaded_at": str(a.uploaded_at),
        }
        for a in bug.attachments
    ]


@router.get("/{bug_id}/attachments/{attachment_id}/download")
def download_attachment(
    bug_id: int,
    attachment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    attachment = db.get(BugAttachment, attachment_id)
    if not attachment or attachment.bug_id != bug_id:
        raise HTTPException(status_code=404, detail="附件不存在")
    bug = db.get(Bug, bug_id)
    check_permission(db, current_user.id, bug.project_id, "attachment.view")
    from app.services.storage_service import generate_download_url
    url = generate_download_url(attachment.object_key, attachment.file_name)
    return RedirectResponse(url=url)


@router.delete("/{bug_id}/attachments/{attachment_id}")
def delete_attachment(
    bug_id: int,
    attachment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    attachment = db.get(BugAttachment, attachment_id)
    if not attachment or attachment.bug_id != bug_id:
        raise HTTPException(status_code=404, detail="附件不存在")
    bug = db.get(Bug, bug_id)
    check_permission(db, current_user.id, bug.project_id, "attachment.delete_own")
    if attachment.uploaded_by != current_user.id and not has_permission(db, current_user.id, bug.project_id, "attachment.delete_any"):
        raise HTTPException(status_code=403, detail="只有上传者或拥有删除他人附件权限的角色可删除")
    object_key = attachment.object_key
    db.delete(attachment)
    db.commit()
    # 同步删除 MinIO 对象，避免桶里积累孤儿文件
    from app.services.storage_service import remove_objects
    remove_objects([object_key])
    return {"ok": True}


class ImagePresignRequest(BaseModel):
    filename: str
    content_type: str


@images_router.post("/presign")
def presign_image_upload(
    payload: ImagePresignRequest,
    current_user: User = Depends(get_current_user),
):
    """
    富文本编辑器图片上传预签名。
    任意登录用户均可调用（无需项目权限，图片属于内容本身）。
    返回 upload_url（PUT 直传 MinIO）和 image_url（嵌入 img src 的可读 URL）。
    """
    from app.services.storage_service import generate_image_upload_presign
    try:
        return generate_image_upload_presign(payload.filename, payload.content_type)
    except ValueError as e:
        raise HTTPException(status_code=415, detail=str(e))


@images_router.get("/{object_key:path}")
def get_image(object_key: str):
    """
    富文本图片代理：每次读取实时生成新的预签名 GET URL 并 302 跳转，
    避免预签名 URL 过期后老 Bug / 用例里的截图 403 裂图。

    公开访问（<img> 标签无法携带 Authorization 头）；对象 key 为随机 UUID，
    不可枚举；仅放行 images/ 前缀，防止通过该端点读取附件等其他对象。
    """
    if not object_key.startswith("images/"):
        raise HTTPException(status_code=404, detail="图片不存在")
    from app.services.storage_service import generate_image_download_url
    url = generate_image_download_url(object_key)
    return RedirectResponse(url=url)
