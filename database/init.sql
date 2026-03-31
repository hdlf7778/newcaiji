-- ============================================================
-- 源画像库 — 网站信息采集系统 数据库初始化脚本
-- 技术方案: v1.0
-- 数据库: MySQL 8.0, utf8mb4, InnoDB
-- ============================================================

CREATE DATABASE IF NOT EXISTS collector DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE collector;

-- ============================================================
-- 1. collector_source — 采集源（25个字段 + column_name）
-- ============================================================
CREATE TABLE collector_source (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '采集源ID',

    -- 基本信息
    name VARCHAR(300) NOT NULL COMMENT '网站名称',
    column_name VARCHAR(200) DEFAULT NULL COMMENT '栏目名称',
    url VARCHAR(2000) NOT NULL COMMENT '采集入口URL（列表页）',
    source_type VARCHAR(50) DEFAULT NULL COMMENT '来源分类（事业单位/卫健/教育等）',
    template VARCHAR(50) DEFAULT NULL COMMENT '模板类型: static_list/iframe_loader/api_json/wechat_article/search_discovery/auth_required/spa_render/rss_feed/gov_cloud_platform/captured_api（导入时为NULL，检测后自动设置）',
    platform VARCHAR(50) DEFAULT NULL COMMENT '政务云平台标识（如 jpaas_zhejiang）',
    platform_params JSON DEFAULT NULL COMMENT '平台参数（web_id/page_id/node_id等）',
    region VARCHAR(100) DEFAULT NULL COMMENT '地区（省/市）',
    priority TINYINT DEFAULT 5 COMMENT '优先级 1-100, 默认5, 100=手动触发最高',
    check_interval INT DEFAULT 7200 COMMENT '采集间隔（秒），默认7200（2小时）',
    encoding VARCHAR(20) DEFAULT 'utf-8' COMMENT '网站编码',

    -- 状态与统计
    status VARCHAR(30) DEFAULT 'pending_detect' COMMENT '状态: pending_detect/detecting/detected/detect_failed/trial/trial_passed/trial_failed/pending_review/approved/active/paused/error/retired',
    fail_count INT DEFAULT 0 COMMENT '连续失败次数',
    total_articles INT DEFAULT 0 COMMENT '累计采集文章数',
    last_success_at DATETIME DEFAULT NULL COMMENT '最后一次成功采集时间',
    last_article_date DATE DEFAULT NULL COMMENT '最近文章的发布日期',

    -- 试采与审批
    trial_score DECIMAL(3,2) DEFAULT NULL COMMENT '试采评分 0.00-1.00',
    trial_result JSON DEFAULT NULL COMMENT '试采详细结果（JSON）',
    trial_at DATETIME DEFAULT NULL COMMENT '最近试采时间',
    approved_by VARCHAR(50) DEFAULT NULL COMMENT '审批人',
    approved_at DATETIME DEFAULT NULL COMMENT '审批时间',

    -- 健康监控
    health_score INT DEFAULT 100 COMMENT '健康评分 0-100',
    avg_update_interval_hours DECIMAL(8,2) DEFAULT NULL COMMENT '平均更新间隔（小时）',
    quiet_days INT DEFAULT 0 COMMENT '静默天数（连续无新文章）',
    quiet_confirmed_at DATETIME DEFAULT NULL COMMENT '静默确认时间（人工确认该源正常静默）',

    -- 时间戳
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    -- 索引
    UNIQUE KEY uk_url_column (url(500), column_name) COMMENT 'URL+栏目联合唯一',
    KEY idx_status (status),
    KEY idx_template (template),
    KEY idx_platform (platform),
    KEY idx_region (region),
    KEY idx_health_score (health_score),
    KEY idx_priority (priority)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='采集源';


-- ============================================================
-- 2. collector_rule — 采集规则
-- ============================================================
CREATE TABLE collector_rule (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '规则ID',
    source_id INT NOT NULL COMMENT '采集源ID',

    -- 规则内容
    list_rule JSON NOT NULL COMMENT '列表页规则（CSS选择器: list_container/list_item/title_selector/url_selector/date_selector等）',
    detail_rule JSON NOT NULL COMMENT '详情页规则（CSS选择器: title_selector/content_selector/publish_time_selector/remove_selectors等）',

    -- 中间件配置
    anti_bot_config JSON DEFAULT NULL COMMENT '反爬配置（type/proxy_pool/cookie_url）',
    attachment_config JSON DEFAULT NULL COMMENT '附件配置（enabled/parse_content）',
    monitor_config JSON DEFAULT NULL COMMENT '页面监控配置',

    -- 版本管理
    rule_version INT DEFAULT 1 COMMENT '规则版本号',
    previous_rule_json JSON DEFAULT NULL COMMENT '上一版本规则备份（用于回滚）',

    -- 元信息
    generated_by VARCHAR(20) DEFAULT 'llm' COMMENT '规则生成方式: llm/manual/platform',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uk_source_id (source_id),
    KEY idx_generated_by (generated_by)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='采集规则';


-- ============================================================
-- 3. source_detect_queue — LLM 规则检测队列
-- ============================================================
CREATE TABLE source_detect_queue (
    id INT AUTO_INCREMENT PRIMARY KEY,
    source_id INT NOT NULL COMMENT '采集源ID',
    detect_type VARCHAR(20) DEFAULT 'full' COMMENT '检测类型: full/template_only/rule_only',
    status VARCHAR(20) DEFAULT 'pending' COMMENT '状态: pending/processing/completed/failed',
    priority INT DEFAULT 5 COMMENT '优先级',
    result JSON DEFAULT NULL COMMENT '检测结果',
    error_message TEXT DEFAULT NULL COMMENT '错误信息',
    retry_count INT DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME DEFAULT NULL,

    KEY idx_status (status),
    KEY idx_source_id (source_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='LLM规则检测队列';


-- ============================================================
-- 4. article_list — 文章列表（10个字段）
-- ============================================================
CREATE TABLE article_list (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '文章ID',
    source_id INT NOT NULL COMMENT '采集源ID',
    url VARCHAR(2000) NOT NULL COMMENT '文章详情页URL',
    url_hash VARCHAR(32) NOT NULL COMMENT 'URL的MD5哈希（用于去重）',
    title VARCHAR(500) NOT NULL COMMENT '文章标题',
    publish_date DATE DEFAULT NULL COMMENT '发布日期（标准化）',
    author VARCHAR(200) DEFAULT NULL COMMENT '作者/发布机构',
    summary VARCHAR(1000) DEFAULT NULL COMMENT '摘要',
    has_detail TINYINT(1) DEFAULT 0 COMMENT '是否已采集详情页 0=否 1=是',
    fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '采集时间',

    UNIQUE KEY uk_url_hash (url_hash),
    KEY idx_source_date (source_id, publish_date DESC),
    KEY idx_publish_date (publish_date DESC),
    KEY idx_fetched_at (fetched_at),
    KEY idx_has_detail (has_detail)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='文章列表';


-- ============================================================
-- 5. article_detail_{0~15} — 文章详情分表（13个字段）
--    路由规则: source_id % 16
-- ============================================================
DELIMITER //
CREATE PROCEDURE create_article_detail_tables()
BEGIN
    DECLARE i INT DEFAULT 0;
    WHILE i < 16 DO
        SET @sql = CONCAT(
            'CREATE TABLE IF NOT EXISTS article_detail_', i, ' (',
            '  id INT AUTO_INCREMENT PRIMARY KEY COMMENT ''详情ID'',',
            '  article_id INT NOT NULL COMMENT ''关联article_list.id'',',
            '  source_id INT NOT NULL COMMENT ''采集源ID'',',
            '  title VARCHAR(500) NOT NULL COMMENT ''文章标题'',',
            '  url VARCHAR(2000) NOT NULL COMMENT ''文章URL'',',
            '  content MEDIUMTEXT COMMENT ''正文纯文本'',',
            '  content_html MEDIUMTEXT COMMENT ''正文原始HTML'',',
            '  publish_time VARCHAR(100) DEFAULT NULL COMMENT ''原始发布时间文本'',',
            '  publish_date DATE DEFAULT NULL COMMENT ''标准化发布日期'',',
            '  author VARCHAR(200) DEFAULT NULL COMMENT ''作者'',',
            '  source_name VARCHAR(300) DEFAULT NULL COMMENT ''来源名称（冗余）'',',
            '  attachment_count INT DEFAULT 0 COMMENT ''附件数量'',',
            '  attachments JSON DEFAULT NULL COMMENT ''附件列表JSON'',',
            '  fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT ''采集时间'',',
            '  KEY idx_article_id (article_id),',
            '  KEY idx_source_id (source_id),',
            '  KEY idx_publish_date (publish_date DESC)',
            ') ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT=''文章详情分表_', i, ''''
        );
        PREPARE stmt FROM @sql;
        EXECUTE stmt;
        DEALLOCATE PREPARE stmt;
        SET i = i + 1;
    END WHILE;
END //
DELIMITER ;

CALL create_article_detail_tables();
DROP PROCEDURE IF EXISTS create_article_detail_tables;


-- ============================================================
-- 6. collector_task — 采集任务（13个字段）
-- ============================================================
CREATE TABLE collector_task (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '任务ID',
    task_id VARCHAR(36) NOT NULL COMMENT '任务UUID（贯穿全链路trace_id）',
    source_id INT NOT NULL COMMENT '采集源ID',
    template VARCHAR(50) NOT NULL COMMENT '模板类型',
    queue_type VARCHAR(20) NOT NULL COMMENT '队列类型: http/browser/priority',
    status VARCHAR(20) DEFAULT 'pending' COMMENT '状态: pending/processing/success/partial/failed/timeout/dead',
    priority INT DEFAULT 5 COMMENT '优先级',
    retry_count INT DEFAULT 0 COMMENT '已重试次数',
    articles_found INT DEFAULT 0 COMMENT '发现文章数',
    articles_new INT DEFAULT 0 COMMENT '新增文章数',
    duration_ms INT DEFAULT NULL COMMENT '采集耗时（毫秒）',
    error_message TEXT DEFAULT NULL COMMENT '错误信息',
    error_type VARCHAR(30) DEFAULT NULL COMMENT '错误类型: network_timeout/http_403/http_429/parse_error/template_mismatch/ssl_error/anti_bot_blocked',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '任务创建时间',
    started_at DATETIME DEFAULT NULL COMMENT '开始执行时间',
    completed_at DATETIME DEFAULT NULL COMMENT '完成时间',

    UNIQUE KEY uk_task_id (task_id),
    KEY idx_source_id (source_id),
    KEY idx_status (status),
    KEY idx_template (template),
    KEY idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='采集任务';


-- ============================================================
-- 7. dead_letter_queue — 死信队列（11个字段）
-- ============================================================
CREATE TABLE dead_letter_queue (
    id INT AUTO_INCREMENT PRIMARY KEY,
    task_id VARCHAR(36) NOT NULL COMMENT '原任务UUID',
    source_id INT NOT NULL COMMENT '采集源ID',
    template VARCHAR(50) NOT NULL COMMENT '模板类型',
    url VARCHAR(2000) NOT NULL COMMENT '采集URL',
    error_type VARCHAR(30) NOT NULL COMMENT '错误类型',
    error_message TEXT COMMENT '错误详情',
    retry_count INT DEFAULT 0 COMMENT '已重试次数',
    handle_status VARCHAR(20) DEFAULT 'pending' COMMENT '处理状态: pending/retried/ignored/reconfigured',
    handled_by VARCHAR(50) DEFAULT NULL COMMENT '处理人',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '进入死信时间',
    handled_at DATETIME DEFAULT NULL COMMENT '处理时间',

    KEY idx_source_id (source_id),
    KEY idx_handle_status (handle_status),
    KEY idx_error_type (error_type),
    KEY idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='死信队列';


-- ============================================================
-- 8. crawl_attachments — 附件解析结果
-- ============================================================
CREATE TABLE crawl_attachments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    article_id INT NOT NULL COMMENT '关联article_list.id',
    source_id INT NOT NULL COMMENT '采集源ID',
    detail_table_index TINYINT GENERATED ALWAYS AS (source_id % 16) STORED COMMENT '对应article_detail分表编号',
    file_name VARCHAR(500) COMMENT '附件文件名',
    file_url TEXT COMMENT '附件下载URL',
    file_type VARCHAR(20) COMMENT '文件类型: pdf/doc/docx/xls/xlsx',
    file_size INT COMMENT '文件大小（字节）',
    parsed_text MEDIUMTEXT COMMENT '解析出的文字内容',
    parsed_tables JSON COMMENT '解析出的表格数据',
    local_path TEXT COMMENT '本地存储路径（90天后清理文件，保留parsed_text）',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    KEY idx_article_id (article_id),
    KEY idx_source_id (source_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='附件解析结果';


-- ============================================================
-- 9. crawl_page_snapshots — 页面状态监控（30天保留）
-- ============================================================
CREATE TABLE crawl_page_snapshots (
    id INT AUTO_INCREMENT PRIMARY KEY,
    source_id INT NOT NULL COMMENT '采集源ID',
    page_hash VARCHAR(64) COMMENT '页面前2000字节MD5',
    keywords_found JSON COMMENT '检测到的关键词',
    content_changed TINYINT(1) DEFAULT 0 COMMENT '内容是否变化',
    snapshot_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    KEY idx_source_id (source_id),
    KEY idx_snapshot_at (snapshot_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='页面状态快照（30天保留）';


-- ============================================================
-- 10. collector_log — 采集日志（30天保留）
-- ============================================================
CREATE TABLE collector_log (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    source_id INT DEFAULT NULL COMMENT '采集源ID',
    task_id VARCHAR(36) DEFAULT NULL COMMENT '关联任务UUID',
    action VARCHAR(50) NOT NULL COMMENT '操作类型: crawl_success/crawl_failed/detect/trial/approve/reject/pause/resume/retire/reset',
    level VARCHAR(10) DEFAULT 'INFO' COMMENT '日志级别: INFO/WARN/ERROR',
    message TEXT COMMENT '日志内容',
    extra JSON DEFAULT NULL COMMENT '额外数据（结构化）',
    operator VARCHAR(50) DEFAULT NULL COMMENT '操作人（系统操作为null）',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    KEY idx_source_id (source_id),
    KEY idx_task_id (task_id),
    KEY idx_action (action),
    KEY idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='采集日志（30天保留）';


-- ============================================================
-- 11. worker_heartbeat — Worker 心跳
-- ============================================================
CREATE TABLE worker_heartbeat (
    id INT AUTO_INCREMENT PRIMARY KEY,
    worker_id VARCHAR(50) NOT NULL COMMENT 'Worker唯一标识',
    worker_type VARCHAR(20) NOT NULL COMMENT '类型: http/browser',
    status VARCHAR(20) DEFAULT 'running' COMMENT '状态: running/idle/stopping',
    current_task_id VARCHAR(36) DEFAULT NULL COMMENT '当前任务ID',
    cpu_usage DECIMAL(5,2) DEFAULT NULL COMMENT 'CPU使用率(%)',
    memory_mb INT DEFAULT NULL COMMENT '内存使用(MB)',
    tasks_completed INT DEFAULT 0 COMMENT '累计完成任务数',
    tasks_failed INT DEFAULT 0 COMMENT '累计失败任务数',
    uptime_seconds INT DEFAULT 0 COMMENT '运行时长(秒)',
    heartbeat_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后心跳时间',

    UNIQUE KEY uk_worker_id (worker_id),
    KEY idx_worker_type (worker_type),
    KEY idx_heartbeat_at (heartbeat_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Worker心跳';


-- ============================================================
-- 12. system_config — 系统配置
-- ============================================================
CREATE TABLE system_config (
    id INT AUTO_INCREMENT PRIMARY KEY,
    config_key VARCHAR(100) NOT NULL COMMENT '配置键',
    config_value TEXT NOT NULL COMMENT '配置值',
    description VARCHAR(500) DEFAULT NULL COMMENT '配置说明',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uk_config_key (config_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='系统配置';


-- ============================================================
-- 13. custom_template — 自定义采集模板
-- ============================================================
CREATE TABLE custom_template (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '自定义模板ID',
    name VARCHAR(100) NOT NULL COMMENT '模板显示名称',
    code VARCHAR(50) NOT NULL UNIQUE COMMENT '模板唯一编码',
    base_template VARCHAR(50) DEFAULT NULL COMMENT '继承的基础模板类型',
    description TEXT DEFAULT NULL COMMENT '模板说明',
    default_list_rule JSON DEFAULT NULL COMMENT '默认列表页采集规则',
    default_detail_rule JSON DEFAULT NULL COMMENT '默认详情页采集规则',
    default_anti_bot JSON DEFAULT NULL COMMENT '默认反爬策略配置',
    default_platform_params JSON DEFAULT NULL COMMENT '默认平台参数',
    enabled TINYINT DEFAULT 1 COMMENT '是否启用',
    source_count INT DEFAULT 0 COMMENT '使用此模板的数据源数量',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='自定义采集模板';


-- ============================================================
-- 初始系统配置（采集调度参数）
-- ============================================================
INSERT INTO system_config (config_key, config_value, description) VALUES
('schedule.work_hours', '08:00-20:00', '工作时间段'),
('schedule.work_interval', '7200', '工作时间采集间隔（秒）= 2小时'),
('schedule.off_interval', '14400', '非工作时间采集间隔（秒）= 4小时'),
('source.auto_approve_enabled', 'true', '是否开启自动审批'),
('source.auto_approve_threshold', '1.0', '自动审批最低分数阈值'),
('task.timeout', '30', '任务超时（秒）'),
('task.max_retry', '3', '最大重试次数'),
('task.connect_timeout', '7', '连接超时（秒）'),
('queue.alert_threshold', '5000', '队列积压告警阈值'),
('worker.heartbeat_interval', '30', 'Worker心跳间隔（秒）'),
('worker.http.concurrency', '15', 'HTTP Worker并发数'),
('worker.browser.concurrency', '5', 'Browser Worker并发数'),
('data.log_retention_days', '30', '日志保留天数'),
('data.snapshot_retention_days', '30', '快照保留天数'),
('data.attachment_file_retention_days', '90', '附件文件保留天数'),
('monitor.alert_channel', 'webhook', '告警通道'),
('llm.timeout', '120', 'LLM调用超时（秒）');
