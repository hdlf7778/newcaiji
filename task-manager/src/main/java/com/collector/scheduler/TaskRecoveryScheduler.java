package com.collector.scheduler;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.collector.entity.CollectorTask;
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
import java.util.Map;
import java.util.Set;

@Component
@Slf4j
@RequiredArgsConstructor
public class TaskRecoveryScheduler {

    private static final String PROCESSING_HASH      = "task:processing";
    private static final String QUEUE_HTTP_PENDING   = "task:http:pending";
    private static final String QUEUE_BROWSER_PENDING = "task:browser:pending";
    private static final String QUEUE_DEAD           = "task:dead";
    private static final int    ZOMBIE_THRESHOLD_MINUTES = 10;
    private static final int    MAX_RESETS = 2;

    private final StringRedisTemplate redisTemplate;
    private final CollectorTaskMapper taskMapper;
    private final ObjectMapper objectMapper;

    /** 每分钟扫描处理中超时的任务（僵尸任务） */
    @Scheduled(fixedRate = 60000)
    public void recoverZombieTasks() {
        Map<Object, Object> processingEntries = redisTemplate.opsForHash().entries(PROCESSING_HASH);
        if (processingEntries.isEmpty()) {
            return;
        }

        LocalDateTime threshold = LocalDateTime.now().minusMinutes(ZOMBIE_THRESHOLD_MINUTES);
        int recovered = 0;
        int dead = 0;

        for (Map.Entry<Object, Object> entry : processingEntries.entrySet()) {
            String taskId = entry.getKey().toString();
            String messageJson = entry.getValue().toString();

            try {
                JsonNode node = objectMapper.readTree(messageJson);
                String startedAtStr = node.has("started_at") ? node.get("started_at").asText() : null;
                if (startedAtStr == null) {
                    continue;
                }

                LocalDateTime startedAt = LocalDateTime.parse(startedAtStr, DateTimeFormatter.ISO_LOCAL_DATE_TIME);
                if (!startedAt.isBefore(threshold)) {
                    continue;
                }

                // Zombie task found — remove from processing hash
                redisTemplate.opsForHash().delete(PROCESSING_HASH, taskId);

                // Check reset count from DB
                CollectorTask task = taskMapper.selectOne(
                        new LambdaQueryWrapper<CollectorTask>().eq(CollectorTask::getTaskId, taskId));

                if (task == null) {
                    log.warn("僵尸任务在数据库中未找到 taskId={}", taskId);
                    continue;
                }

                int retryCount = task.getRetryCount() != null ? task.getRetryCount() : 0;

                if (retryCount < MAX_RESETS) {
                    // Re-queue the task
                    String queueType = task.getQueueType();
                    String queue = "browser".equals(queueType) ? QUEUE_BROWSER_PENDING : QUEUE_HTTP_PENDING;
                    int priority = task.getPriority() != null ? task.getPriority() : 5;

                    redisTemplate.opsForZSet().add(queue, messageJson, priority);

                    // Update DB status back to pending, increment retry
                    taskMapper.update(null, new LambdaUpdateWrapper<CollectorTask>()
                            .eq(CollectorTask::getTaskId, taskId)
                            .set(CollectorTask::getStatus, "pending")
                            .set(CollectorTask::getRetryCount, retryCount + 1));

                    log.warn("僵尸任务已重新入队 taskId={} retryCount={}", taskId, retryCount + 1);
                    recovered++;
                } else {
                    // Mark as failed and push to dead letter queue
                    taskMapper.update(null, new LambdaUpdateWrapper<CollectorTask>()
                            .eq(CollectorTask::getTaskId, taskId)
                            .set(CollectorTask::getStatus, "dead")
                            .set(CollectorTask::getErrorMessage, "任务超时，重试次数已耗尽")
                            .set(CollectorTask::getCompletedAt, LocalDateTime.now()));

                    redisTemplate.opsForList().leftPush(QUEUE_DEAD, messageJson);

                    log.error("僵尸任务重试耗尽，已移入死信队列 taskId={}", taskId);
                    dead++;
                }
            } catch (Exception e) {
                log.error("处理僵尸任务失败 taskId={}", taskId, e);
            }
        }

        if (recovered > 0 || dead > 0) {
            log.info("僵尸任务恢复完成: recovered={} dead={}", recovered, dead);
        }
    }
}
