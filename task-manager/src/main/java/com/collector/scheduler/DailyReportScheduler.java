package com.collector.scheduler;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.collector.entity.CollectorSource;
import com.collector.entity.CollectorTask;
import com.collector.enums.SourceStatus;
import com.collector.mapper.CollectorSourceMapper;
import com.collector.mapper.CollectorTaskMapper;
import com.collector.service.AlertService;
import com.collector.service.WebhookService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * 每日巡检日报 — 每天 9:00 生成并推送
 *
 * 日报内容:
 * 1. 全局指标（活跃源/异常/成功率/今日新增文章/队列积压）
 * 2. 异常源汇总（访问异常/规则失效/长期静默）
 * 3. 模板健康度
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class DailyReportScheduler {

    private final CollectorSourceMapper sourceMapper;
    private final CollectorTaskMapper taskMapper;
    private final WebhookService webhookService;
    private final AlertService alertService;

    /**
     * 每天 9:00 生成巡检日报
     */
    @Scheduled(cron = "0 0 9 * * *")
    public void generateDailyReport() {
        log.info("开始生成每日巡检日报...");

        // 先执行一轮告警检查
        alertService.checkAlerts();

        // 生成日报
        String report = buildReport();
        webhookService.send("📊 采集系统巡检日报 — " + LocalDate.now().format(DateTimeFormatter.ISO_LOCAL_DATE), report);

        log.info("每日巡检日报已生成并推送");
    }

    /**
     * 手动触发日报（供 Controller 调用）
     */
    public String generateAndReturn() {
        alertService.checkAlerts();
        return buildReport();
    }

    private String buildReport() {
        StringBuilder sb = new StringBuilder();
        LocalDateTime todayStart = LocalDate.now().atStartOfDay();

        // ---- 全局指标 ----
        long activeSources = sourceMapper.selectCount(
                new LambdaQueryWrapper<CollectorSource>().eq(CollectorSource::getStatus, SourceStatus.ACTIVE));
        long errorSources = sourceMapper.selectCount(
                new LambdaQueryWrapper<CollectorSource>().eq(CollectorSource::getStatus, SourceStatus.ERROR));
        long pendingReview = sourceMapper.selectCount(
                new LambdaQueryWrapper<CollectorSource>().eq(CollectorSource::getStatus, SourceStatus.PENDING_REVIEW));
        long totalSources = sourceMapper.selectCount(null);

        long todayTasks = taskMapper.selectCount(
                new LambdaQueryWrapper<CollectorTask>().ge(CollectorTask::getCreatedAt, todayStart));
        long todaySuccess = taskMapper.selectCount(
                new LambdaQueryWrapper<CollectorTask>()
                        .ge(CollectorTask::getCreatedAt, todayStart)
                        .eq(CollectorTask::getStatus, "success"));
        long todayFailed = taskMapper.selectCount(
                new LambdaQueryWrapper<CollectorTask>()
                        .ge(CollectorTask::getCreatedAt, todayStart)
                        .in(CollectorTask::getStatus, "failed", "timeout", "dead"));
        long todayArticles = 0;
        // 简化：用成功任务的 articles_new 汇总
        var successTasks = taskMapper.selectList(
                new LambdaQueryWrapper<CollectorTask>()
                        .ge(CollectorTask::getCreatedAt, todayStart)
                        .eq(CollectorTask::getStatus, "success")
                        .isNotNull(CollectorTask::getArticlesNew));
        todayArticles = successTasks.stream()
                .mapToLong(t -> t.getArticlesNew() != null ? t.getArticlesNew() : 0)
                .sum();

        double successRate = todayTasks > 0 ? (double) todaySuccess / todayTasks * 100 : 0;

        sb.append("**一、全局指标**\n\n");
        sb.append(String.format("- 采集源总数: %d | 活跃: %d | 异常: %d | 待审核: %d\n",
                totalSources, activeSources, errorSources, pendingReview));
        sb.append(String.format("- 今日任务: %d | 成功: %d | 失败: %d | 成功率: %.1f%%\n",
                todayTasks, todaySuccess, todayFailed, successRate));
        sb.append(String.format("- 今日新增文章: %d\n", todayArticles));
        sb.append("\n");

        // ---- 异常源汇总 ----
        sb.append("**二、需关注问题**\n\n");

        // 访问异常（error 状态）
        if (errorSources > 0) {
            sb.append(String.format("🔴 访问异常: %d 个\n", errorSources));
            var errorList = sourceMapper.selectList(
                    new LambdaQueryWrapper<CollectorSource>()
                            .eq(CollectorSource::getStatus, SourceStatus.ERROR)
                            .last("LIMIT 5"));
            for (var s : errorList) {
                sb.append(String.format("  - #%d %s（%s）连续失败 %d 次\n",
                        s.getId(), s.getName(), s.getColumnName() != null ? s.getColumnName() : "", s.getFailCount()));
            }
        }

        // 规则失效
        long detectFailed = sourceMapper.selectCount(
                new LambdaQueryWrapper<CollectorSource>().eq(CollectorSource::getStatus, SourceStatus.DETECT_FAILED));
        if (detectFailed > 0) {
            sb.append(String.format("🟡 规则失效: %d 个\n", detectFailed));
        }

        // 长期静默（quiet_days > 30）
        long quietSources = sourceMapper.selectCount(
                new LambdaQueryWrapper<CollectorSource>()
                        .eq(CollectorSource::getStatus, SourceStatus.ACTIVE)
                        .gt(CollectorSource::getQuietDays, 30));
        if (quietSources > 0) {
            sb.append(String.format("🟢 长期静默(>30天): %d 个\n", quietSources));
        }

        if (errorSources == 0 && detectFailed == 0 && quietSources == 0) {
            sb.append("✅ 无异常，系统运行正常\n");
        }
        sb.append("\n");

        // ---- 模板健康度 ----
        sb.append("**三、模板健康度**\n\n");

        var allActive = sourceMapper.selectList(
                new LambdaQueryWrapper<CollectorSource>().eq(CollectorSource::getStatus, SourceStatus.ACTIVE));
        Map<String, Long> templateCounts = allActive.stream()
                .collect(Collectors.groupingBy(
                        s -> s.getTemplate() != null ? s.getTemplate().getLetter() : "?",
                        Collectors.counting()));
        Map<String, Double> templateHealth = allActive.stream()
                .collect(Collectors.groupingBy(
                        s -> s.getTemplate() != null ? s.getTemplate().getLetter() : "?",
                        Collectors.averagingInt(s -> s.getHealthScore() != null ? s.getHealthScore() : 0)));

        for (var entry : templateCounts.entrySet()) {
            String letter = entry.getKey();
            long count = entry.getValue();
            double avgHealth = templateHealth.getOrDefault(letter, 0.0);
            String bar = avgHealth >= 90 ? "🟢" : avgHealth >= 70 ? "🟡" : "🔴";
            sb.append(String.format("  %s 模板%s: %d源, 平均健康 %.0f分\n", bar, letter, count, avgHealth));
        }

        return sb.toString();
    }
}
