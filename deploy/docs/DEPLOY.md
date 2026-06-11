# MediaRadar v2 — 部署指南

> 一份"从零到上线"的完整流程，目标读者：自己运维 MediaRadar 的同学。
>
> 预计阅读 + 部署时间：30 ~ 60 分钟（含 DNS 等待）。

---

## 目录

1. [前置要求](#1-前置要求)
2. [架构总览](#2-架构总览)
3. [域名与 DNS](#3-域名与-dns)
4. [服务器初始化](#4-服务器初始化)
5. [克隆代码与准备环境](#5-克隆代码与准备环境)
6. [配置 .env](#6-配置-env)
7. [一键部署](#7-一键部署)
8. [验证服务](#8-验证服务)
9. [回滚方案](#9-回滚方案)
10. [监控与日志](#10-监控与日志)
11. [数据备份与恢复](#11-数据备份与恢复)
12. [常见问题 FAQ](#12-常见问题-faq)

---

## 1. 前置要求

| 项目 | 最低 | 推荐 | 备注 |
|------|------|------|------|
| OS | Ubuntu 22.04 LTS | Ubuntu 24.04 LTS | 其他 Debian 系可类推 |
| CPU | 2 vCPU | 4 vCPU | Playwright 浏览器较吃 CPU |
| RAM | 2 GB | 4 GB | 主要消耗在 Chromium 启动时 |
| 存储 | 20 GB SSD | 40 GB SSD | 留 10 GB 给 Qdrant + 备份 |
| 带宽 | 5 Mbps | 20 Mbps | 取决于爬虫并发 |
| Docker | 24.0+ | 26.x | 需启用 compose v2 |
| 公网 IP | 1 个固定 IP | — | 家庭宽带请配置 DDNS |

### 安装 Docker

```bash
# Ubuntu 一键安装
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER    # 免 sudo 用 docker
newgrp docker
docker --version
docker compose version         # v2.x
```

### 开放端口

在云服务商安全组 / 防火墙放行：

- `80/tcp` — HTTP（Let's Encrypt 验证 + 自动 301 到 HTTPS）
- `443/tcp` — HTTPS（主流量）
- `22/tcp` — SSH（运维）
- 关闭 `8000`、`8080`、`6333` 等内部端口的公网访问（仅 localhost 即可）

---

## 2. 架构总览

```
                Internet
                   │
                   ▼
        ┌─────────────────────┐
        │  Cloud Firewall     │   放行 80/443/22
        └─────────┬───────────┘
                  ▼
        ┌─────────────────────┐
        │  Host Nginx         │   /etc/nginx/nginx.conf
        │  (port 80 + 443)    │   TLS 终止, gzip, security headers
        └─────────┬───────────┘
                  │
   ┌──────────────┴──────────────┐
   ▼                             ▼
┌─────────────────┐       ┌─────────────────┐
│  frontend       │       │  backend        │
│  (nginx:alpine) │       │  (FastAPI)      │
│  :8080          │       │  :8000          │
│  H5 static      │       │  /api/*         │
└─────────────────┘       └────────┬────────┘
                                   │
                                   ▼
                          ┌─────────────────┐
                          │  qdrant         │
                          │  :6333 (gRPC    │
                          │        :6334)   │
                          │  vector storage │
                          └─────────────────┘
```

- **Host nginx**：仅做 TLS 终止 + 反向代理，不跑业务。
- **Docker network**：`mediaradar-net`（bridge），服务间用服务名互访。
- **Volumes**：`mediaradar_backend_data` / `mediaradar_crawler_data` / `mediaradar_qdrant` / `mediaradar_logs`。
- **持久化**：`/var/lib/docker/volumes/...`（可用 NFS / 云盘外挂）。

---

## 3. 域名与 DNS

### 3.1 申请域名

在阿里云 / 腾讯云 / Cloudflare / Namecheap 等任意注册商购买。

### 3.2 配置 DNS 解析

在你的 DNS 服务商处添加两条 A 记录：

| 类型 | 主机记录 | 记录值 | TTL |
|------|---------|--------|-----|
| A | `radar` | `<服务器公网IP>` | 600 |
| A | `www.radar`（或暂不配） | `<服务器公网IP>` | 600 |

例如 `radar.example.com` 解析到 `203.0.113.10`。

### 3.3 等待 DNS 生效

```bash
# Linux / macOS
dig +short radar.example.com
nslookup radar.example.com

# Windows
nslookup radar.example.com
```

等待返回正确 IP（最长 24 小时，多数情况 5 分钟）。

---

## 4. 服务器初始化

```bash
# 4.1 创建部署用户（可选，但推荐）
sudo adduser mediaradar --disabled-password --gecos ""
sudo usermod -aG sudo,docker mediaradar
sudo -iu mediaradar

# 4.2 基础工具
sudo apt-get update && sudo apt-get install -y \
    curl wget git vim ufw certbot htop jq unzip

# 4.3 防火墙
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow http
sudo ufw allow https
sudo ufw enable

# 4.4 时区（影响 cron 续期时间）
sudo timedatectl set-timezone Asia/Shanghai
```

---

## 5. 克隆代码与准备环境

### 5.1 克隆项目

```bash
cd ~
git clone <your-git-repo-url> mediaradar
cd mediaradar
git checkout main          # 或指定的 release tag
```

> 如果是私有仓库，先在 `~/.ssh/config` 配置好 SSH key。

### 5.2 准备前端构建产物

前端 (`frontend/MiniApp`) 需要先构建为 H5 静态文件，放到 `frontend/web/`：

```bash
cd frontend/MiniApp
npm install
npm run build:h5            # 产物在 frontend/MiniApp/dist/build/h5
mkdir -p ../web
# uni-app 默认输出在 dist/build/h5，复制到 deploy 期望的位置
cp -r dist/build/h5/* ../web/
cd ../..
```

> 子代理 A 负责此步骤。也可以用任何 web 构建工具。

### 5.3 验证目录结构

```bash
ls deploy/                    # 应有 Dockerfile.backend / nginx / scripts / docs
ls frontend/web/index.html    # 必须存在
```

---

## 6. 配置 .env

```bash
cp .env.production.example .env
nano .env   # 或 vim / code 等
```

**必填项**：

- `DOMAIN` — 与 DNS 解析一致
- `ALLOWED_ORIGINS` — 你的真实域名
- `DEFAULT_API_KEY`（以及至少一个 `REVIEWER_API_KEY` / `EMBEDDING_API_KEY` / `VISION_API_KEY`）
- `API_KEYS` — 用 `openssl rand -hex 32` 生成
- `JWT_SECRET` — 用 `openssl rand -base64 48` 生成
- 至少一个推送通道（Wecom / Feishu / SMTP）

**生成密钥**：

```bash
openssl rand -hex 32          # 用于 API_KEYS
openssl rand -base64 48       # 用于 JWT_SECRET
```

完成后保存退出。

> 永远不要把真实 `.env` 提交到 git。它已经在 `.gitignore` 中。

---

## 7. 一键部署

```bash
# 一行命令：域名必须与 .env 中的 DOMAIN 一致
./deploy/scripts/deploy.sh radar.example.com --ssl
```

脚本会自动：

1. 检查 `docker`、`docker compose`、`.env`；
2. 同步 nginx 配置文件到 `/etc/nginx/conf.d/mediaradar.conf`；
3. 用 certbot 申请 Let's Encrypt 证书（首次部署）；
4. `docker compose pull && up -d --build`；
5. 等待后端 / Qdrant 健康；
6. 重新加载 host nginx。

> 首次部署会下载 Playwright Chromium 镜像 (~ 300MB) 和 Python 依赖，可能耗时 5 ~ 15 分钟。

---

## 8. 验证服务

### 8.1 容器状态

```bash
docker compose ps
```

应该看到 `mediaradar-backend` / `mediaradar-frontend` / `mediaradar-qdrant` 三个容器 `Up` 状态。

### 8.2 端到端检查

```bash
# HTTPS 跳转
curl -I http://radar.example.com
# 期望：HTTP/1.1 301 ... Location: https://...

# API 健康
curl -fsS https://radar.example.com/api/radar_status | jq .

# 主页 HTML
curl -fsS https://radar.example.com/ | head -20

# Qdrant (内部)
docker exec mediaradar-qdrant curl -s http://localhost:6333/readyz
# 期望：all shards are ready
```

### 8.3 浏览器访问

打开 `https://radar.example.com`，应看到 MediaRadar 首页。点击"启动扫描"测试一次端到端。

---

## 9. 回滚方案

### 9.1 代码回滚

```bash
cd ~/mediaradar
git log --oneline -10            # 找上一个稳定版本
git checkout <stable-tag>
./deploy/scripts/deploy.sh radar.example.com
```

> 注意：如果 schema 改了，可能要手动迁移数据库。先停 scheduler：

```bash
docker compose exec backend python -c "from services.radar_service.scheduler import scheduler_stop; print(scheduler_stop())"
```

### 9.2 数据回滚

```bash
ls -la ~/mediaradar/backups/         # 找最近的备份
tar -xzf mediaradar_<TIMESTAMP>.tar.gz
# 按需把数据卷 cp 回去，然后重启容器：
docker compose down
docker volume rm mediaradar_backend_data
docker volume create mediaradar_backend_data
docker run --rm -v mediaradar_backend_data:/dst -v $PWD/backend_data:/src alpine cp -a /src/. /dst/
docker compose up -d
```

### 9.3 紧急停机

```bash
docker compose down              # 停止所有服务但保留 volumes
docker compose down -v           # 危险：连数据一起删
```

---

## 10. 监控与日志

### 10.1 实时日志

```bash
# 所有服务
docker compose logs -f --tail 200

# 单独服务
docker compose logs -f backend
docker compose logs -f qdrant

# Host nginx
sudo tail -f /var/log/nginx/access.log /var/log/nginx/error.log

# 容器内应用日志
docker exec mediaradar-backend tail -f /app/logs/gateway.log
```

### 10.2 Prometheus 指标

后端暴露 `/metrics`（如果启用了 `prometheus_client`），可在 host nginx 加白名单或内网访问：

```nginx
location /metrics {
    allow 127.0.0.1;
    allow 10.0.0.0/8;
    deny all;
    proxy_pass http://mediaradar_backend;
}
```

### 10.3 健康检查

| 端点 | 检查项 |
|------|--------|
| `https://radar.example.com/api/radar_status` | 雷达服务 |
| `https://radar.example.com/openapi.json` | 后端存活 |
| `http://127.0.0.1:6333/readyz` | Qdrant |

建议在 UptimeRobot / 阿里云监控 / StatusCake 等接入。

---

## 11. 数据备份与恢复

### 11.1 自动备份

```bash
# 手动跑一次
./deploy/scripts/backup.sh

# 推到 S3（需先配 BACKUP_S3_BUCKET）
./deploy/scripts/backup.sh --s3
```

**加入 crontab 每日 02:30 备份**：

```bash
(crontab -l 2>/dev/null; echo "30 2 * * * /home/mediaradar/mediaradar/deploy/scripts/backup.sh --s3 >> /var/log/mediaradar-backup.log 2>&1") | crontab -
```

### 11.2 恢复

参见 [9.2 数据回滚](#92-数据回滚)。

### 11.3 备份内容

`mediaradar_<timestamp>.tar.gz` 包含：

- `backend_data/` — SQLite 数据库
- `backend_crawler_data/` — 登录 cookies
- `qdrant_storage/` — 向量索引
- `backend_logs/` — 应用日志
- `manifest.txt` — 元信息

---

## 12. 常见问题 FAQ

### Q1. certbot 申请证书失败 "Connection refused"

A: 80 端口被占用。先停 nginx：

```bash
sudo systemctl stop nginx
sudo certbot certonly --standalone -d radar.example.com
```

或加 `--http-01-port 8080`（需先在 nginx 转发 ACME 路径）。

### Q2. 部署后前端 502

A: 99% 是 `frontend/web/` 为空。先把构建产物放进去：

```bash
cd frontend/MiniApp && npm run build:h5
mkdir -p ../web && cp -r dist/build/h5/* ../web/
cd ../.. && docker compose restart frontend
```

### Q3. 后端一直在重启

```bash
docker compose logs --tail 100 backend
```

最常见原因：
- `.env` 缺 LLM API key → 加上后重启
- 端口被占 → `lsof -i :8000` 找出占用进程
- Playwright 浏览器下载失败 → 重建镜像 `docker compose build --no-cache backend`

### Q4. Qdrant 数据丢了

A: 容器外的 named volume `mediaradar_qdrant` 应被保留。可用 `backup.sh` + `restore` 还原。如果 `docker compose down -v` 被误执行，那就**永久丢失**了。

### Q5. 如何切换域名

```bash
# 1. 改 .env 的 DOMAIN
# 2. 重新跑 deploy（会重新签发证书）：
./deploy/scripts/deploy.sh new.example.com --ssl
```

### Q6. 内存爆了

```bash
docker stats           # 看各容器占用
free -h                # 主机内存
```

Qdrant 默认吃 ~300 MB，backend ~500 MB ~ 1 GB（Playwright 启动 Chromium 时）。如果 host 只有 2 GB，建议关闭 Playwright 自动登录（仅用 cookie 持久化），或加 swap：

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### Q7. 如何升级到新版本

```bash
cd ~/mediaradar
git pull
./deploy/scripts/deploy.sh radar.example.com
```

> 数据卷不会被重建，升级是滚动式的。如果 backend image 改了端口或路径，先 `docker compose down`。

### Q8. docker compose 报 "version is obsolete"

A: 删掉 `docker-compose.yml` 顶部的 `version: '3.x'` 行（YAML 2.x 已不需要）。

---

## 附录 A：目录速查

```
mediaradar/
├── backend/                     # FastAPI 后端
│   ├── gateway/main.py
│   ├── services/...
│   └── data/                    # SQLite (持久化卷)
├── frontend/
│   └── web/                     # H5 构建产物（必备）
├── deploy/
│   ├── Dockerfile.backend
│   ├── nginx/
│   │   ├── nginx.conf
│   │   ├── conf.d/mediaradar.conf
│   │   └── frontend.conf
│   ├── scripts/
│   │   ├── deploy.sh
│   │   ├── ssl-init.sh
│   │   └── backup.sh
│   └── docs/DEPLOY.md           # 本文档
├── docker-compose.yml
├── .env                         # 真实环境变量（不入 git）
├── .env.production.example
└── requirements.txt
```

## 附录 B：关键运维命令

```bash
# 启停
docker compose up -d
docker compose stop
docker compose down
docker compose restart backend

# 调试
docker compose exec backend bash
docker compose logs -f --tail 200 backend
docker stats

# 清理（危险）
docker system prune -a              # 删所有未用镜像
docker volume prune                 # 删未用卷（会丢数据！）
```

## 附录 C：联系 / 升级

- 项目仓库：见 README.md
- 升级前请阅读 `CHANGELOG.md` 中的 `BREAKING CHANGES` 段
