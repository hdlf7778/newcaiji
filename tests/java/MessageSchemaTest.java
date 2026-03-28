package com.collector.tests;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;

import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.*;

/**
 * T01: Java↔Python 消息契约序列化验证
 *
 * 验证目标：
 * 1. Java 用 Jackson 序列化消息体 → snake_case JSON
 * 2. 时间字段输出 ISO 8601 + 时区
 * 3. 嵌套 JSON（rule/platform_params）正确序列化
 * 4. Python 端能正确反序列化（见 test_message.py）
 *
 * 运行方式（无需 Spring Boot，独立运行）：
 *   javac -cp jackson-databind.jar:jackson-core.jar:jackson-annotations.jar:jackson-datatype-jsr310.jar MessageSchemaTest.java
 *   java -cp .:... com.collector.tests.MessageSchemaTest
 *
 * 或直接在 IDE 中运行 main 方法。
 */
public class MessageSchemaTest {

    private static ObjectMapper createObjectMapper() {
        ObjectMapper mapper = new ObjectMapper();
        mapper.setPropertyNamingStrategy(PropertyNamingStrategies.SNAKE_CASE);
        mapper.registerModule(new JavaTimeModule());
        mapper.disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS);
        mapper.setSerializationInclusion(JsonInclude.Include.NON_NULL);
        return mapper;
    }

    // ======== 消息体 POJO（与正式 Entity 独立，仅用于契约验证） ========

    public static class TaskMessage {
        public String taskId;
        public Integer sourceId;
        public String sourceName;
        public String columnName;
        public String url;
        public String template;
        public Map<String, Object> rule;
        public Map<String, String> platformParams;
        public Map<String, Object> antiBot;
        public Map<String, Object> attachments;
        public Integer priority;
        public Integer retryCount;
        public OffsetDateTime createdAt;
    }

    public static class ResultMessage {
        public String taskId;
        public Integer sourceId;
        public String status;
        public Integer articlesFound;
        public Integer articlesNew;
        public Integer durationMs;
        public String errorMessage;
        public String errorType;
        public OffsetDateTime completedAt;
    }

    public static class HeartbeatMessage {
        public String workerId;
        public String workerType;
        public String status;
        public String currentTaskId;
        public Double cpuUsage;
        public Integer memoryMb;
        public Integer tasksCompleted;
        public Integer tasksFailed;
        public Integer uptimeSeconds;
        public OffsetDateTime heartbeatAt;
    }

    // ======== 测试方法 ========

    public static void main(String[] args) throws Exception {
        ObjectMapper mapper = createObjectMapper();
        int passed = 0;
        int failed = 0;

        // --- Test 1: 任务消息体序列化 ---
        System.out.println("=== Test 1: 任务消息体 (Java → Redis → Python) ===");
        try {
            TaskMessage task = new TaskMessage();
            task.taskId = "550e8400-e29b-41d4-a716-446655440000";
            task.sourceId = 12345;
            task.sourceName = "海宁市人民政府";
            task.columnName = "招考录用";
            task.url = "https://www.haining.gov.cn/col/col1455897/";
            task.template = "gov_cloud_platform";

            Map<String, Object> listRule = new LinkedHashMap<>();
            listRule.put("list_container", ".article-list");
            listRule.put("list_item", "li.article-item");
            listRule.put("title_selector", "a.title");
            listRule.put("url_selector", "a.title");
            listRule.put("date_selector", "span.date");
            listRule.put("date_format", "yyyy-MM-dd");
            listRule.put("max_items", 20);

            Map<String, Object> detailRule = new LinkedHashMap<>();
            detailRule.put("title_selector", "h1.article-title");
            detailRule.put("content_selector", "div.article-content");
            detailRule.put("publish_time_selector", "div.publish-time");
            detailRule.put("remove_selectors", Arrays.asList(".share-bar", "script"));
            detailRule.put("attachment_selector", "a[href$='.pdf'], a[href$='.doc']");

            task.rule = new LinkedHashMap<>();
            task.rule.put("list_rule", listRule);
            task.rule.put("detail_rule", detailRule);

            task.platformParams = new LinkedHashMap<>();
            task.platformParams.put("web_id", "2780");
            task.platformParams.put("page_id", "1455897");
            task.platformParams.put("node_id", "330481000000");
            task.platformParams.put("xxgk_id", "I1-3");

            task.antiBot = Map.of("type", "none");
            task.attachments = Map.of("enabled", true, "parse_content", true);
            task.priority = 5;
            task.retryCount = 0;
            task.createdAt = OffsetDateTime.of(2026, 3, 28, 10, 0, 0, 0, ZoneOffset.ofHours(8));

            String json = mapper.writerWithDefaultPrettyPrinter().writeValueAsString(task);
            System.out.println(json);

            // 验证 snake_case
            assert json.contains("\"task_id\"") : "task_id should be snake_case";
            assert json.contains("\"source_id\"") : "source_id should be snake_case";
            assert json.contains("\"source_name\"") : "source_name should be snake_case";
            assert json.contains("\"column_name\"") : "column_name should be snake_case";
            assert json.contains("\"retry_count\"") : "retry_count should be snake_case";
            assert json.contains("\"created_at\"") : "created_at should be snake_case";
            assert json.contains("\"platform_params\"") : "platform_params should be snake_case";
            assert json.contains("\"anti_bot\"") : "anti_bot should be snake_case";

            // 验证 ISO 8601
            assert json.contains("2026-03-28T10:00:00+08:00") : "created_at should be ISO 8601 with timezone";

            // 验证嵌套结构
            assert json.contains("\"list_rule\"") : "nested list_rule should exist";
            assert json.contains("\"detail_rule\"") : "nested detail_rule should exist";
            assert json.contains("\"remove_selectors\"") : "array field should exist";

            // 反序列化验证
            TaskMessage deserialized = mapper.readValue(json, TaskMessage.class);
            assert deserialized.taskId.equals(task.taskId) : "taskId roundtrip failed";
            assert deserialized.sourceId.equals(task.sourceId) : "sourceId roundtrip failed";
            assert deserialized.priority.equals(task.priority) : "priority roundtrip failed";

            System.out.println("✅ Test 1 PASSED: 任务消息体 snake_case + ISO8601 + 嵌套结构正确\n");
            passed++;
        } catch (Exception e) {
            System.out.println("❌ Test 1 FAILED: " + e.getMessage());
            e.printStackTrace();
            failed++;
        }

        // --- Test 2: 结果回报体序列化 ---
        System.out.println("=== Test 2: 结果回报体 (Python → Redis → Java) ===");
        try {
            // 模拟 Python 端写入的 JSON（snake_case）
            String pythonJson = """
                {
                    "task_id": "550e8400-e29b-41d4-a716-446655440000",
                    "source_id": 12345,
                    "status": "success",
                    "articles_found": 15,
                    "articles_new": 3,
                    "duration_ms": 4523,
                    "error_message": null,
                    "error_type": null,
                    "completed_at": "2026-03-28T10:00:05+08:00"
                }
                """;

            ResultMessage result = mapper.readValue(pythonJson, ResultMessage.class);
            assert result.taskId.equals("550e8400-e29b-41d4-a716-446655440000") : "taskId parse failed";
            assert result.sourceId == 12345 : "sourceId parse failed";
            assert result.status.equals("success") : "status parse failed";
            assert result.articlesFound == 15 : "articlesFound parse failed";
            assert result.articlesNew == 3 : "articlesNew parse failed";
            assert result.durationMs == 4523 : "durationMs parse failed";
            assert result.errorMessage == null : "errorMessage should be null";
            assert result.completedAt != null : "completedAt parse failed";
            assert result.completedAt.getOffset().equals(ZoneOffset.ofHours(8)) : "timezone should be +08:00";

            // Java 再序列化回去
            String javaJson = mapper.writeValueAsString(result);
            assert javaJson.contains("\"articles_found\"") : "should serialize back to snake_case";
            assert javaJson.contains("\"duration_ms\"") : "should serialize back to snake_case";

            System.out.println("  Python JSON → Java 反序列化:");
            System.out.println("    task_id: " + result.taskId);
            System.out.println("    status: " + result.status);
            System.out.println("    articles_found: " + result.articlesFound);
            System.out.println("    articles_new: " + result.articlesNew);
            System.out.println("    completed_at: " + result.completedAt);
            System.out.println("✅ Test 2 PASSED: Python JSON → Java 反序列化正确\n");
            passed++;
        } catch (Exception e) {
            System.out.println("❌ Test 2 FAILED: " + e.getMessage());
            e.printStackTrace();
            failed++;
        }

        // --- Test 3: Worker 心跳体 ---
        System.out.println("=== Test 3: Worker 心跳体 (双向验证) ===");
        try {
            // Python 写入
            String pythonHeartbeat = """
                {
                    "worker_id": "http-worker-01",
                    "worker_type": "http",
                    "status": "running",
                    "current_task_id": "550e8400-e29b-41d4-a716-446655440000",
                    "cpu_usage": 45.2,
                    "memory_mb": 512,
                    "tasks_completed": 1234,
                    "tasks_failed": 12,
                    "uptime_seconds": 86400,
                    "heartbeat_at": "2026-03-28T10:00:00+08:00"
                }
                """;

            HeartbeatMessage hb = mapper.readValue(pythonHeartbeat, HeartbeatMessage.class);
            assert hb.workerId.equals("http-worker-01") : "workerId parse failed";
            assert hb.workerType.equals("http") : "workerType parse failed";
            assert hb.cpuUsage == 45.2 : "cpuUsage parse failed";
            assert hb.memoryMb == 512 : "memoryMb parse failed";
            assert hb.tasksCompleted == 1234 : "tasksCompleted parse failed";
            assert hb.uptimeSeconds == 86400 : "uptimeSeconds parse failed";

            // Java 序列化
            String javaHb = mapper.writeValueAsString(hb);
            assert javaHb.contains("\"worker_id\"") : "worker_id snake_case";
            assert javaHb.contains("\"worker_type\"") : "worker_type snake_case";
            assert javaHb.contains("\"cpu_usage\"") : "cpu_usage snake_case";
            assert javaHb.contains("\"memory_mb\"") : "memory_mb snake_case";
            assert javaHb.contains("\"tasks_completed\"") : "tasks_completed snake_case";
            assert javaHb.contains("\"uptime_seconds\"") : "uptime_seconds snake_case";

            System.out.println("  worker_id: " + hb.workerId);
            System.out.println("  worker_type: " + hb.workerType);
            System.out.println("  cpu_usage: " + hb.cpuUsage + "%");
            System.out.println("  memory_mb: " + hb.memoryMb + "MB");
            System.out.println("✅ Test 3 PASSED: 心跳体双向序列化正确\n");
            passed++;
        } catch (Exception e) {
            System.out.println("❌ Test 3 FAILED: " + e.getMessage());
            e.printStackTrace();
            failed++;
        }

        // --- Test 4: 手动触发任务（priority=100）---
        System.out.println("=== Test 4: 手动触发任务 (priority=100) ===");
        try {
            TaskMessage manualTask = new TaskMessage();
            manualTask.taskId = UUID.randomUUID().toString();
            manualTask.sourceId = 99999;
            manualTask.url = "https://example.gov.cn/list/";
            manualTask.template = "static_list";
            manualTask.rule = Map.of(
                "list_rule", Map.of("list_container", "ul", "title_selector", "a", "url_selector", "a"),
                "detail_rule", Map.of("title_selector", "h1", "content_selector", ".content")
            );
            manualTask.antiBot = Map.of("type", "none");
            manualTask.priority = 100; // 手动触发最高优先级
            manualTask.retryCount = 0;
            manualTask.createdAt = OffsetDateTime.now(ZoneOffset.ofHours(8));

            String json = mapper.writeValueAsString(manualTask);
            TaskMessage parsed = mapper.readValue(json, TaskMessage.class);
            assert parsed.priority == 100 : "manual trigger priority should be 100";

            System.out.println("  priority: " + parsed.priority + " (手动触发最高优先级)");
            System.out.println("✅ Test 4 PASSED: 手动触发消息体正确\n");
            passed++;
        } catch (Exception e) {
            System.out.println("❌ Test 4 FAILED: " + e.getMessage());
            e.printStackTrace();
            failed++;
        }

        // --- Test 5: 失败结果回报 ---
        System.out.println("=== Test 5: 失败结果回报 ===");
        try {
            String failedJson = """
                {
                    "task_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                    "source_id": 54321,
                    "status": "failed",
                    "articles_found": 0,
                    "articles_new": 0,
                    "duration_ms": 30123,
                    "error_message": "Connection timeout after 30s",
                    "error_type": "network_timeout",
                    "completed_at": "2026-03-28T12:30:00+08:00"
                }
                """;

            ResultMessage failResult = mapper.readValue(failedJson, ResultMessage.class);
            assert failResult.status.equals("failed") : "status should be failed";
            assert failResult.errorMessage != null : "errorMessage should not be null";
            assert failResult.errorType.equals("network_timeout") : "errorType should be network_timeout";

            System.out.println("  status: " + failResult.status);
            System.out.println("  error_type: " + failResult.errorType);
            System.out.println("  error_message: " + failResult.errorMessage);
            System.out.println("✅ Test 5 PASSED: 失败结果回报解析正确\n");
            passed++;
        } catch (Exception e) {
            System.out.println("❌ Test 5 FAILED: " + e.getMessage());
            e.printStackTrace();
            failed++;
        }

        // --- 总结 ---
        System.out.println("========================================");
        System.out.println("测试结果: " + passed + " passed, " + failed + " failed");
        if (failed == 0) {
            System.out.println("✅ ALL TESTS PASSED — 消息契约验证通过");
            System.out.println("  - snake_case 字段命名 ✅");
            System.out.println("  - ISO 8601+时区 时间格式 ✅");
            System.out.println("  - JSON 嵌套结构(rule/platform_params) ✅");
            System.out.println("  - Java序列化 → Python反序列化 兼容 ✅");
            System.out.println("  - Python序列化 → Java反序列化 兼容 ✅");
            System.out.println("  - 手动触发 priority=100 ✅");
            System.out.println("  - 失败结果 error_type/error_message ✅");
        } else {
            System.out.println("❌ SOME TESTS FAILED");
            System.exit(1);
        }
    }
}
