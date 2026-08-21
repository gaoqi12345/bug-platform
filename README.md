# Bug Platform — 缺陷管理平台

一个基于 FastAPI + Vue 3 的轻量级缺陷管理系统，支持 Bug 全生命周期管理、RBAC 权限控制、测试用例管理、MinIO 文件存储和飞书通知。

## 技术栈

| 层次 | 技术 |
|------|------|
| 后端 | Python 3.11 · FastAPI · SQLAlchemy · Alembic · PostgreSQL |
| 前端 | Vue 3 · Vite · Element Plus · Pinia · Tiptap（富文本） |
| 存储 | MinIO（对象存储） |
| 部署 | Docker Compose · Nginx |

---

## 快速开始（Docker 部署，推荐）

### 前置条件

- [Docker](https://docs.docker.com/get-docker/) >= 20.10
- [Docker Compose](https://docs.docker.com/compose/install/) >= 2.0（通常随 Docker Desktop 一起安装）

### 第一步：克隆项目

```bash
git clone <仓库地址>
cd bug-platform
```

### 第二步：修改配置文件

打开 `backend/config.toml`，根据你的环境修改以下配置：

```toml
[database]
host     = "postgres"    # Docker 部署固定填 "postgres"，本地开发填 "localhost"
password = "bugpass"     # 修改为你的数据库密码

[minio]
external_endpoint = "192.168.1.100:9000"  # 改为宿主机 IP，浏览器需能访问

[app]
base_url = "http://192.168.1.100:8081"    # 改为宿主机 IP
```

> **最简部署**：如果只是本地体验，直接跳过此步骤，默认配置开箱即用。

### 第三步：启动所有服务

```bash
docker-compose up -d --build
```

首次启动会自动完成：
1. 拉取 PostgreSQL / MinIO 镜像
2. 构建后端和前端镜像
3. 等待数据库就绪
4. **自动运行 Alembic 数据库迁移**（建表）
5. 创建 MinIO 存储桶
6. **自动创建默认管理员账号**

### 第四步：验证启动

```bash
# 查看所有容器状态（全部应为 healthy）
docker-compose ps

# 查看后端启动日志
docker-compose logs backend
```

访问地址：

| 服务 | 地址 |
|------|------|
| **前端** | http://localhost:8081 |
| **API 文档** | http://localhost:8002/docs |
| **MinIO 控制台** | http://localhost:9001 |

### 默认账号

| 账号 | 密码 |
|------|------|
| `admin@bugplatform.com` | `Admin@123` |

MinIO 控制台默认账号：`minioadmin` / `minioadmin`（在 `backend/config.toml` 的 `[minio]` 节修改）

---

## 数据持久化说明

所有数据均通过 Docker named volumes 持久化，**`docker-compose down` 不会丢失数据**。

| 卷名 | 存储内容 | 说明 |
|------|---------|------|
| `pgdata` | PostgreSQL 数据库文件 | 所有业务数据：用户、项目、Bug、测试用例等 |
| `miniodata` | MinIO 对象存储文件 | Bug 附件、富文本图片等上传文件 |
| `backendlogs` | 后端应用日志 | JSON 格式结构化日志，按日轮转 |

查看卷在宿主机的实际位置：
```bash
docker volume inspect bug-platform_pgdata
```

---

## Docker 容器管理

### 启动 / 停止

```bash
# 启动所有服务（后台运行）
docker-compose up -d

# 停止所有服务（保留数据）
docker-compose down

# 重启单个服务
docker-compose restart backend

# 强制重新构建镜像并启动
docker-compose up -d --build
```

---

## 本地开发（Windows / macOS / Linux）

### 前置条件

- [uv](https://docs.astral.sh/uv/getting-started/installation/) — Python 包管理器（替代 pip + venv）
- Node.js 20+
- Docker Desktop（用于运行 PostgreSQL / MinIO）

**安装 uv：**
```bash
# Windows（PowerShell）
pip install uv
# 或
winget install astral-sh.uv

# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 启动步骤

**Windows：**

```bat
# 1. 启动依赖服务
docker-compose up -d postgres minio

# 2. 后端（uv 自动创建 .venv 并安装依赖）
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8002

# 3. 前端（新窗口）
cd frontend
npm install
npm run dev
```

**macOS / Linux：**

```bash
# 1. 启动依赖服务
docker-compose up -d postgres minio

# 2. 后端
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8002

# 3. 前端（新终端）
cd frontend
npm install
npm run dev
```

Windows 用户也可双击 `start.bat` 一键启动（自动完成 `uv sync` + 启动服务，需已运行过 `docker-compose up -d postgres minio` 至少一次）。

### 本地配置

后端读取 `backend/config.toml`，本地开发默认值开箱即用，无需修改：

```toml
[database]
host = "localhost"   # 本地开发用 localhost
port = 5432
user = "buguser"
password = "bugpass"

[minio]
endpoint = "localhost:9000"
external_endpoint = "localhost:9000"
```

> ⚠️ **MinIO 为必需组件**：Bug 附件与富文本截图均存储在 MinIO，本地开发需先启动
> `docker-compose up -d postgres minio`（不支持跳过 MinIO 的 mock 模式）。
>
> 富文本图片通过后端代理（`GET /api/v1/images/{key}`）展示，每次读取实时续签，
> 不会过期失效；前提是 `MINIO_EXTERNAL_ENDPOINT` 为浏览器可访问的地址。

---

## 项目结构

```
bug-platform/
├── backend/                  # FastAPI 后端
│   ├── app/
│   │   ├── api/v1/           # REST API 路由
│   │   ├── core/             # 配置、安全、RBAC、状态机
│   │   ├── models/           # SQLAlchemy 数据模型
│   │   ├── services/         # 业务逻辑（存储、通知）
│   │   └── db/migrations/    # Alembic 数据库迁移
│   ├── scripts/seed_demo.py  # ⭐ 演示数据重建脚本（清空并生成多项目/版本/Bug/用例）
│   ├── tests/                # 单元测试
│   ├── Dockerfile
│   ├── entrypoint.sh         # 容器启动脚本（迁移 + Gunicorn 启动）
│   ├── config.toml           # ⭐ 所有配置在这里，直接编辑即可
│   ├── pyproject.toml        # 项目依赖声明（uv 管理）
│   └── uv.lock               # 完整依赖锁文件（锁定所有传递依赖）
├── frontend/                 # Vue 3 前端
│   ├── src/
│   │   ├── api/              # API 封装
│   │   ├── stores/           # Pinia 状态管理
│   │   ├── utils/            # 权限工具函数
│   │   └── views/            # 页面组件
│   ├── Dockerfile
│   └── nginx.conf            # Nginx 配置（容器内使用）
├── docker-compose.yml        # 完整 Docker 部署配置
├── nginx.conf                # Nginx 配置原始文件
├── LICENSE
├── start.bat                 # Windows 本地开发一键启动脚本
└── stop.bat                  # Windows 本地开发停止脚本
```

---

## 主要功能

- **Bug 管理**：完整生命周期（NEW → ASSIGNED → IN_PROGRESS → RESOLVED → CLOSED），支持自定义流转规则
- **RBAC 权限**：内置 viewer / tester / developer / pm 四种角色，支持自定义角色和权限点
- **测试用例**：用例管理 + 执行记录，可与 Bug 关联
- **文件附件**：MinIO 预签名 URL 上传，支持图片预览
- **统计报表**：Bug 状态分布、人员工作量统计
- **跨项目视图**：顶部「当前项目」下拉支持「全部项目」模式，工作台 / Bug 列表 / 测试用例 / 统计报表联动按项目筛选
- **飞书通知**：Bug 指派时自动推送（可选）
- **邮件通知**：SMTP 邮件通知（可选）

---

## 演示数据

重新生成一套完整的演示数据（多项目 / 多版本 / Bug / 测试用例）：

```bash
cd backend
uv run --no-sync python scripts/seed_demo.py
```

> 脚本会清空并重建 `projects` / `versions` / `bugs` / `test_cases` 等项目域数据（固定随机种子，结果可复现）；用户、团队、RBAC 角色权限与系统配置不受影响。

---

## 运行测试

```bash
cd backend
# 运行全部测试（无需 PostgreSQL，使用 SQLite 内存库）
pytest tests/ -v

# 单独运行
pytest tests/test_transitions.py -v   # 状态机测试
pytest tests/test_permissions.py -v   # RBAC 权限测试
```

---

## 环境变量完整参考

| 变量 | 说明 | 默认值（开发） |
|------|------|--------------|
| `DATABASE_URL` | PostgreSQL 连接串 | `postgresql://buguser:bugpass@localhost:5432/bugplatform` |
| `SECRET_KEY` | JWT 签名密钥（**生产必须修改**） | `dev-secret-key-change-in-prod` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access Token 过期时间（分钟） | `60` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh Token 过期时间（天） | `7` |
| `MINIO_ENDPOINT` | MinIO 内网地址（后端直连） | `localhost:9000` |
| `MINIO_EXTERNAL_ENDPOINT` | MinIO 外网地址（浏览器预签名 URL） | `localhost:9000` |
| `MINIO_ACCESS_KEY` | MinIO 访问密钥 | `minioadmin` |
| `MINIO_SECRET_KEY` | MinIO 密钥 | `minioadmin` |
| `MINIO_SECURE` | MinIO 是否使用 HTTPS | `false` |
| `APP_BASE_URL` | 前端访问地址（飞书通知跳转） | `http://localhost:8081` |
| `LOG_LEVEL` | 日志级别（DEBUG/INFO/WARNING/ERROR） | `INFO` |
| `FEISHU_WEBHOOK_URL` | 飞书机器人 Webhook URL（留空禁用） | 空 |
| `FEISHU_WEBHOOK_SECRET` | 飞书签名密钥（可选） | 空 |
| `EMAIL_ENABLED` | 是否启用邮件通知 | `false` |
| `SMTP_HOST` | SMTP 服务器地址 | 空 |
| `SMTP_PORT` | SMTP 端口 | `465` |
| `SMTP_USER` | SMTP 用户名 | 空 |
| `SMTP_PASSWORD` | SMTP 密码 | 空 |

---

## 常见问题

**Q: `docker-compose up` 后后端一直重启？**

查看日志：`docker-compose logs backend`。常见原因：
- `.env.prod` 未创建 → `cp backend/.env.prod.example backend/.env.prod`
- `DATABASE_URL` 中 `CHANGE_ME` 未替换

**Q: 上传文件失败 / 图片无法显示？**

检查 `MINIO_EXTERNAL_ENDPOINT` 是否设置为浏览器可访问的地址（不能是 `minio:9000`，必须是宿主机 IP）。

**Q: 前端访问 API 报 CORS 错误？**

确认 `APP_BASE_URL` 与浏览器实际访问地址一致。

**Q: 想彻底重置，从零开始？**

```bash
docker-compose down -v   # 停止并删除所有数据卷
docker-compose up -d --build
```

---

## License

本项目基于 [MIT License](./LICENSE) 开源。
