from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.core.logging import setup_logging, get_logger

# ── 日志最先初始化 ─────────────────────────────────────────────
setup_logging(
    log_dir="logs",
    log_level=settings.LOG_LEVEL,
    app_name="bug-platform",
)
logger = get_logger(__name__)


def init_minio():
    """启动时确保 MinIO bucket 存在（MinIO 为必需组件，图片/附件均存储于此）"""
    try:
        from minio import Minio
        client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
        for bucket in [settings.MINIO_BUCKET_ATTACHMENTS, settings.MINIO_BUCKET_EXPORTS]:
            if not client.bucket_exists(bucket):
                client.make_bucket(bucket)
                logger.info("MinIO bucket 已创建", extra={"bucket": bucket})
    except Exception as e:
        logger.warning("MinIO 初始化失败，上传/图片功能将不可用", extra={"error": str(e)})


# ── 飞书 WebSocket 长连接客户端 ──────────────────────────────────
_ws_thread: "object | None" = None


def _start_feishu_ws():
    """
    启动飞书长连接（本地开发用，无需公网 URL）。
    前置条件：自建应用凭证已配置 + 私聊开关打开。未满足则跳过。
    lark-oapi 的 ws.Client.start() 为阻塞调用，必须放独立线程。
    """
    global _ws_thread
    try:
        from app.services.notify_service import _load_feishu_cfg
        cfg = _load_feishu_cfg()
        if not cfg.get("app_id") or not cfg.get("app_secret"):
            return
        if not cfg.get("private_notify_enabled"):
            logger.info("私聊通知未开启，跳过飞书长连接")
            return
        from app.api.v1.feishu_callback import build_ws_event_handler
        handler = build_ws_event_handler()
        if handler is None:
            return

        import threading
        import lark_oapi as lark
        from lark_oapi.ws import Client as LarkWsClient

        def _run():
            try:
                client = LarkWsClient(
                    app_id=cfg["app_id"],
                    app_secret=cfg["app_secret"],
                    event_handler=handler,
                    log_level=lark.LogLevel.WARNING,
                )
                logger.info("飞书长连接启动中…")
                client.start()  # 阻塞，断线自动重连
            except Exception as e:
                logger.error("飞书长连接异常退出: %s", e, exc_info=True)

        _ws_thread = threading.Thread(target=_run, daemon=True, name="feishu-ws")
        _ws_thread.start()
        logger.info("飞书长连接线程已启动", extra={"thread_name": "feishu-ws"})
    except Exception as e:
        logger.warning("飞书长连接启动失败（可忽略）: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Bug Platform 启动中…")
    init_minio()
    _start_feishu_ws()
    logger.info("Bug Platform 启动完成")
    yield
    logger.info("Bug Platform 已关闭")


app = FastAPI(
    title="Bug Platform API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── 全局异常 handler：捕获所有未处理的 500 错误 ───────────────
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error(
        "未处理异常",
        exc_info=exc,
        extra={
            "method": request.method,
            "url":    str(request.url),
            "client": request.client.host if request.client else None,
        },
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误，请联系管理员"},
    )


# ── 注册所有路由 ──────────────────────────────────────────────
from app.api.v1 import auth, users, teams, projects, versions, bugs, attachments, stats, testcases, config, roles, system, feishu_callback

app.include_router(auth.router,                  prefix="/api/v1")
app.include_router(users.router,                 prefix="/api/v1")
app.include_router(teams.router,                 prefix="/api/v1")
app.include_router(projects.router,              prefix="/api/v1")
app.include_router(versions.router,              prefix="/api/v1")
app.include_router(bugs.router,                  prefix="/api/v1")
app.include_router(attachments.router,           prefix="/api/v1")
app.include_router(attachments.images_router,    prefix="/api/v1")
app.include_router(stats.router,                 prefix="/api/v1")
app.include_router(testcases.router,             prefix="/api/v1")
app.include_router(testcases.all_cases_router,   prefix="/api/v1")
app.include_router(testcases.bug_cases_router,   prefix="/api/v1")
app.include_router(config.router,                prefix="/api/v1")
app.include_router(roles.router,                 prefix="/api/v1")
app.include_router(system.router,                prefix="/api/v1")
app.include_router(feishu_callback.router,       prefix="/api/v1")


@app.get("/health")
def health():
    return {"status": "ok"}
