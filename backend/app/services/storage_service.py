import re
import uuid
from datetime import timedelta

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

ALLOWED_TYPES = {
    "image/png", "image/jpeg", "image/gif", "image/webp",
    "text/plain", "application/pdf", "application/zip",
    "application/octet-stream",
}

IMAGE_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp"}


def _get_client(external: bool = False):
    from minio import Minio
    endpoint = settings.MINIO_EXTERNAL_ENDPOINT if external else settings.MINIO_ENDPOINT
    return Minio(
        endpoint,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_SECURE,
    )


def generate_upload_presign(bug_id: int, filename: str, content_type: str) -> dict:
    if content_type not in ALLOWED_TYPES:
        raise ValueError(f"不支持的文件类型: {content_type}")

    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    object_key = f"bugs/{bug_id}/attachments/{uuid.uuid4()}.{ext}"

    # 使用外部地址生成预签名 URL，浏览器可直接 PUT
    client = _get_client(external=True)
    url = client.get_presigned_url(
        method="PUT",
        bucket_name=settings.MINIO_BUCKET_ATTACHMENTS,
        object_name=object_key,
        expires=timedelta(minutes=5),
    )
    return {
        "url": url,
        "object_key": object_key,
        "bucket": settings.MINIO_BUCKET_ATTACHMENTS,
    }


def generate_image_upload_presign(filename: str, content_type: str) -> dict:
    """
    富文本编辑器内嵌图片专用预签名接口（不绑定 bug_id）。
    上传后返回后端代理 URL（/api/v1/images/{key}），读取时实时续签，
    避免预签名 GET URL 过期导致老内容裂图。
    """
    if content_type not in IMAGE_TYPES:
        raise ValueError(f"不支持的图片类型: {content_type}，仅支持 PNG/JPEG/GIF/WebP")

    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "png"
    object_key = f"images/{uuid.uuid4()}.{ext}"

    client_ext = _get_client(external=True)

    # 预签名 PUT（上传用，5分钟有效）
    upload_url = client_ext.get_presigned_url(
        method="PUT",
        bucket_name=settings.MINIO_BUCKET_ATTACHMENTS,
        object_name=object_key,
        expires=timedelta(minutes=5),
    )

    # 展示用后端代理 URL（GET /api/v1/images/{key} 实时生成新预签名 URL）
    image_url = f"/api/v1/images/{object_key}"

    return {
        "upload_url": upload_url,
        "image_url":  image_url,
        "object_key": object_key,
    }


def generate_image_download_url(object_key: str) -> str:
    """富文本图片代理用：实时生成 1 小时预签名 GET URL（每次访问都续签）"""
    client = _get_client(external=True)
    return client.presigned_get_object(
        bucket_name=settings.MINIO_BUCKET_ATTACHMENTS,
        object_name=object_key,
        expires=timedelta(hours=1),
    )


def generate_download_url(object_key: str, filename: str) -> str:
    client = _get_client(external=True)
    return client.presigned_get_object(
        bucket_name=settings.MINIO_BUCKET_ATTACHMENTS,
        object_name=object_key,
        expires=timedelta(hours=1),
        response_headers={
            "response-content-disposition": f'inline; filename="{filename}"'
        },
    )


def remove_objects(object_keys: list[str]) -> None:
    """批量删除 MinIO 对象（删除 Bug/用例/附件时清理孤儿文件）。

    删除失败仅记录日志，不阻断主流程（DB 已提交，遗留对象可通过后续扫描清理）。
    """
    keys = {k for k in (object_keys or []) if k}
    if not keys:
        return
    client = _get_client(external=False)  # 服务端直连内网地址
    for key in keys:
        try:
            client.remove_object(
                bucket_name=settings.MINIO_BUCKET_ATTACHMENTS,
                object_name=key,
            )
            logger.info("MinIO 对象已删除", extra={"object_key": key})
        except Exception as e:
            logger.warning("MinIO 对象删除失败", extra={"object_key": key, "error": str(e)})


def extract_image_keys_from_html(html: str | None) -> list[str]:
    """从富文本 HTML 提取富文本图片对象 key（去重）。

    兼容两种 src 格式：
      - 后端代理：/api/v1/images/images/xxx.png
      - 旧版预签名：http://host/bug-attachments/images/xxx.png?X-Amz-...
    """
    if not html:
        return []
    bucket = re.escape(settings.MINIO_BUCKET_ATTACHMENTS)
    pattern = re.compile(
        rf"/api/v1/images/([A-Za-z0-9._/-]+?)(?=[?\"'\s<])"
        rf"|{bucket}/([A-Za-z0-9._/-]+?)(?=[?\"'\s<])"
    )
    keys = set()
    for m in pattern.finditer(html):
        keys.add(m.group(1) or m.group(2))
    return list(keys)
