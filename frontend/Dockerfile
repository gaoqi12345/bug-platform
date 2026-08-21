# ============================================================
# Bug Platform — 前端镜像（构建 + Nginx 运行）
# 架构说明：
#   - 前端镜像内置 nginx：托管 Vue 静态文件 + 反代 /api/ 到后端
#   - docker run -p 8080:80 一条命令即用，无需独立 nginx 容器
#   - 若未来需要多服务网关，再引入独立 nginx 容器，本容器退役
# ============================================================

# 阶段1：构建
FROM docker.m.daocloud.io/library/node:20-alpine AS builder

WORKDIR /app

# 先复制依赖声明文件，利用 Docker 层缓存
COPY package*.json ./
RUN npm ci --registry=https://registry.npmmirror.com

# 复制源码并构建
COPY . .
RUN npm run build

# 阶段2：运行（nginx 托管静态 + 反代）
FROM docker.m.daocloud.io/library/nginx:alpine

# 复制构建产物
COPY --from=builder /app/dist /usr/share/nginx/html

# 复制 nginx 配置（nginx.conf 在 frontend/ 目录下）
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=10s --timeout=3s \
    CMD wget -qO- http://127.0.0.1/ || exit 1
