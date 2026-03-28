package com.collector.dto;

import com.collector.enums.SourceStatus;
import com.collector.enums.TemplateType;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class SourceDetailVO {

    // --- identity ---
    private Integer id;

    // --- basic info ---
    private String name;
    private String columnName;
    private String url;
    private String sourceType;
    private TemplateType template;
    private String platform;
    private String platformParams;
    private String region;
    private Integer priority;
    private Integer checkInterval;
    private String encoding;

    // --- status & stats ---
    private SourceStatus status;
    private Integer failCount;
    private Integer totalArticles;
    private LocalDateTime lastSuccessAt;
    private LocalDate lastArticleDate;

    // --- trial & approval ---
    private BigDecimal trialScore;
    private String trialResult;
    private LocalDateTime trialAt;
    private String approvedBy;
    private LocalDateTime approvedAt;

    // --- health monitoring ---
    private Integer healthScore;
    private BigDecimal avgUpdateIntervalHours;
    private Integer quietDays;
    private LocalDateTime quietConfirmedAt;

    // --- timestamps ---
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;

    // --- enriched ---
    /** JSON string from collector_rule */
    private String rulInfo;

    /** Recent 5 collector_log entries */
    private List<Map<String, Object>> recentLogs;
}
