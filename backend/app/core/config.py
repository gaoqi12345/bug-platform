from pathlib import Path
import os

try:
    import tomllib          # Python 3.11+ 内置
except ImportError:
    import tomli as tomllib  # 3.10 及以下需安装 tomli

# config.toml 始终在 backend/ 目录下（config.py 上溯 3 层）
_CONFIG_FILE = Path(__file__).parent.parent.parent / "config.toml"

if not _CONFIG_FILE.exists():
    raise FileNotFoundError(
        f"配置文件不存在：{_CONFIG_FILE}\n"
        "请确认 backend/config.toml 存在（项目根目录下已提供默认配置）。"
    )

with open(_CONFIG_FILE, "rb") as f:
    _cfg = tomllib.load(f)

# 检测是否在 Docker 容器内运行
# entrypoint.sh 启动时会设置 RUNNING_IN_DOCKER=1
_IN_DOCKER = os.environ.get("RUNNING_IN_DOCKER") == "1"


def _section(name: str) -> dict:
    """
    读取配置节，Docker 环境下自动用 [docker.<name>] 覆盖。
    例如：_section("database") 在 Docker 内会把 [docker.database] 的值
    合并覆盖到 [database] 上，只覆盖有变化的键。
    """
    base = dict(_cfg.get(name, {}))
    if _IN_DOCKER:
        override = _cfg.get("docker", {}).get(name, {})
        base.update(override)
    return base


class _Settings:
    # 数据库
    @property
    def DATABASE_URL(self) -> str:
        db = _section("database")
        return (
            f"postgresql://{db['user']}:{db['password']}"
            f"@{db['host']}:{db['port']}/{db['name']}"
        )

    # JWT
    @property
    def SECRET_KEY(self) -> str:
        return _cfg["auth"]["secret_key"]

    @property
    def ACCESS_TOKEN_EXPIRE_MINUTES(self) -> int:
        return _cfg["auth"]["access_token_expire_minutes"]

    @property
    def REFRESH_TOKEN_EXPIRE_DAYS(self) -> int:
        return _cfg["auth"]["refresh_token_expire_days"]

    # MinIO
    @property
    def MINIO_ENDPOINT(self) -> str:
        return _section("minio")["endpoint"]

    @property
    def MINIO_EXTERNAL_ENDPOINT(self) -> str:
        return _section("minio")["external_endpoint"]

    @property
    def MINIO_ACCESS_KEY(self) -> str:
        return _cfg["minio"]["access_key"]

    @property
    def MINIO_SECRET_KEY(self) -> str:
        return _cfg["minio"]["secret_key"]

    @property
    def MINIO_SECURE(self) -> bool:
        return _cfg["minio"]["secure"]

    @property
    def MINIO_BUCKET_ATTACHMENTS(self) -> str:
        return _cfg["minio"]["bucket_attachments"]

    @property
    def MINIO_BUCKET_EXPORTS(self) -> str:
        return _cfg["minio"]["bucket_exports"]

    # 飞书
    @property
    def FEISHU_WEBHOOK_URL(self) -> str:
        return _cfg["feishu"]["webhook_url"]

    @property
    def FEISHU_WEBHOOK_SECRET(self) -> str:
        return _cfg["feishu"]["webhook_secret"]

    # 飞书自建应用（私聊消息 + 卡片回调需要；旧配置没有这些字段时回退为空）
    @property
    def FEISHU_APP_ID(self) -> str:
        return _cfg["feishu"].get("app_id", "")

    @property
    def FEISHU_APP_SECRET(self) -> str:
        return _cfg["feishu"].get("app_secret", "")

    @property
    def FEISHU_VERIFICATION_TOKEN(self) -> str:
        return _cfg["feishu"].get("verification_token", "")

    # 邮件
    @property
    def EMAIL_ENABLED(self) -> bool:
        return _cfg["email"]["enabled"]

    @property
    def SMTP_HOST(self) -> str:
        return _cfg["email"]["smtp_host"]

    @property
    def SMTP_PORT(self) -> int:
        return _cfg["email"]["smtp_port"]

    @property
    def SMTP_USER(self) -> str:
        return _cfg["email"]["smtp_user"]

    @property
    def SMTP_PASSWORD(self) -> str:
        return _cfg["email"]["smtp_password"]

    @property
    def SMTP_USE_SSL(self) -> bool:
        return _cfg["email"]["smtp_use_ssl"]

    @property
    def EMAIL_FROM_NAME(self) -> str:
        return _cfg["email"]["from_name"]

    # 应用
    @property
    def APP_BASE_URL(self) -> str:
        return _section("app")["base_url"]

    @property
    def LOG_LEVEL(self) -> str:
        return _cfg["app"]["log_level"]


settings = _Settings()
