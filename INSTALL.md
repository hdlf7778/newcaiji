# 源画像库 — 安装部署指南

## 一、环境要求

### 硬件要求
| 项目 | 最低配置 | 推荐配置 |
|------|---------|---------|
| CPU | 2 核 | 4 核 |
| 内存 | 4 GB | 8 GB |
| 磁盘 | 20 GB | 50 GB |

### 操作系统
- macOS 12+ (Intel/Apple Silicon)
- Ubuntu 20.04+ / CentOS 8+
- Windows 10+ (需使用 WSL2)

### 必需软件

| 软件 | 版本要求 | 用途 |
|------|---------|------|
| Docker | 20.x+ | 运行 MySQL、Redis |
| Docker Compose | v2.x+ | 编排基础服务 |
| Java (JDK) | 21+ | Spring Boot 后端 |
| Maven | 3.9+ | Java 构建工具 |
| Python | 3.11+ | 采集引擎 |
| Node.js | **20.19+** | Vue 前端 (Vite 6 要求) |
| npm | 9+ | 前端包管理 |
| Git | 2.x+ | 代码拉取 |

> **注意：** Vite 6 要求 Node.js 20.19+ 或 22.12+，Node 18 已不再支持。如使用 nvm 管理版本，请运行 `nvm install 20 && nvm use 20`。

---

## 二、安装步骤

### 2.1 安装基础软件

#### macOS (Homebrew)
```bash
# Docker（安装 Docker Desktop）
# 从 https://www.docker.com/products/docker-desktop/ 下载安装

# Java 21
brew install openjdk@21
echo 'export JAVA_HOME=$(brew --prefix openjdk@21)/libexec/openjdk.jdk/Contents/Home' >> ~/.zshrc
echo 'export PATH=$JAVA_HOME/bin:$PATH' >> ~/.zshrc
source ~/.zshrc

# Maven
brew install maven

# Python 3.12
brew install python@3.12

# Node.js 20+（如已有 nvm）
nvm install 20
nvm use 20

# 或直接安装
brew install node@20

# Git
brew install git
```

#### Ubuntu/Debian
```bash
# Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Java 21
sudo apt install -y openjdk-21-jdk
echo 'export JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64' >> ~/.bashrc

# Maven
sudo apt install -y maven

# Python 3.12
sudo apt install -y python3.12 python3.12-venv python3-pip

# Node.js 20+
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Git
sudo apt install -y git
```

#### Windows
1. 安装 [Docker Desktop](https://www.docker.com/products/docker-desktop/)（需启用 WSL2）
2. 安装 [JDK 21](https://adoptium.net/)（选择 Windows x64 .msi）
3. 安装 [Maven](https://maven.apache.org/download.cgi)
4. 安装 [Python 3.12](https://www.python.org/downloads/)（勾选 Add to PATH）
5. 安装 [Node.js 20+](https://nodejs.org/)（选择 LTS 版本）
6. 安装 [Git](https://git-scm.com/download/win)

### 2.2 克隆代码
```bash
git clone https://github.com/hdlf7778/newcaiji.git
cd newcaiji
```

### 2.3 配置环境变量

#### Docker 环境变量
```bash
cd docker
cp .env.example .env
```

编辑 `docker/.env` 文件，**必须修改**以下项（不要使用模板中的占位符）：

```bash
# 生成强密码（推荐使用以下命令）
openssl rand -base64 16   # 用于 DB_ROOT_PASSWORD / DB_PASSWORD / REDIS_PASSWORD
openssl rand -base64 64   # 用于 JWT_SECRET
```

| 变量 | 说明 | 示例 |
|------|------|------|
| `DB_ROOT_PASSWORD` | MySQL root 密码 | `MyStr0ng!P@ss` |
| `DB_PASSWORD` | 应用数据库密码（本地开发可与 root 相同） | `MyStr0ng!P@ss` |
| `REDIS_PASSWORD` | Redis 密码 | `RedisP@ss2026` |
| `JWT_SECRET` | JWT 签名密钥（**至少 64 字符**） | `openssl rand -base64 64` 的输出 |
| `GRAFANA_ADMIN_PASSWORD` | Grafana 管理密码 | `GrafanaP@ss` |
| `LLM_API_KEY` | 豆包大模型 API Key（可选，不填则 LLM 功能不可用） | 在火山引擎控制台获取 |

> **安全提示：** `.env` 文件包含敏感凭据，已在 `.gitignore` 中排除。切勿将其提交到 Git 仓库。

#### Python Worker 环境变量

```bash
cd ../collector-worker
cp .env.example .env
```

编辑 `collector-worker/.env`，确保密码与 `docker/.env` 一致：

```env
DB_HOST=localhost
DB_PORT=3307
DB_NAME=collector
DB_USERNAME=root
DB_PASSWORD=<与 docker/.env 中 DB_ROOT_PASSWORD 相同>

REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=<与 docker/.env 中 REDIS_PASSWORD 相同>

LLM_API_URL=https://ark.cn-beijing.volces.com/api/v3
LLM_API_KEY=<可选，与 docker/.env 相同>
LLM_MODEL=ep-20260328081539-wq277

HTTP_CONCURRENCY=5
METRICS_PORT=9091
```

> **注意：** 本地开发时 Python 连接 MySQL 使用 `localhost:3307`（Docker 映射端口），而非 `mysql:3306`（Docker 内部网络）。

#### Java 后端配置

本地开发使用 `application-dev.yml` 配置文件。如果你修改了 `docker/.env` 中的密码，也需要同步修改 `task-manager/src/main/resources/application-dev.yml` 中的对应值：

```yaml
spring:
  datasource:
    password: "<与 DB_ROOT_PASSWORD 相同>"
  data:
    redis:
      password: "<与 REDIS_PASSWORD 相同>"

collector:
  admin:
    password-hash: "<bcrypt 哈希，见下方说明>"
  jwt:
    secret: "<与 JWT_SECRET 相同>"
```

**生成管理员密码哈希：**
```bash
python3 -c "import bcrypt; print(bcrypt.hashpw(b'admin123', bcrypt.gensalt(10)).decode())"
```
将输出的 `$2b$10$...` 字符串填入 `password-hash` 字段。默认登录密码为 `admin123`，如需修改登录密码，将上述命令中的 `admin123` 替换为你的密码。

### 2.4 启动基础服务（MySQL + Redis）
```bash
cd docker
docker compose up -d mysql redis
```

等待约 10-30 秒，确认服务健康：
```bash
docker ps
# 应看到 collector-mysql (healthy) 和 collector-redis (healthy)
```

数据库表结构和初始数据会在 MySQL 首次启动时自动导入（通过 `docker-entrypoint-initdb.d` 挂载）。

### 2.5 安装 Java 后端依赖
```bash
cd ../task-manager
mvn dependency:resolve -DskipTests
```

### 2.6 安装 Python 依赖
```bash
cd ../collector-worker
pip3 install -r requirements.txt

# 安装 Playwright 浏览器（用于 SPA 渲染类采集）
playwright install chromium
```

### 2.7 安装前端依赖
```bash
cd ../web-admin
npm install
```

---

## 三、启动系统

### 方式一：一键启动（推荐）
```bash
cd /path/to/newcaiji
chmod +x start.sh
./start.sh
```

脚本会自动按顺序启动所有服务，完成后显示访问地址。

> **注意：** 一键启动脚本假设 Node.js 20+ 已安装。如使用 nvm，请先运行 `nvm use 20`。

### 方式二：手动逐个启动
```bash
# 终端 1：Java 后端
cd task-manager
JAVA_HOME=/path/to/java21 mvn spring-boot:run -Dspring-boot.run.profiles=dev

# 终端 2：Python Worker API
cd collector-worker
python3 api_server.py

# 终端 3：Python HTTP Worker
cd collector-worker
python3 worker.py --queue http

# 终端 4：Vue 前端（需 Node.js 20+）
cd web-admin
npx vite --host
```

### 方式三：Docker 全容器部署（生产环境）
```bash
cd docker
cp .env.example .env
# !! 必须编辑 .env，将所有 CHANGE_ME 替换为实际强密码 !!
docker compose up -d --build
```

生产环境注意事项：
- **必须**修改所有 `CHANGE_ME_*` 占位符为强密码
- **必须**设置真实的 `JWT_SECRET`（至少 64 字符随机字符串）
- MySQL 和 Redis 端口仅绑定到 `127.0.0.1`，不对外暴露
- Prometheus 端口不对外暴露（仅 Docker 内部网络访问）
- Grafana 端口仅绑定到 `127.0.0.1:3000`
- Nginx 已配置安全头（X-Frame-Options、X-Content-Type-Options 等）
- Actuator 端点除 `/actuator/health` 外均需认证
- 建议配置 HTTPS（通过 Nginx TLS 终止 + Let's Encrypt）

---

## 四、访问系统

| 服务 | 地址 | 说明 |
|------|------|------|
| 管理平台 | http://localhost:5173 | 本地开发地址 |
| 后端 API | http://localhost:8080 | Spring Boot |
| Worker API | http://localhost:8001 | Python FastAPI |
| Grafana 监控 | http://localhost:3000 | 密码见 `docker/.env` 中 `GRAFANA_ADMIN_PASSWORD` |

### 默认登录账号

| 服务 | 账号 | 密码 | 说明 |
|------|------|------|------|
| 管理平台 | `admin` | `admin123` | 可通过修改 `password-hash` 更改 |
| Grafana | `admin` | 见 `.env` | `GRAFANA_ADMIN_PASSWORD` |

> **安全提示：** 生产环境部署前请务必修改默认密码。

---

## 五、停止系统

```bash
# 一键停止所有本地服务
./start.sh stop

# 停止 Docker 基础服务
cd docker && docker compose down

# 停止并清除数据卷（谨慎：会删除所有数据）
cd docker && docker compose down -v
```

---

## 六、安全说明

本项目已实施以下安全措施：

### 认证与授权
- JWT 令牌认证，支持 HS512 签名
- 登录失败限频：同一 IP 5 次失败后锁定 15 分钟
- 前端路由级 RBAC 角色检查
- Actuator 敏感端点（metrics、prometheus、env）需认证访问

### 输入防护
- SSRF 防护：Java 后端和 Python Worker 均校验用户提供的 URL，拦截内网 IP、元数据端点
- SQL 注入防护：使用 MyBatis-Plus 参数化查询，表名白名单校验
- XSS 防护：前端使用 DOMPurify 消毒 HTML，外部链接协议校验
- 分页上限：所有列表接口 `pageSize` 限制为 200
- 文件上传限制：最大 10MB

### 基础设施
- MySQL / Redis 端口仅绑定 `127.0.0.1`，不对外暴露
- Prometheus 不暴露主机端口（仅 Docker 内部访问）
- Nginx 安全头：X-Frame-Options、X-Content-Type-Options、X-XSS-Protection、Referrer-Policy
- 登录接口 Nginx 限流：10 次/分钟
- Docker 容器以非 root 用户运行（task-manager、worker）
- `.dockerignore` 排除 `.env` 等敏感文件

### 凭据管理
- 所有密码通过环境变量注入，不硬编码在源码中
- `.env` 文件已加入 `.gitignore`
- `.env.example` 仅包含占位符，不含真实凭据
- 管理员密码使用 bcrypt 哈希存储

---

## 七、常见问题

### Q: Java 后端启动报 `characterEncoding` 错误
**A:** MySQL Connector J 9.x 不支持 `utf8mb4`，改为 `utf8`。确认使用 `application-dev.yml` 配置（启动时加 `-Dspring-boot.run.profiles=dev`）。

### Q: Java 后端启动报 `password-hash` 缺失
**A:** 检查 `application-dev.yml` 中的 `collector.admin.password-hash` 是否已填写。生成方法：
```bash
python3 -c "import bcrypt; print(bcrypt.hashpw(b'admin123', bcrypt.gensalt(10)).decode())"
```
如果缺少 `bcrypt` 包：`pip3 install bcrypt`

### Q: MySQL 容器不断重启（Restarting）
**A:** 常见原因：
1. `.env` 中 `DB_USERNAME` 设置为 `root` — 不要使用 `MYSQL_USER=root`（MySQL 官方镜像不允许）
2. 密码包含 Shell 特殊字符 — 避免使用 `$`、`'`、`"` 等字符，或用引号包裹

查看日志定位原因：`docker logs collector-mysql --tail 20`

### Q: Vue 前端启动报 `Node.js version` 错误
**A:** Vite 6 要求 Node.js 20.19+ 或 22.12+。升级方法：
```bash
# 使用 nvm
nvm install 20
nvm use 20

# 或使用 Homebrew
brew install node@20
```

### Q: Python 安装依赖报 `externally-managed-environment`
**A:** 这是 Homebrew Python 的限制，加 `--break-system-packages` 参数：
```bash
pip3 install -r requirements.txt --break-system-packages
```
或使用虚拟环境：
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Q: `npm install` 报网络错误
**A:** 切换镜像源：
```bash
npm config set registry https://registry.npmmirror.com
npm install
```

### Q: Docker MySQL 端口冲突（3306 已被占用）
**A:** 项目默认映射到 **3307** 端口（`docker-compose.yml` 中 `127.0.0.1:3307:3306`）。如果本机已有 MySQL 占用 3306 不影响。

### Q: 页面打开白屏
**A:** 按 `Cmd + Shift + R`（Mac）或 `Ctrl + Shift + R`（Windows）强制刷新清除浏览器缓存。

### Q: 登录后提示"您没有权限执行此操作"
**A:** 通常是 JWT 令牌过期或配置不一致导致。解决方法：
1. 清除浏览器 localStorage（开发者工具 → Application → Local Storage → 删除 token）
2. 确认 `application-dev.yml` 中的 `jwt.secret` 与生成 token 时一致
3. 重新登录

### Q: LLM 规则生成不可用
**A:** 需要配置豆包大模型 API Key。编辑 `collector-worker/.env` 和 `docker/.env`，填入 `LLM_API_KEY` 字段。未配置时自动检测和手动采集仍可使用，仅 LLM 智能规则生成功能不可用。

### Q: 模板管理页面报 500 错误
**A:** `custom_template` 表可能未创建。手动执行：
```bash
docker exec -i collector-mysql mysql -uroot -p<你的密码> collector -e "
CREATE TABLE IF NOT EXISTS custom_template (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  code VARCHAR(50) NOT NULL UNIQUE,
  base_template VARCHAR(50),
  description TEXT,
  default_list_rule JSON,
  default_detail_rule JSON,
  default_anti_bot JSON,
  default_platform_params JSON,
  enabled TINYINT DEFAULT 1,
  source_count INT DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
"
```

---

## 八、目录结构

```
newcaiji/
├── start.sh                  # 一键启动脚本
├── .dockerignore             # Docker 构建排除规则
├── database/                 # 数据库初始化脚本
│   ├── init.sql              # 表结构 + 分表 + 索引
│   └── sample-data.sql       # 测试数据（自动在 MySQL 首次启动时导入）
├── task-manager/             # Java 后端 (Spring Boot)
│   ├── pom.xml
│   └── src/
│       └── main/resources/
│           ├── application.yml       # 基础配置（环境变量占位符）
│           └── application-dev.yml   # 本地开发配置
├── collector-worker/         # Python 采集引擎
│   ├── worker.py             # 采集 Worker 主进程
│   ├── api_server.py         # FastAPI 检测服务
│   ├── requirements.txt      # Python 依赖
│   ├── .env.example          # 环境变量模板
│   ├── core/                 # 核心模块（数据库、存储、队列、HTTP）
│   ├── templates/            # 10 种采集模板
│   ├── middleware/            # 反爬/验证码/附件解析
│   └── tests/                # 单元测试
├── web-admin/                # Vue3 前端
│   ├── package.json
│   ├── vite.config.js        # Vite 配置（开发代理 → localhost:8080）
│   └── src/
│       ├── api/              # API 请求封装（Axios + JWT 拦截器）
│       ├── stores/           # Pinia 状态管理
│       ├── router/           # Vue Router（含 RBAC 路由守卫）
│       └── views/            # 页面组件
├── docker/                   # Docker 部署配置
│   ├── docker-compose.yml    # 服务编排
│   ├── .env.example          # 环境变量模板（所有值为占位符）
│   ├── nginx.conf            # Nginx 反向代理 + 安全头 + 限流
│   ├── Dockerfile.*          # 各服务 Dockerfile（非 root 运行）
│   ├── prometheus/           # Prometheus 监控配置
│   ├── grafana/              # Grafana 仪表盘 + 数据源
│   └── redis/                # Redis 配置
└── tools/                    # 辅助工具
```
