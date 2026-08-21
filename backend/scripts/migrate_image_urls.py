"""
migrate_image_urls.py — 存量富文本图片 URL 迁移 + 孤儿对象扫描

功能：
  1. 迁移（幂等，可重复运行）：把历史富文本 HTML 里内嵌的旧版预签名图片 URL
     （形如 http://host/bug-attachments/images/xxx.png?X-Amz-...）改写为永不过期的
     后端代理地址 /api/v1/images/images/xxx.png。
  2. 孤儿扫描：找出 MinIO bug-attachments/images/ 下未被任何富文本字段引用的对象，
     --delete 参数可一并清理（仅清理 images/ 前缀，不碰附件对象）。

用法：
    cd backend
    uv run --no-sync python scripts/migrate_image_urls.py          # 仅迁移
    uv run --no-sync python scripts/migrate_image_urls.py --scan   # 迁移 + 扫描孤儿
    uv run --no-sync python scripts/migrate_image_urls.py --delete # 迁移 + 扫描 + 删除孤儿
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.logging import get_logger  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402

logger = get_logger(__name__)

# 富文本字段清单（含图片可能出现的所有位置）
FIELDS = [
    ("bugs",       ["description", "steps_to_reproduce", "expected_result", "actual_result"]),
    ("test_cases", ["precondition", "steps", "expected_result"]),
    ("test_runs",  ["actual_result"]),
]

BUCKET = re.escape(settings.MINIO_BUCKET_ATTACHMENTS)

# 旧格式：任意 host + /bucket/images/{key} + 可选 query
OLD_URL_RE = re.compile(
    rf"(?:https?://[^\"'\s<]*)?/{BUCKET}/images/([A-Za-z0-9._/-]+?)(?:\?[^\"'\s<]*)?"
)


def migrate(db) -> int:
    """旧预签名 URL → 代理 URL，返回替换次数"""
    total = 0
    for table, cols in FIELDS:
        rows = db.execute(text(f"SELECT id, {', '.join(cols)} FROM {table}")).fetchall()
        for row in rows:
            new_vals = {}
            for col in cols:
                val = getattr(row, col)
                if not val:
                    continue
                new_val, n = OLD_URL_RE.subn(
                    lambda m: f"/api/v1/images/images/{m.group(1)}", val)
                if n:
                    new_vals[col] = new_val
                    total += n
            if new_vals:
                sets = ", ".join(f"{c} = :{c}" for c in new_vals)
                params = {c: v for c, v in new_vals.items()}
                params["id"] = row.id
                db.execute(text(f"UPDATE {table} SET {sets} WHERE id = :id"), params)
    return total


def collect_referenced_keys(db) -> set[str]:
    """从所有富文本字段收集被引用的图片对象 key（迁移后为代理格式）"""
    keys = set()
    ref_re = re.compile(
        rf"/api/v1/images/(images/[A-Za-z0-9._/-]+)"
        rf"|(?:https?://[^\"'\s<]*)?/{BUCKET}/images/([A-Za-z0-9._/-]+?)(?:\?[^\"'\s<]*)?"
    )
    for table, cols in FIELDS:
        rows = db.execute(text(f"SELECT {', '.join(cols)} FROM {table}")).fetchall()
        for row in rows:
            for col in cols:
                val = getattr(row, col)
                if val:
                    for m in ref_re.finditer(val):
                        keys.add(m.group(1) or m.group(2))
    return keys


def scan_orphans(db, delete: bool) -> list[str]:
    """扫描 images/ 前缀下未被引用的孤儿对象"""
    from minio import Minio
    client = Minio(
        settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_SECURE,
    )
    referenced = collect_referenced_keys(db)
    orphans = []
    for obj in client.list_objects(settings.MINIO_BUCKET_ATTACHMENTS,
                                   prefix="images/", recursive=True):
        if obj.object_name not in referenced:
            orphans.append(obj.object_name)
    for key in orphans:
        if delete:
            client.remove_object(settings.MINIO_BUCKET_ATTACHMENTS, key)
            logger.info("孤儿对象已删除", extra={"object_key": key})
        else:
            logger.info("孤儿对象", extra={"object_key": key})
    return orphans


def main():
    db = SessionLocal()
    try:
        n = migrate(db)
        db.commit()
        print(f"[迁移] 已改写 {n} 处旧预签名 URL → 代理 URL（幂等，可重复运行）")

        if "--scan" in sys.argv or "--delete" in sys.argv:
            orphans = scan_orphans(db, delete=("--delete" in sys.argv))
            action = "删除" if "--delete" in sys.argv else "发现"
            print(f"[扫描] {action} {len(orphans)} 个未被引用的孤儿图片对象")
            for k in orphans:
                print(f"    - {k}")
        else:
            print("[提示] 加 --scan 扫描孤儿对象，加 --delete 同时删除")
    finally:
        db.close()


if __name__ == "__main__":
    main()
