package com.collector.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.collector.entity.CollectorSource;
import com.collector.entity.CollectorTask;
import com.collector.entity.WorkerHeartbeat;
import com.collector.enums.SourceStatus;
import com.collector.mapper.CollectorSourceMapper;
import com.collector.mapper.CollectorTaskMapper;
import com.collector.mapper.WorkerHeartbeatMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.*;
import java.util.stream.Collectors;

/**
 * 监控面板服务 — 提供 Dashboard 概览、Worker 状态、队列状态和模板健康度
 * <p>
 * 返回的 Map 使用 snake_case 键名以匹配前端约定。
 * dashboard() 中 error_sources 和 error_count 是同一个值的两个别名，保持前端兼容。
 * queue_pending 和 queue_backlog 同理。
 * </p>
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class MonitorService {

    private final CollectorSourceMapper sourceMapper;
    private final CollectorTaskMapper taskMapper;
    private final WorkerHeartbeatMapper heartbeatMapper;
    private final StringRedisTemplate redisTemplate;

    /**
     * Dashboard 概览数据
     * <p>
     * 包含：活跃/异常数据源数、今日新增文章数、24小时成功率、
     * Redis 队列积压数、待检测/待审核/沉默数据源数。
     * 成功率计算保留两位小数（先 *10000 再 /100.0）。
     * </p>
     */
    public Map<String, Object> dashboard() {
        Map<String, Object> result = new LinkedHashMap<>();

        // 活跃数据源数量
        long activeSources = sourceMapper.selectCount(
                new LambdaQueryWrapper<CollectorSource>()
                        .eq(CollectorSource::getStatus, SourceStatus.ACTIVE));

        // 异常数据源数量
        long errorSources = sourceMapper.selectCount(
                new LambdaQueryWrapper<CollectorSource>()
                        .eq(CollectorSource::getStatus, SourceStatus.ERROR));

        // 今日新增文章数（基于 completedAt 统计，仅计 success/partial 状态的任务）
        LocalDateTime todayStart = LocalDateTime.now().toLocalDate().atStartOfDay();
        List<CollectorTask> todayTasks = taskMapper.selectList(
                new LambdaQueryWrapper<CollectorTask>()
                        .ge(CollectorTask::getCompletedAt, todayStart)
                        .in(CollectorTask::getStatus, "success", "partial"));

        long todayArticles = todayTasks.stream()
                .mapToLong(t -> t.getArticlesNew() != null ? t.getArticlesNew() : 0)
                .sum();

        // 最近24小时成功率（success+partial 视为成功）
        LocalDateTime since24h = LocalDateTime.now().minusHours(24);
        List<CollectorTask> recentTasks = taskMapper.selectList(
                new LambdaQueryWrapper<CollectorTask>()
                        .ge(CollectorTask::getCreatedAt, since24h)
                        .in(CollectorTask::getStatus, "success", "partial", "failed", "timeout", "dead"));

        double successRate = 0.0;
        if (!recentTasks.isEmpty()) {
            long succeeded = recentTasks.stream()
                    .filter(t -> "success".equals(t.getStatus()) || "partial".equals(t.getStatus()))
                    .count();
            successRate = Math.round((double) succeeded / recentTasks.size() * 10000) / 100.0;
        }

        // Redis 队列积压数（http + browser 两个队列之和）
        Map<String, Object> queueInfo = queueStatus();
        long queuePending = ((Number) queueInfo.getOrDefault("httpPending", 0)).longValue()
                + ((Number) queueInfo.getOrDefault("browserPending", 0)).longValue();

        // 待检测数据源数量
        long pendingDetect = sourceMapper.selectCount(
                new LambdaQueryWrapper<CollectorSource>()
                        .eq(CollectorSource::getStatus, SourceStatus.PENDING_DETECT));

        // 待审核数据源数量（trial_passed 或 pending_review）
        long pendingReview = sourceMapper.selectCount(
                new LambdaQueryWrapper<CollectorSource>()
                        .in(CollectorSource::getStatus, SourceStatus.TRIAL_PASSED, SourceStatus.PENDING_REVIEW));

        // 沉默数据源（活跃状态但超过30天未更新）
        long silentCount = sourceMapper.selectCount(
                new LambdaQueryWrapper<CollectorSource>()
                        .eq(CollectorSource::getStatus, SourceStatus.ACTIVE)
                        .gt(CollectorSource::getQuietDays, 30));

        result.put("active_sources", activeSources);
        result.put("error_sources", errorSources);
        result.put("error_count", errorSources);
        result.put("today_articles", todayArticles);
        result.put("success_rate", successRate);
        result.put("queue_pending", queuePending);
        result.put("queue_backlog", queuePending);
        result.put("pending_detect", pendingDetect);
        result.put("pending_review", pendingReview);
        result.put("silent_count", silentCount);
        return result;
    }

    /** Worker 在线状态 — 60秒内有心跳的 Worker 视为在线 */
    public List<WorkerHeartbeat> workerStatus() {
        LocalDateTime threshold = LocalDateTime.now().minusSeconds(60);
        return heartbeatMapper.selectList(
                new LambdaQueryWrapper<WorkerHeartbeat>()
                        .ge(WorkerHeartbeat::getHeartbeatAt, threshold)
                        .orderByDesc(WorkerHeartbeat::getHeartbeatAt));
    }

    /**
     * Redis 队列状态 — 查询各队列的积压量
     * <p>
     * Redis 不可用时返回全零并附加 error 字段，不抛异常。
     * </p>
     */
    public Map<String, Object> queueStatus() {
        Map<String, Object> result = new LinkedHashMap<>();

        try {
            // HTTP 待处理队列（Sorted Set，用 ZCARD 获取数量）
            Long httpPending = redisTemplate.opsForZSet().size("task:http:pending");
            result.put("httpPending", httpPending != null ? httpPending : 0);

            // 浏览器渲染待处理队列（Sorted Set）
            Long browserPending = redisTemplate.opsForZSet().size("task:browser:pending");
            result.put("browserPending", browserPending != null ? browserPending : 0);

            // 正在处理中的任务（Hash，key=taskId）
            Long processing = redisTemplate.opsForHash().size("task:processing");
            result.put("processing", processing != null ? processing : 0);

            // 死信队列（List，多次失败的任务）
            Long dead = redisTemplate.opsForList().size("task:dead");
            result.put("dead", dead != null ? dead : 0);

        } catch (Exception e) {
            log.warn("Failed to query Redis queue status: {}", e.getMessage());
            result.put("httpPending", 0);
            result.put("browserPending", 0);
            result.put("processing", 0);
            result.put("dead", 0);
            result.put("error", "Redis unavailable");
        }

        return result;
    }

    /**
     * 模板健康度 — 按模板分组统计最近24小时的成功率
     * <p>
     * 结果按成功率升序排列，便于发现异常模板。
     * </p>
     */
    public List<Map<String, Object>> templateHealth() {
        LocalDateTime since24h = LocalDateTime.now().minusHours(24);

        List<CollectorTask> recentTasks = taskMapper.selectList(
                new LambdaQueryWrapper<CollectorTask>()
                        .ge(CollectorTask::getCreatedAt, since24h)
                        .in(CollectorTask::getStatus, "success", "partial", "failed", "timeout", "dead"));

        Map<String, List<CollectorTask>> byTemplate = recentTasks.stream()
                .filter(t -> t.getTemplate() != null)
                .collect(Collectors.groupingBy(CollectorTask::getTemplate));

        List<Map<String, Object>> healthList = new ArrayList<>();
        for (Map.Entry<String, List<CollectorTask>> entry : byTemplate.entrySet()) {
            String template = entry.getKey();
            List<CollectorTask> tasks = entry.getValue();
            long total = tasks.size();
            long succeeded = tasks.stream()
                    .filter(t -> "success".equals(t.getStatus()) || "partial".equals(t.getStatus()))
                    .count();
            double rate = total > 0 ? Math.round((double) succeeded / total * 10000) / 100.0 : 0.0;

            Map<String, Object> item = new LinkedHashMap<>();
            item.put("template", template);
            item.put("total", total);
            item.put("succeeded", succeeded);
            item.put("successRate", rate);
            healthList.add(item);
        }

        healthList.sort((a, b) -> Double.compare(
                (Double) a.get("successRate"), (Double) b.get("successRate")));

        return healthList;
    }
}
