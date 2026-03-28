-- ============================================================
-- 源画像库 — 测试用示例数据
-- 10条采集源 + 对应规则，覆盖模板 A/I/B/C + 同网站多栏目
-- ============================================================

USE collector;

-- ============================================================
-- 采集源（10条，覆盖主力模板 + 同网站多栏目场景）
-- ============================================================
INSERT INTO collector_source (name, column_name, url, source_type, template, platform, platform_params, region, priority, status, health_score) VALUES
-- 模板 I: 政务云（36.8%，最高覆盖率）
('海宁市人民政府', '招考录用', 'https://www.haining.gov.cn/col/col1455897/', '事业单位', 'gov_cloud_platform', 'jpaas_zhejiang', '{"web_id":"2780","page_id":"1455897","node_id":"330481000000","xxgk_id":"I1-3"}', '浙江', 8, 'active', 95),
('海宁市人民政府', '公告公示', 'https://www.haining.gov.cn/col/col1455898/', '综合', 'gov_cloud_platform', 'jpaas_zhejiang', '{"web_id":"2780","page_id":"1455898","node_id":"330481000000","xxgk_id":"I1-4"}', '浙江', 6, 'active', 90),
('湖南省人社厅', '事业单位招聘', 'https://rst.hunan.gov.cn/xxgk/sydwgkzp/', '事业单位', 'gov_cloud_platform', NULL, NULL, '湖南', 8, 'active', 88),

-- 模板 A: 静态列表页（32.6%）
('南京市人社局', '通知公告', 'http://rsj.nanjing.gov.cn/njsrlzyhshbzj/tzgg/', '事业单位', 'static_list', NULL, NULL, '江苏', 7, 'active', 92),
('广西人才网', '招聘信息', 'http://www.gxrc.com/', '招聘', 'static_list', NULL, NULL, '广西', 6, 'active', 85),
('中国教育考试网', '公告', 'http://www.ceec.net.cn/', '教育', 'static_list', NULL, NULL, '全国', 7, 'active', 90),

-- 模板 C: API 接口型
('黑龙江事业单位招聘', '公开招聘', 'http://gkzp.renshenet.org.cn/', '事业单位', 'api_json', NULL, NULL, '黑龙江', 7, 'pending_detect', 100),

-- 模板 B: iframe 加载
('台江卫健人才网', '人才招聘', 'http://tj.dfwsrc.com/', '卫健', 'iframe_loader', 'dfwsrc', NULL, '福建', 5, 'pending_detect', 100),

-- 模板 F: 登录态/反爬（23.9%）
('某内部招聘平台', '社会招聘', 'https://hr.example-corp.com/jobs', '企业', 'auth_required', NULL, NULL, '全国', 4, 'pending_detect', 100),

-- 待检测（模拟批量导入后的状态）
('北京大学', '人才招聘', 'https://hr.pku.edu.cn/', '高校', 'static_list', NULL, NULL, '北京', 6, 'trial_passed', 100);


-- ============================================================
-- 采集规则（为已激活的源配置规则）
-- ============================================================

-- 海宁市-招考录用（模板I/JPAAS）
INSERT INTO collector_rule (source_id, list_rule, detail_rule, anti_bot_config, attachment_config, generated_by) VALUES
(1,
 '{"list_container":".xxgk_list ul","list_item":"li","title_selector":"a","url_selector":"a","date_selector":"span.date","date_format":"yyyy-MM-dd","max_items":20}',
 '{"title_selector":"h1","content_selector":".article","publish_time_selector":".ly span","remove_selectors":[".share-bar","script","style"]}',
 '{"type":"none"}',
 '{"enabled":true,"parse_content":true}',
 'platform');

-- 海宁市-公告公示（同平台复用规则结构）
INSERT INTO collector_rule (source_id, list_rule, detail_rule, anti_bot_config, attachment_config, generated_by) VALUES
(2,
 '{"list_container":".xxgk_list ul","list_item":"li","title_selector":"a","url_selector":"a","date_selector":"span.date","date_format":"yyyy-MM-dd","max_items":20}',
 '{"title_selector":"h1","content_selector":".article","publish_time_selector":".ly span","remove_selectors":[".share-bar","script","style"]}',
 '{"type":"none"}',
 '{"enabled":true,"parse_content":true}',
 'platform');

-- 湖南省人社厅（模板I）
INSERT INTO collector_rule (source_id, list_rule, detail_rule, anti_bot_config, attachment_config, generated_by) VALUES
(3,
 '{"list_container":".news_list","list_item":"li","title_selector":"a","url_selector":"a","date_selector":"span","date_format":"yyyy-MM-dd","max_items":20}',
 '{"title_selector":"h1","content_selector":".TRS_Editor","publish_time_selector":"span.time","remove_selectors":["script","style",".share"]}',
 '{"type":"none"}',
 '{"enabled":true,"parse_content":true}',
 'llm');

-- 南京市人社局（模板A）
INSERT INTO collector_rule (source_id, list_rule, detail_rule, anti_bot_config, attachment_config, generated_by) VALUES
(4,
 '{"list_container":"ul.news-list","list_item":"li","title_selector":"a","url_selector":"a","date_selector":"span.date","date_format":"yyyy-MM-dd","max_items":20}',
 '{"title_selector":"h1.article-title","content_selector":".contentBox","publish_time_selector":"span.publish-time","remove_selectors":["script","style"]}',
 '{"type":"none"}',
 '{"enabled":false}',
 'llm');

-- 广西人才网（模板A）
INSERT INTO collector_rule (source_id, list_rule, detail_rule, anti_bot_config, attachment_config, generated_by) VALUES
(5,
 '{"list_container":".job-list","list_item":"li","title_selector":"a.title","url_selector":"a.title","date_selector":"span.date","max_items":30}',
 '{"title_selector":"h1","content_selector":".job-detail","publish_time_selector":".info span","remove_selectors":["script","style",".ad"]}',
 '{"type":"none"}',
 '{"enabled":false}',
 'llm');

-- 中国教育考试网（模板A）
INSERT INTO collector_rule (source_id, list_rule, detail_rule, anti_bot_config, attachment_config, generated_by) VALUES
(6,
 '{"list_container":"ul.list","list_item":"li","title_selector":"a","url_selector":"a","date_selector":"span","date_format":"yyyy-MM-dd","max_items":20}',
 '{"title_selector":"h2","content_selector":".content","publish_time_selector":"p.info","remove_selectors":["script","style"]}',
 '{"type":"none"}',
 '{"enabled":true,"parse_content":true}',
 'llm');


-- ============================================================
-- 系统配置已在 init.sql 中初始化
-- ============================================================

-- 验证: 查看导入结果
SELECT '采集源统计' AS info, COUNT(*) AS total,
       SUM(status='active') AS active,
       SUM(status='pending_detect') AS pending,
       SUM(status='trial_passed') AS trial_passed
FROM collector_source;

SELECT '规则统计' AS info, COUNT(*) AS total,
       SUM(generated_by='platform') AS platform_rules,
       SUM(generated_by='llm') AS llm_rules
FROM collector_rule;

SELECT '分表验证' AS info, COUNT(*) AS detail_tables
FROM information_schema.tables
WHERE table_schema='collector' AND table_name LIKE 'article_detail_%';
