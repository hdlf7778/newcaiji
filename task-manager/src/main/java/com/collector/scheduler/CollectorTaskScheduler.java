package com.collector.scheduler;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.collector.config.ScheduleConfig;
import com.collector.entity.CollectorRule;
import com.collector.entity.CollectorSource;
import com.collector.entity.CollectorTask;
import com.collector.enums.SourceStatus;
import com.collector.mapper.CollectorRuleMapper;
import com.collector.mapper.CollectorSourceMapper;
import com.collector.mapper.CollectorTaskMapper;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@Component
@Slf4j
@RequiredArgsConstructor
public class CollectorTaskScheduler {

    private static final String QUEUE_HTTP_PENDING     = "task:http:pending";
    private static final String QUEUE_BROWSER_PENDING  = "task:browser:pending";
    private static final String QUEUE_PRIORITY         = "task:priority";

    private final CollectorSourceMapper sourceMapper;
    private final CollectorTaskMapper taskMapper;
    private final CollectorRuleMapper ruleMapper;
    private final StringRedisTemplate redisTemplate;
    private final ScheduleConfig scheduleConfig;
    private final ObjectMapper objectMapper;

    /** 工作时间调度：08:00-18:00，每2小时触发一次 */
    @Scheduled(cron = "0 0 8,10,12,14,16,18 * * *")
    public void workHourSchedule() {
        log.info("工作时间调度触发");
        generateTasksForAllActiveSources(scheduleConfig.getScheduledPriority());
    }

    /** 非工作时间调度：20:00, 00:00, 04:00 */
    @Scheduled(cron = "0 0 20,0,4 * * *")
    public void offHourSchedule() {
        log.info("非工作时间调度触发");
        generateTasksForAllActiveSources(scheduleConfig.getScheduledPriority());
    }

    /** 每分钟激活已审批的数据源 */
    @Scheduled(fixedRate = 60000)
    public void activateApprovedSources() {
        List<CollectorSource> approved = sourceMapper.selectList(
                new LambdaQueryWrapper<CollectorSource>()
                        .eq(CollectorSource::getStatus, SourceStatus.APPROVED));
        if (approved.isEmpty()) {
            return;
        }
        for (CollectorSource source : approved) {
            source.setStatus(SourceStatus.ACTIVE);
            sourceMapper.updateById(source);
            log.info("数据源已激活: sourceId={} name={}", source.getId(), source.getName());
        }
    }

    /** 为所有活跃数据源生成任务并推入 Redis 队列 */
    public void generateTasksForAllActiveSources(int priority) {
        List<CollectorSource> sources = sourceMapper.selectList(
                new LambdaQueryWrapper<CollectorSource>()
                        .eq(CollectorSource::getStatus, SourceStatus.ACTIVE));
        log.info("生成调度任务，活跃数据源数量: {}", sources.size());
        for (CollectorSource source : sources) {
            pushTaskToQueue(source, priority);
        }
    }

    /** 手动触发指定数据源（高优先级） */
    public void manualTrigger(List<Integer> sourceIds) {
        if (sourceIds == null || sourceIds.isEmpty()) {
            return;
        }
        List<CollectorSource> sources = sourceMapper.selectBatchIds(sourceIds);
        for (CollectorSource source : sources) {
            pushPriorityTask(source);
        }
    }

    // ----------------------------------------------------------------- private

    private void pushTaskToQueue(CollectorSource source, int priority) {
        try {
            String taskId = UUID.randomUUID().toString();
            String ruleJson = loadRuleJson(source.getId());
            String template = source.getTemplate() != null ? source.getTemplate().getCode() : null;
            String queueType = source.getTemplate() != null ? source.getTemplate().getQueueType() : "http";

            String message = buildTaskMessage(taskId, source, template, ruleJson, priority, 0);

            // Persist task record
            saveTaskRecord(taskId, source, template, queueType, priority);

            // Route to the correct ZSet
            String queue = "browser".equals(queueType) ? QUEUE_BROWSER_PENDING : QUEUE_HTTP_PENDING;
            redisTemplate.opsForZSet().add(queue, message, priority);

            log.debug("任务已推入队列 queue={} sourceId={} taskId={}", queue, source.getId(), taskId);
        } catch (Exception e) {
            log.error("推送任务失败 sourceId={}", source.getId(), e);
        }
    }

    private void pushPriorityTask(CollectorSource source) {
        try {
            String taskId = UUID.randomUUID().toString();
            String ruleJson = loadRuleJson(source.getId());
            String template = source.getTemplate() != null ? source.getTemplate().getCode() : null;
            String queueType = source.getTemplate() != null ? source.getTemplate().getQueueType() : "http";
            int priority = scheduleConfig.getManualTriggerPriority();

            String message = buildTaskMessage(taskId, source, template, ruleJson, priority, 0);

            // Persist task record
            saveTaskRecord(taskId, source, template, "priority", priority);

            // Push to priority list (LPUSH)
            redisTemplate.opsForList().leftPush(QUEUE_PRIORITY, message);

            log.info("手动任务已推入优先队列 sourceId={} taskId={}", source.getId(), taskId);
        } catch (Exception e) {
            log.error("推送手动任务失败 sourceId={}", source.getId(), e);
        }
    }

    private String buildTaskMessage(String taskId, CollectorSource source, String template,
                                     String ruleJson, int priority, int retryCount)
            throws JsonProcessingException {
        Map<String, Object> msg = new HashMap<>();
        msg.put("task_id", taskId);
        msg.put("source_id", source.getId());
        msg.put("url", source.getUrl());
        msg.put("template", template);
        msg.put("rule", ruleJson != null ? objectMapper.readValue(ruleJson, Object.class) : null);
        msg.put("priority", priority);
        msg.put("retry_count", retryCount);
        msg.put("created_at", LocalDateTime.now().format(DateTimeFormatter.ISO_LOCAL_DATE_TIME));
        return objectMapper.writeValueAsString(msg);
    }

    private String loadRuleJson(Integer sourceId) {
        CollectorRule rule = ruleMapper.selectOne(
                new LambdaQueryWrapper<CollectorRule>()
                        .eq(CollectorRule::getSourceId, sourceId)
                        .orderByDesc(CollectorRule::getCreatedAt)
                        .last("LIMIT 1"));
        if (rule == null) {
            return null;
        }
        try {
            Map<String, Object> r = new HashMap<>();
            r.put("list_rule", rule.getListRule() != null
                    ? objectMapper.readValue(rule.getListRule(), Object.class) : null);
            r.put("detail_rule", rule.getDetailRule() != null
                    ? objectMapper.readValue(rule.getDetailRule(), Object.class) : null);
            r.put("anti_bot_config", rule.getAntiBotConfig() != null
                    ? objectMapper.readValue(rule.getAntiBotConfig(), Object.class) : null);
            return objectMapper.writeValueAsString(r);
        } catch (Exception e) {
            log.warn("规则JSON序列化失败 sourceId={}", sourceId, e);
            return null;
        }
    }

    private void saveTaskRecord(String taskId, CollectorSource source,
                                 String template, String queueType, int priority) {
        CollectorTask task = CollectorTask.builder()
                .taskId(taskId)
                .sourceId(source.getId())
                .template(template)
                .queueType(queueType)
                .status("pending")
                .priority(priority)
                .retryCount(0)
                .build();
        taskMapper.insert(task);
    }
}
