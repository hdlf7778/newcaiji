"""
Prometheus 指标暴露 — /metrics 端点
"""
from prometheus_client import Counter, Histogram, Gauge, start_http_server

import config

# 采集维度
CRAWL_TASKS_TOTAL = Counter(
    "crawl_tasks_total", "采集任务总数", ["template", "status"]
)
CRAWL_DURATION = Histogram(
    "crawl_duration_seconds", "采集耗时", ["template"],
    buckets=[0.5, 1, 2, 5, 10, 20, 30, 60]
)
CRAWL_ARTICLES_NEW = Counter(
    "crawl_articles_new_total", "新增文章数", ["template"]
)

# 队列维度
QUEUE_PENDING = Gauge(
    "queue_pending_tasks", "待处理任务数", ["queue_type"]
)
QUEUE_PROCESSING = Gauge(
    "queue_processing_tasks", "处理中任务数"
)

# Worker 维度
WORKER_ACTIVE = Gauge(
    "worker_active_count", "活跃Worker数", ["worker_type"]
)
WORKER_MEMORY = Gauge(
    "worker_memory_bytes", "Worker内存使用", ["worker_id"]
)

# LLM 维度
LLM_DETECT_TOTAL = Counter(
    "llm_detect_total", "LLM检测调用数", ["status"]
)
LLM_DETECT_DURATION = Histogram(
    "llm_detect_duration_seconds", "LLM检测耗时",
    buckets=[1, 5, 10, 30, 60, 120]
)


# v1.0 新增: 调度维度
SCHEDULE_ROUND_TOTAL = Counter(
    "schedule_round_total", "调度轮次数", ["period"]  # work / off_hour / manual
)
SCHEDULE_ROUND_DURATION = Histogram(
    "schedule_round_duration_seconds", "每轮采集耗时",
    buckets=[60, 120, 300, 600, 1200, 1800, 3600, 7200]
)

# v1.0 新增: 反爬维度
ANTIBOT_ATTEMPTS_TOTAL = Counter(
    "antibot_attempts_total", "反爬尝试次数", ["tier", "status"]
    # tier: simple/captcha/tls/browser
    # status: success/failed
)

# v1.0 新增: 更新检测
UPDATE_CHECK_TOTAL = Counter(
    "update_check_total", "更新检测次数", ["result"]  # updated / skipped / error
)
UPDATE_CHECK_SKIP_RATE = Gauge(
    "update_check_skip_rate", "更新检测跳过率"
)


def start_metrics_server(port: int = None):
    """启动 Prometheus HTTP 服务"""
    port = port or config.METRICS_PORT
    start_http_server(port)
