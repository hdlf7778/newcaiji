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
| Node.js | 18+ | Vue 前端 |
| npm | 9+ | 前端包管理 |
| Git | 2.x+ | 代码拉取 |

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

# Node.js
brew install node

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

# Node.js 18+
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs

# Git
sudo apt install -y git
```

#### Windows
1. 安装 [Docker Desktop](https://www.docker.com/products/docker-desktop/)（需启用 WSL2）
2. 安装 [JDK 21](https://adoptium.net/)（选择 Windows x64 .msi）
3. 安装 [Maven](https://maven.apache.org/download.cgi)
4. 安装 [Python 3.12](https://www.python.org/downloads/)（勾选 Add to PATH）
5. 安装 [Node.js 18+](https://nodejs.org/)
6. 安装 [Git](https://git-scm.com/download/win)

### 2.2 克隆代码
```bash
git clone https://github.com/hdlf7778/newcaiji.git
cd newcaiji
```

### 2.3 启动基础服务（MySQL + Redis）
```bash
cd docker
cp .env.example .env
# 编辑 .env 文件，按需修改密码（默认可直接使用）
docker compose up -d mysql redis
```

等待约 10 秒，确认服务启动：
```bash
docker ps
# 应看到 collector-mysql 和 collector-redis 两个容器
```

### 2.4 初始化数据库
```bash
# 导入表结构和初始数据
docker exec -i collector-mysql mysql -u root -pcollector123 collector < ../database/init.sql
docker exec -i collector-mysql mysql -u root -pcollector123 collector < ../database/sample-data.sql
```

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

### 2.7 创建 Python 环境配置
```bash
# 在 collector-worker 目录下创建 .env 文件
cat > .env << 'EOF'
DB_HOST=localhost
DB_PORT=3307
DB_NAME=collector
DB_USERNAME=root
DB_PASSWORD=collector123

REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=collector_redis

LLM_API_URL=https://ark.cn-beijing.volces.com/api/v3
LLM_API_KEY=
LLM_MODEL=ep-20260328081539-wq277

HTTP_CONCURRENCY=5
METRICS_PORT=9091
EOF
```

### 2.8 安装前端依赖
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

# 终端 4：Vue 前端
cd web-admin
npx vite --host
```

### 方式三：Docker 全容器部署（生产环境）
```bash
cd docker
cp .env.example .env
# 编辑 .env 填入实际配置
docker compose up -d --build
```

---

## 四、访问系统

| 服务 | 地址 | 说明 |
|------|------|------|
| 管理平台 | http://localhost:5173 | 登录账号 `admin` / 密码 `admin123` |
| 后端 API | http://localhost:8080 | Spring Boot |
| Worker API | http://localhost:8001 | Python FastAPI |
| Grafana 监控 | http://localhost:3000 | 默认 admin/admin |
| Prometheus | http://localhost:9090 | 指标查询 |

---

## 五、停止系统

```bash
# 一键停止
./start.sh stop

# 或停止 Docker 服务
cd docker && docker compose down
```

---

## 六、常见问题

### Q: Java 后端启动报 `characterEncoding` 错误
**A:** MySQL Connector J 9.x 不支持 `utf8mb4`，改为 `utf8`。确认使用 `application-dev.yml` 配置（启动时加 `--spring.profiles.active=dev`）。

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
**A:** 项目默认映射到 **3307** 端口（`docker-compose.yml` 中 `3307:3306`）。如果本机已有 MySQL 占用 3306 不影响。

### Q: 页面打开白屏
**A:** 按 `Cmd + Shift + R`（Mac）或 `Ctrl + Shift + R`（Windows）强制刷新清除浏览器缓存。

### Q: LLM 规则生成不可用
**A:** 需要配置豆包大模型 API Key。编辑 `collector-worker/.env`，填入 `LLM_API_KEY` 字段。未配置时自动检测仍可使用，仅 LLM 智能生成功能不可用。

---

## 七、目录结构

```
newcaiji/
├── start.sh                  # 一键启动脚本
├── database/                 # 数据库初始化脚本
│   ├── init.sql              # 表结构 + 分表 + 索引
│   └── sample-data.sql       # 测试数据
├── task-manager/             # Java 后端 (Spring Boot)
│   ├── pom.xml
│   └── src/
├── collector-worker/         # Python 采集引擎
│   ├── worker.py             # 采集 Worker 主进程
│   ├── api_server.py         # FastAPI 检测服务
│   ├── requirements.txt      # Python 依赖
│   ├── core/                 # 核心模块
│   ├── templates/            # 10 种采集模板
│   ├── middleware/            # 反爬/验证码/附件解析
│   └── tests/                # 单元测试 (183 个)
├── web-admin/                # Vue3 前端
│   ├── package.json
│   ├── src/
│   └── tests/smoke.test.mjs  # E2E 冒烟测试
├── docker/                   # Docker 部署配置
│   ├── docker-compose.yml    # 9 个服务编排
│   ├── .env.example          # 环境变量模板
│   └── prometheus/grafana/   # 监控配置
└── tools/                    # 辅助工具
```
