# 源画像库 — 企业级智能网页采集管理平台

分布式网页采集系统，支持 10 种采集模板、LLM 智能规则生成、一键诊断修复、批量导入管理。

## 技术栈

| 组件 | 技术 |
|------|------|
| 管理后端 | Java 21 + Spring Boot 3 + MyBatis-Plus |
| 采集引擎 | Python 3.12 + httpx + Playwright + FastAPI |
| 管理前端 | Vue 3 + Ant Design Vue + Vite 6 |
| 基础设施 | MySQL 8 + Redis 6 + Prometheus + Grafana |

## 快速开始

### 环境要求

Docker 20+、Java 21+、Maven 3.9+、Python 3.11+、Node.js 20+、Git

### 1. 克隆代码

```bash
git clone https://github.com/hdlf7778/newcaiji.git
cd newcaiji
```

### 2. 配置环境变量

```bash
# Docker 基础服务配置
cd docker
cp .env.example .env
# 编辑 .env，将所有 CHANGE_ME 替换为实际密码
# 生成密码: openssl rand -base64 16
# 生成 JWT 密钥: openssl rand -base64 64

# Python Worker 配置
cd ../collector-worker
cp .env.example .env
# 编辑 .env，填入与 docker/.env 一致的数据库和 Redis 密码

# Java 后端配置
# 编辑 task-manager/src/main/resources/application-dev.yml
# 将密码改为与 docker/.env 一致的值
# 生成管理员密码哈希:
python3 -c "import bcrypt; print(bcrypt.hashpw(b'你的密码', bcrypt.gensalt(10)).decode())"
```

### 3. 启动基础服务

```bash
cd docker
docker compose up -d mysql redis
# 等待 ~30 秒，确认 healthy:
docker ps
```

### 4. 安装依赖

```bash
# Java
cd task-manager && mvn dependency:resolve -DskipTests && cd ..

# Python
cd collector-worker && pip3 install -r requirements.txt && cd ..

# 前端
cd web-admin && npm install && cd ..
```

### 5. 一键启动

```bash
chmod +x start.sh
./start.sh
```

或手动分终端启动：

```bash
# 终端1: Java 后端
cd task-manager && mvn spring-boot:run -Dspring-boot.run.profiles=dev

# 终端2: Python Worker API
cd collector-worker && python3 api_server.py

# 终端3: Python HTTP Worker
cd collector-worker && python3 worker.py --queue http

# 终端4: Vue 前端
cd web-admin && npx vite --host
```

### 6. 访问系统

| 服务 | 地址 |
|------|------|
| 管理平台 | http://localhost:5173 |
| 后端 API | http://localhost:8080 |
| Worker API | http://localhost:8001 |
| Grafana | http://localhost:3000 |

## 目录结构

```
newcaiji/
├── task-manager/          # Java 后端 (Spring Boot)
├── collector-worker/      # Python 采集引擎 (FastAPI + 10种模板)
├── web-admin/             # Vue 3 前端
├── database/              # SQL 初始化脚本（Docker 启动时自动导入）
├── docker/                # Docker Compose + Nginx + 监控配置
├── start.sh               # 一键启动脚本
├── INSTALL.md             # 详细安装部署指南
└── tools/                 # 辅助工具
```

## 核心功能

- **10 种采集模板**：静态 HTML、iframe、API 接口、微信公众号、SPA 渲染、政务云平台等
- **LLM 智能规则生成**：豆包大模型自动分析网页结构，生成 CSS 选择器规则
- **智能诊断修复**：一键修复失败的采集源（URL 重定向、模板切换、多策略轮换、LLM 深度分析）
- **人工辅助修复**：输入 F12 抓包线索，LLM 自动生成规则并试采
- **批量导入**：CSV/Excel 批量导入，自动表头识别，分批提交实时进度
- **采集调度**：工作时间 2h、非工作时间 4h 自动轮询，支持手动触发
- **监控告警**：Prometheus + Grafana 监控面板，仪表盘三色告警

## 开发指南

### 分支规范

```bash
# 创建功能分支
git checkout -b feature/你的功能名

# 开发完成后
git add .
git commit -m "feat: 功能描述"
git push origin feature/你的功能名

# 在 GitHub 创建 Pull Request 合并到 main
```

### 后端开发

```bash
cd task-manager
# 启动（dev 配置自动连接本地 MySQL:3307 + Redis:6379）
mvn spring-boot:run -Dspring-boot.run.profiles=dev

# 代码结构
src/main/java/com/collector/
├── controller/    # REST API 控制器
├── service/       # 业务逻辑
├── entity/        # 数据库实体
├── mapper/        # MyBatis-Plus Mapper
├── dto/           # 数据传输对象
├── config/        # Spring 配置
├── security/      # JWT 认证
└── scheduler/     # 定时任务
```

### 采集引擎开发

```bash
cd collector-worker
# 启动 API 服务
python3 api_server.py

# 启动 HTTP Worker
python3 worker.py --queue http

# 启动 Browser Worker（需 Playwright）
playwright install chromium
python3 worker.py --queue browser

# 代码结构
collector-worker/
├── api_server.py      # FastAPI 服务（检测/诊断/修复接口）
├── worker.py          # 采集 Worker 主进程
├── config.py          # 配置（从 .env 读取）
├── rule_detector.py   # LLM 规则检测
├── core/              # 核心模块（数据库/存储/队列/HTTP）
├── templates/         # 10 种采集模板实现
├── middleware/        # 反爬/验证码/附件
└── tests/             # 单元测试
```

### 前端开发

```bash
cd web-admin
# 启动开发服务器（自动代理 /api → localhost:8080）
npx vite --host

# 代码结构
src/
├── api/           # API 请求封装
├── views/         # 页面组件
├── router/        # 路由（含 RBAC 守卫）
├── stores/        # Pinia 状态管理
├── constants/     # 常量定义
├── composables/   # 组合式函数
└── utils/         # 工具函数
```

### 常用开发命令

```bash
# 重建数据库（清除所有数据）
cd docker && docker compose down -v && docker compose up -d mysql redis

# 查看 Java 日志
tail -f /tmp/task-manager.log

# 查看 Worker 日志
tail -f /tmp/worker-api.log

# 停止所有服务
./start.sh stop
```

## 详细文档

- **安装部署**：[INSTALL.md](INSTALL.md)
- **使用说明**：启动系统后访问 http://localhost:5173/guide
- **API 文档**：启动后访问 http://localhost:8001/docs（Worker FastAPI 自动文档）

## License

Private - All rights reserved.
