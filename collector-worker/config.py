"""
全局配置 — 从环境变量读取，支持 .env 文件
"""
import os
from dotenv import load_dotenv

load_dotenv()


# Redis
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")
REDIS_DB = int(os.getenv("REDIS_DB", "0"))

# MySQL
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_NAME = os.getenv("DB_NAME", "collector")
DB_USERNAME = os.getenv("DB_USERNAME", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

# Redis 队列键名（与 Java 端消息契约一致）
QUEUE_HTTP_PENDING = "task:http:pending"
QUEUE_BROWSER_PENDING = "task:browser:pending"
QUEUE_PRIORITY = "task:priority"
QUEUE_PROCESSING = "task:processing"
QUEUE_DEAD = "task:dead"
QUEUE_RESULT = "task:result"
QUEUE_DETECT = "source:detect"

# Worker 配置
HTTP_CONCURRENCY = int(os.getenv("HTTP_CONCURRENCY", "15"))
BROWSER_CONCURRENCY = int(os.getenv("BROWSER_CONCURRENCY", "5"))
HEARTBEAT_INTERVAL = int(os.getenv("HEARTBEAT_INTERVAL", "30"))
TASK_TIMEOUT = int(os.getenv("TASK_TIMEOUT", "30"))
CONNECT_TIMEOUT = int(os.getenv("CONNECT_TIMEOUT", "7"))

# LLM
LLM_API_URL = os.getenv("LLM_API_URL", "https://ark.cn-beijing.volces.com/api/v3")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "doubao-1-5-pro-32k")
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "120"))

# Prometheus
METRICS_PORT = int(os.getenv("METRICS_PORT", "9090"))

# HTTP 请求默认头
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}
