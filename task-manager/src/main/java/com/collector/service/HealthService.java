package com.collector.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.collector.entity.CollectorSource;
import com.collector.entity.CollectorTask;
import com.collector.enums.SourceStatus;
import com.collector.mapper.CollectorSourceMapper;
import com.collector.mapper.CollectorTaskMapper;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * 健康评分服务 — 可被 Controller 和 Scheduler 共用
 *
 * 评分维度（0-100）:
 *   成功率 40% | 连续失败 20% | 静默异常 20% | 规则年龄 10% | 内容质量 10%
 *
 * 评分区间:
 *   90-100 优秀（正常采集）
 *   70-89  良好（纳入巡检关注）
 *   50-69  警告（降低频率，优先排查）
 *   0-49   危险（自动暂停，通知人工）
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class HealthService {

    private final CollectorSourceMapper sourceMapper;
    private final CollectorTaskMapper taskMapper;

    /**
     * 计算单个源的健康评分
     */
    public HealthDetail computeHealth(CollectorSource source) {
        LocalDateTime since7d = LocalDateTime.now().minusDays(7);
        List<CollectorTask> tasks = taskMapper.selectList(
                new LambdaQueryWrapper<CollectorTask>()
                        .eq(CollectorTask::getSourceId, source.getId())
                        .ge(CollectorTask::getCreatedAt, since7d));
        return computeHealth(source, tasks);
    }

    /**
     * 计算健康评分（传入任务列表，避免重复查询）
     */
    public HealthDetail computeHealth(CollectorSource source, List<CollectorTask> tasks) {
        HealthDetail detail = new HealthDetail();
        detail.setSourceId(source.getId());

        // 维度1: 近7天成功率 (40分)
        detail.setSuccessRateScore(calcSuccessRate(tasks));

        // 维度2: 连续失败惩罚 (20分)
        int failCount = source.getFailCount() != null ? source.getFailCount() : 0;
        detail.setFailPenaltyScore(Math.max(0.0, 20.0 - failCount * 4.0));

        // 维度3: 静默异常 (20分)
        int quietDays = calcQuietDays(source);
        detail.setQuietDays(quietDays);
        detail.setQuietScore(calcQuietScore(quietDays, source));

        // 维度4: 规则年龄 (10分)
        detail.setRuleAgeScore(calcRuleAge(source));

        // 维度5: 内容质量 (10分)
        detail.setContentQualityScore(calcContentQuality(tasks));

        // 总分
        double total = detail.getSuccessRateScore() + detail.getFailPenaltyScore()
                + detail.getQuietScore() + detail.getRuleAgeScore() + detail.getContentQualityScore();
        detail.setHealthScore((int) Math.round(Math.min(100, Math.max(0, total))));

        // 基线计算
        detail.setAvgUpdateIntervalHours(calcAvgInterval(tasks));

        // 异常静默检测
        detail.setQuietAnomaly(isQuietAnomaly(quietDays, detail.getAvgUpdateIntervalHours()));

        // 等级
        detail.setLevel(scoreToLevel(detail.getHealthScore()));

        return detail;
    }

    /**
     * 批量计算所有 active 源的健康评分并写入数据库
     */
    public int recalculateAll() {
        List<CollectorSource> sources = sourceMapper.selectList(
                new LambdaQueryWrapper<CollectorSource>()
                        .eq(CollectorSource::getStatus, SourceStatus.ACTIVE));

        LocalDateTime since7d = LocalDateTime.now().minusDays(7);
        List<CollectorTask> allTasks = taskMapper.selectList(
                new LambdaQueryWrapper<CollectorTask>()
                        .ge(CollectorTask::getCreatedAt, since7d));

        Map<Integer, List<CollectorTask>> tasksBySource = allTasks.stream()
                .collect(Collectors.groupingBy(CollectorTask::getSourceId));

        int updated = 0;
        for (CollectorSource source : sources) {
            try {
                HealthDetail detail = computeHealth(source,
                        tasksBySource.getOrDefault(source.getId(), List.of()));

                source.setHealthScore(detail.getHealthScore());
                source.setAvgUpdateIntervalHours(detail.getAvgUpdateIntervalHours());
                source.setQuietDays(detail.getQuietDays());
                sourceMapper.updateById(source);
                updated++;
            } catch (Exception e) {
                log.warn("健康评分计算失败 source={}: {}", source.getId(), e.getMessage());
            }
        }
        return updated;
    }

    /**
     * 获取异常静默源列表（quiet_days > 基线 × 3）
     */
    public List<CollectorSource> getQuietAnomalySources() {
        List<CollectorSource> sources = sourceMapper.selectList(
                new LambdaQueryWrapper<CollectorSource>()
                        .eq(CollectorSource::getStatus, SourceStatus.ACTIVE)
                        .gt(CollectorSource::getQuietDays, 0)
                        .isNull(CollectorSource::getQuietConfirmedAt));

        List<CollectorSource> anomalies = new ArrayList<>();
        for (CollectorSource source : sources) {
            BigDecimal avg = source.getAvgUpdateIntervalHours();
            int qd = source.getQuietDays() != null ? source.getQuietDays() : 0;
            if (isQuietAnomaly(qd, avg)) {
                anomalies.add(source);
            }
        }
        return anomalies;
    }

    // ==================== 计算方法 ====================

    private double calcSuccessRate(List<CollectorTask> tasks) {
        if (tasks.isEmpty()) return 20.0;
        long completed = tasks.stream()
                .filter(t -> t.getStatus() != null && !"pending".equals(t.getStatus()) && !"processing".equals(t.getStatus()))
                .count();
        long succeeded = tasks.stream()
                .filter(t -> "success".equals(t.getStatus()) || "partial".equals(t.getStatus()))
                .count();
        return completed > 0 ? (double) succeeded / completed * 40.0 : 20.0;
    }

    private double calcQuietScore(int quietDays, CollectorSource source) {
        if (quietDays <= 0) return 20.0;
        // 超30天静默严重扣分，超90天扣满
        if (quietDays > 90) return 0.0;
        if (quietDays > 30) return 5.0;
        return Math.max(0.0, 20.0 - quietDays * 0.5);
    }

    private double calcRuleAge(CollectorSource source) {
        if (source.getCreatedAt() == null) return 10.0;
        long months = ChronoUnit.MONTHS.between(source.getCreatedAt().toLocalDate(), LocalDate.now());
        // 超6个月未更新规则扣分
        if (months > 6) return 0.0;
        if (months > 3) return 5.0;
        return 10.0;
    }

    private double calcContentQuality(List<CollectorTask> tasks) {
        if (tasks.isEmpty()) return 10.0;
        long withArticles = tasks.stream()
                .filter(t -> t.getArticlesNew() != null && t.getArticlesNew() > 0)
                .count();
        return (double) withArticles / tasks.size() * 10.0;
    }

    private int calcQuietDays(CollectorSource source) {
        if (source.getLastSuccessAt() == null) return 0;
        long days = ChronoUnit.DAYS.between(source.getLastSuccessAt().toLocalDate(), LocalDate.now());
        return (int) Math.max(0, days);
    }

    private BigDecimal calcAvgInterval(List<CollectorTask> tasks) {
        List<LocalDateTime> successTimes = tasks.stream()
                .filter(t -> "success".equals(t.getStatus()) || "partial".equals(t.getStatus()))
                .filter(t -> t.getCompletedAt() != null)
                .map(CollectorTask::getCompletedAt)
                .sorted()
                .collect(Collectors.toList());

        if (successTimes.size() < 2) return null;

        long totalMinutes = 0;
        for (int i = 1; i < successTimes.size(); i++) {
            totalMinutes += ChronoUnit.MINUTES.between(successTimes.get(i - 1), successTimes.get(i));
        }
        double avgHours = (double) totalMinutes / (successTimes.size() - 1) / 60.0;
        return BigDecimal.valueOf(avgHours).setScale(2, RoundingMode.HALF_UP);
    }

    /**
     * 异常静默检测: quiet_days > 基线间隔(天) × 3
     * 如果没有基线，超30天视为异常
     */
    private boolean isQuietAnomaly(int quietDays, BigDecimal avgIntervalHours) {
        if (quietDays <= 0) return false;
        if (avgIntervalHours != null && avgIntervalHours.compareTo(BigDecimal.ZERO) > 0) {
            double baselineDays = avgIntervalHours.doubleValue() / 24.0;
            return quietDays > baselineDays * 3;
        }
        return quietDays > 30;
    }

    private String scoreToLevel(int score) {
        if (score >= 90) return "excellent";
        if (score >= 70) return "good";
        if (score >= 50) return "warning";
        return "danger";
    }

    // ==================== VO ====================

    @Data
    public static class HealthDetail {
        private Integer sourceId;
        private int healthScore;
        private String level;
        private double successRateScore;
        private double failPenaltyScore;
        private double quietScore;
        private double ruleAgeScore;
        private double contentQualityScore;
        private int quietDays;
        private boolean quietAnomaly;
        private BigDecimal avgUpdateIntervalHours;
    }
}
