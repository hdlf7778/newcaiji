#!/bin/bash
# ============================================================
# 源画像库 — 一键启动脚本
#
# 使用方式：cd /Users/hd/Desktop/xincaiji/newcaiji && ./start.sh
# 停止方式：./start.sh stop
# ============================================================

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
JAVA_HOME="/usr/local/Cellar/openjdk@21/21.0.10/libexec/openjdk.jdk/Contents/Home"
PYTHON="/usr/local/bin/python3.12"

# 颜色
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# ---- 停止所有服务 ----
stop_all() {
    echo -e "${YELLOW}正在停止所有服务...${NC}"
    pkill -f "CollectorApplication" 2>/dev/null
    pkill -f "spring-boot:run" 2>/dev/null
    pkill -f "api_server.py" 2>/dev/null
    pkill -f "worker.py --queue" 2>/dev/null
    pkill -f "node.*vite" 2>/dev/null
    echo -e "${GREEN}所有服务已停止${NC}"
}

if [ "$1" = "stop" ]; then
    stop_all
    exit 0
fi

echo ""
echo "============================================"
echo "   源画像库 — 采集系统管理平台"
echo "============================================"
echo ""

# ---- Step 1: 检查 Docker 基础服务 ----
echo -e "${YELLOW}[1/5] 检查 Docker 基础服务（MySQL + Redis）...${NC}"
if ! docker ps | grep -q "collector-mysql"; then
    echo "  启动 Docker 服务..."
    cd "$ROOT_DIR/docker" && docker compose up -d mysql redis 2>/dev/null
    sleep 5
fi
if docker ps | grep -q "collector-mysql" && docker ps | grep -q "collector-redis"; then
    echo -e "  ${GREEN}✅ MySQL (3307) + Redis (6379) 运行中${NC}"
else
    echo -e "  ${RED}❌ Docker 服务启动失败，请检查 Docker 是否运行${NC}"
    exit 1
fi

# ---- Step 2: 启动 Java 后端 ----
echo -e "${YELLOW}[2/5] 启动 Java 后端（Spring Boot）...${NC}"
if pgrep -f "CollectorApplication" > /dev/null; then
    echo -e "  ${GREEN}✅ Java 后端已在运行${NC}"
else
    cd "$ROOT_DIR/task-manager"
    JAVA_HOME="$JAVA_HOME" nohup mvn spring-boot:run -Dspring-boot.run.profiles=dev --no-transfer-progress > /tmp/task-manager.log 2>&1 &
    echo "  等待启动..."
    for i in $(seq 1 20); do
        sleep 1
        if curl -s http://localhost:8080/actuator/health 2>/dev/null | grep -q "UP"; then
            echo -e "  ${GREEN}✅ Java 后端已启动 → http://localhost:8080${NC}"
            break
        fi
        if [ $i -eq 20 ]; then
            echo -e "  ${RED}❌ Java 后端启动超时，查看日志: tail -50 /tmp/task-manager.log${NC}"
        fi
    done
fi

# ---- Step 3: 启动 Python Worker API ----
echo -e "${YELLOW}[3/5] 启动 Python Worker API...${NC}"
if curl -s http://localhost:8001/health 2>/dev/null | grep -q "ok"; then
    echo -e "  ${GREEN}✅ Worker API 已在运行${NC}"
else
    cd "$ROOT_DIR/collector-worker"
    nohup $PYTHON api_server.py > /tmp/worker-api.log 2>&1 &
    sleep 3
    if curl -s http://localhost:8001/health 2>/dev/null | grep -q "ok"; then
        echo -e "  ${GREEN}✅ Worker API 已启动 → http://localhost:8001${NC}"
    else
        echo -e "  ${RED}❌ Worker API 启动失败，查看日志: tail -20 /tmp/worker-api.log${NC}"
    fi
fi

# ---- Step 4: 启动 Python HTTP Worker ----
echo -e "${YELLOW}[4/5] 启动 Python HTTP Worker...${NC}"
if pgrep -f "worker.py --queue http" > /dev/null; then
    echo -e "  ${GREEN}✅ HTTP Worker 已在运行${NC}"
else
    cd "$ROOT_DIR/collector-worker"
    nohup $PYTHON worker.py --queue http > /tmp/worker-http.log 2>&1 &
    sleep 2
    echo -e "  ${GREEN}✅ HTTP Worker 已启动${NC}"
fi

# ---- Step 5: 启动 Vue 前端 ----
echo -e "${YELLOW}[5/5] 启动 Vue 前端（Vite Dev Server）...${NC}"
if curl -s http://localhost:5173/ 2>/dev/null | grep -q "app"; then
    echo -e "  ${GREEN}✅ Vue 前端已在运行${NC}"
else
    cd "$ROOT_DIR/web-admin"
    nohup npx vite --host > /tmp/vite.log 2>&1 &
    sleep 5
    if curl -s http://localhost:5173/ 2>/dev/null | grep -q "app"; then
        echo -e "  ${GREEN}✅ Vue 前端已启动${NC}"
    else
        echo -e "  ${RED}❌ Vue 前端启动失败，查看日志: tail -20 /tmp/vite.log${NC}"
    fi
fi

# ---- 汇总 ----
echo ""
echo "============================================"
echo -e "  ${GREEN}系统已启动！${NC}"
echo ""
echo "  管理平台：http://localhost:5173"
echo "  账号：admin  密码：admin123"
echo ""
echo "  后端 API：http://localhost:8080"
echo "  Worker API：http://localhost:8001"
echo "  Grafana：http://localhost:3000"
echo ""
echo "  停止所有服务：./start.sh stop"
echo "============================================"
echo ""
