package com.collector.scheduler;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.collector.entity.CollectorSource;
import com.collector.entity.CollectorTask;
import com.collector.enums.SourceStatus;
import com.collector.mapper.CollectorSourceMapper;
import com.collector.mapper.CollectorTaskMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.temporal.ChronoUnit;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@Slf4j
@Component
@RequiredArgsConstructor
public class HealthScoreScheduler {

    private final CollectorSourceMapper sourceMapper;
    private final CollectorTaskMapper taskMapper;

    /**
     * Calculate and update health scores for all active sources every day at 02:00 AM.
     *
     * Score formula (0–100):
     *   recent_7d_success_rate * 0.4
     *   + consecutive_fail_penalty * 0.2
     *   + quiet_anomaly * 0.2
     *   + rule_age * 0.1
     *   + content_quality * 0.1
     */
    @Scheduled(cron = "0 0 2 * * *")
    public void calculateHealthScores() {
        log.info("Starting health score calculation...");

        List<CollectorSource> activeSources = sourceMapper.selectList(
                new LambdaQueryWrapper<CollectorSource>()
                        .eq(CollectorSource::getStatus, SourceStatus.ACTIVE));

        if (activeSources.isEmpty()) {
            log.info("No active sources found, skipping health score calculation.");
            return;
        }

        LocalDateTime since7d = LocalDateTime.now().minusDays(7);
        List<CollectorTask> recentTasks = taskMapper.selectList(
                new LambdaQueryWrapper<CollectorTask>()
                        .ge(CollectorTask::getCreatedAt, since7d));

        // Group tasks by sourceId
        Map<Integer, List<CollectorTask>> tasksBySource = recentTasks.stream()
                .collect(Collectors.groupingBy(CollectorTask::getSourceId));

        int updated = 0;
        for (CollectorSource source : activeSources) {
            try {
                int healthScore = computeHealthScore(source, tasksBySource.getOrDefault(source.getId(), List.of()));
                BigDecimal avgInterval = computeAvgUpdateInterval(source,
                        tasksBySource.getOrDefault(source.getId(), List.of()));
                int quietDays = computeQuietDays(source);

                source.setHealthScore(healthScore);
                source.setAvgUpdateIntervalHours(avgInterval);
                source.setQuietDays(quietDays);
                sourceMapper.updateById(source);
                updated++;
            } catch (Exception e) {
                log.warn("Failed to compute health score for source id={}: {}", source.getId(), e.getMessage());
            }
        }

        log.info("Health score calculation complete. Updated {} sources.", updated);
    }

    private int computeHealthScore(CollectorSource source, List<CollectorTask> tasks) {
        // Component 1: recent 7d success rate (weight 0.4, max 40 points)
        double successRateScore = 0.0;
        if (!tasks.isEmpty()) {
            long completed = tasks.stream()
                    .filter(t -> "success".equals(t.getStatus()) || "partial".equals(t.getStatus())
                            || "failed".equals(t.getStatus()) || "timeout".equals(t.getStatus())
                            || "dead".equals(t.getStatus()))
                    .count();
            long succeeded = tasks.stream()
                    .filter(t -> "success".equals(t.getStatus()) || "partial".equals(t.getStatus()))
                    .count();
            if (completed > 0) {
                successRateScore = (double) succeeded / completed * 40.0;
            }
        } else {
            // No tasks in 7 days — neutral score
            successRateScore = 20.0;
        }

        // Component 2: consecutive fail penalty (weight 0.2, max 20 points)
        // More consecutive failures = lower score
        double consecutiveFailScore = 20.0;
        int failCount = source.getFailCount() != null ? source.getFailCount() : 0;
        if (failCount > 0) {
            // Each consecutive fail reduces by 4 points, minimum 0
            consecutiveFailScore = Math.max(0.0, 20.0 - failCount * 4.0);
        }

        // Component 3: quiet anomaly (weight 0.2, max 20 points)
        // The longer the source has been quiet, the lower the score
        double quietAnomalyScore = 20.0;
        int quietDays = computeQuietDays(source);
        if (quietDays > 0) {
            quietAnomalyScore = Math.max(0.0, 20.0 - quietDays * 2.0);
        }

        // Component 4: rule age (weight 0.1, max 10 points)
        // Newer sources get slight bonus; older ones are assumed stable
        double ruleAgeScore = 10.0;
        if (source.getCreatedAt() != null) {
            long daysSinceCreation = ChronoUnit.DAYS.between(
                    source.getCreatedAt().toLocalDate(), LocalDate.now());
            // Newly added sources (< 7 days) get slightly lower score due to uncertainty
            if (daysSinceCreation < 7) {
                ruleAgeScore = 5.0;
            }
        }

        // Component 5: content quality proxy (weight 0.1, max 10 points)
        // Based on articles found ratio
        double contentQualityScore = 10.0;
        if (!tasks.isEmpty()) {
            long tasksWithArticles = tasks.stream()
                    .filter(t -> t.getArticlesNew() != null && t.getArticlesNew() > 0)
                    .count();
            contentQualityScore = (double) tasksWithArticles / tasks.size() * 10.0;
        }

        double total = successRateScore + consecutiveFailScore + quietAnomalyScore
                + ruleAgeScore + contentQualityScore;

        return (int) Math.round(Math.min(100, Math.max(0, total)));
    }

    private BigDecimal computeAvgUpdateInterval(CollectorSource source, List<CollectorTask> tasks) {
        List<CollectorTask> successTasks = tasks.stream()
                .filter(t -> "success".equals(t.getStatus()) || "partial".equals(t.getStatus()))
                .filter(t -> t.getCompletedAt() != null)
                .sorted((a, b) -> a.getCompletedAt().compareTo(b.getCompletedAt()))
                .collect(Collectors.toList());

        if (successTasks.size() < 2) {
            return null;
        }

        long totalMinutes = 0;
        for (int i = 1; i < successTasks.size(); i++) {
            long minutes = ChronoUnit.MINUTES.between(
                    successTasks.get(i - 1).getCompletedAt(),
                    successTasks.get(i).getCompletedAt());
            totalMinutes += minutes;
        }

        double avgHours = (double) totalMinutes / (successTasks.size() - 1) / 60.0;
        return BigDecimal.valueOf(avgHours).setScale(2, RoundingMode.HALF_UP);
    }

    private int computeQuietDays(CollectorSource source) {
        if (source.getLastSuccessAt() == null) {
            return 0;
        }
        long days = ChronoUnit.DAYS.between(source.getLastSuccessAt().toLocalDate(), LocalDate.now());
        return (int) Math.max(0, days);
    }
}
