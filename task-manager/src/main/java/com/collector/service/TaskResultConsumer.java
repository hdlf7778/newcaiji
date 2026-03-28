package com.collector.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.collector.entity.CollectorSource;
import com.collector.entity.CollectorTask;
import com.collector.mapper.CollectorSourceMapper;
import com.collector.mapper.CollectorTaskMapper;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;

@Component
@Slf4j
@RequiredArgsConstructor
public class TaskResultConsumer {

    private static final String QUEUE_RESULT         = "task:result";
    private static final String QUEUE_HTTP_PENDING   = "task:http:pending";
    private static final String QUEUE_BROWSER_PENDING = "task:browser:pending";
    private static final String QUEUE_DEAD           = "task:dead";
    private static final int    MAX_RETRY = 2;

    private final StringRedisTemplate redisTemplate;
    private final CollectorTaskMapper taskMapper;
    private final CollectorSourceMapper sourceMapper;
    private final ObjectMapper objectMapper;

    /**
     * 每2秒轮询一次 task:result 队列，消费 Python Worker 写入的采集结果。
     * 结果格式（snake_case）:
     * {"task_id":"uuid","source_id":123,"status":"success",
     *  "articles_found":15,"articles_new":3,"duration_ms":4523,
     *  "error_message":null,"completed_at":"ISO8601"}
     */
    @Scheduled(fixedDelay = 2000)
    public void consumeResults() {
        String raw = redisTemplate.opsForList().rightPop(QUEUE_RESULT);
        while (raw != null) {
            processResult(raw);
            raw = redisTemplate.opsForList().rightPop(QUEUE_RESULT);
        }
    }

    // ----------------------------------------------------------------- private

    private void processResult(String raw) {
        try {
            JsonNode node = objectMapper.readTree(raw);
            String taskId       = node.path("task_id").asText(null);
            int    sourceId     = node.path("source_id").asInt(0);
            String status       = node.path("status").asText("failed");
            int    articlesFound = node.path("articles_found").asInt(0);
            int    articlesNew   = node.path("articles_new").asInt(0);
            int    durationMs    = node.path("duration_ms").asInt(0);
            String errorMessage  = node.path("error_message").isNull() ? null : node.path("error_message").asText();
            String completedAtStr = node.path("completed_at").asText(null);

            LocalDateTime completedAt = completedAtStr != null
                    ? LocalDateTime.parse(completedAtStr, DateTimeFormatter.ISO_LOCAL_DATE_TIME)
                    : LocalDateTime.now();

            // Load task from DB
            CollectorTask task = taskMapper.selectOne(
                    new LambdaQueryWrapper<CollectorTask>().eq(CollectorTask::getTaskId, taskId));

            if (task == null) {
                log.warn("收到结果但任务不存在 taskId={}", taskId);
                return;
            }

            if ("success".equals(status) || "partial".equals(status)) {
                updateTaskSuccess(task, status, articlesFound, articlesNew, durationMs, completedAt);
                updateSourceSuccess(sourceId, articlesNew);
            } else {
                // failed / timeout
                int retryCount = task.getRetryCount() != null ? task.getRetryCount() : 0;
                if (retryCount < MAX_RETRY) {
                    requeue(task, raw, retryCount, errorMessage);
                } else {
                    updateTaskDead(task, errorMessage, completedAt);
                    updateSourceFail(sourceId);
                    redisTemplate.opsForList().leftPush(QUEUE_DEAD, raw);
                    log.error("任务重试耗尽，已移入死信队列 taskId={} sourceId={}", taskId, sourceId);
                }
            }
        } catch (Exception e) {
            log.error("处理任务结果失败 raw={}", raw, e);
        }
    }

    private void updateTaskSuccess(CollectorTask task, String status, int articlesFound,
                                    int articlesNew, int durationMs, LocalDateTime completedAt) {
        taskMapper.update(null, new LambdaUpdateWrapper<CollectorTask>()
                .eq(CollectorTask::getTaskId, task.getTaskId())
                .set(CollectorTask::getStatus, status)
                .set(CollectorTask::getArticlesFound, articlesFound)
                .set(CollectorTask::getArticlesNew, articlesNew)
                .set(CollectorTask::getDurationMs, durationMs)
                .set(CollectorTask::getErrorMessage, null)
                .set(CollectorTask::getCompletedAt, completedAt));
    }

    private void updateTaskDead(CollectorTask task, String errorMessage, LocalDateTime completedAt) {
        taskMapper.update(null, new LambdaUpdateWrapper<CollectorTask>()
                .eq(CollectorTask::getTaskId, task.getTaskId())
                .set(CollectorTask::getStatus, "dead")
                .set(CollectorTask::getErrorMessage, errorMessage)
                .set(CollectorTask::getCompletedAt, completedAt));
    }

    private void requeue(CollectorTask task, String originalMessage, int retryCount, String errorMessage) {
        String queueType = task.getQueueType();
        String queue = "browser".equals(queueType) ? QUEUE_BROWSER_PENDING : QUEUE_HTTP_PENDING;
        int priority = task.getPriority() != null ? task.getPriority() : 5;

        redisTemplate.opsForZSet().add(queue, originalMessage, priority);

        taskMapper.update(null, new LambdaUpdateWrapper<CollectorTask>()
                .eq(CollectorTask::getTaskId, task.getTaskId())
                .set(CollectorTask::getStatus, "pending")
                .set(CollectorTask::getRetryCount, retryCount + 1)
                .set(CollectorTask::getErrorMessage, errorMessage));

        log.info("任务已重新入队 taskId={} retry={}", task.getTaskId(), retryCount + 1);
    }

    private void updateSourceSuccess(int sourceId, int articlesNew) {
        if (sourceId <= 0) return;
        CollectorSource source = sourceMapper.selectById(sourceId);
        if (source == null) return;
        int total = (source.getTotalArticles() != null ? source.getTotalArticles() : 0) + articlesNew;
        sourceMapper.update(null, new LambdaUpdateWrapper<CollectorSource>()
                .eq(CollectorSource::getId, sourceId)
                .set(CollectorSource::getLastSuccessAt, LocalDateTime.now())
                .set(CollectorSource::getTotalArticles, total)
                .set(CollectorSource::getFailCount, 0));
    }

    private void updateSourceFail(int sourceId) {
        if (sourceId <= 0) return;
        CollectorSource source = sourceMapper.selectById(sourceId);
        if (source == null) return;
        int failCount = (source.getFailCount() != null ? source.getFailCount() : 0) + 1;
        sourceMapper.update(null, new LambdaUpdateWrapper<CollectorSource>()
                .eq(CollectorSource::getId, sourceId)
                .set(CollectorSource::getFailCount, failCount));
    }
}
