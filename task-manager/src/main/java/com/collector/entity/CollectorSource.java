package com.collector.entity;

import com.baomidou.mybatisplus.annotation.*;
import com.collector.enums.SourceStatus;
import com.collector.enums.TemplateType;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@TableName("collector_source")
public class CollectorSource {

    @TableId(type = IdType.AUTO)
    private Integer id;

    // 基本信息
    private String name;
    private String columnName;
    private String url;
    private String sourceType;
    private TemplateType template;
    private String platform;
    private String platformParams;   // JSON
    private String region;
    private Integer priority;
    private Integer checkInterval;
    private String encoding;

    // 状态与统计
    private SourceStatus status;
    private Integer failCount;
    private Integer totalArticles;
    private LocalDateTime lastSuccessAt;
    private LocalDate lastArticleDate;

    // 试采与审批
    private BigDecimal trialScore;
    private String trialResult;      // JSON
    private LocalDateTime trialAt;
    private String approvedBy;
    private LocalDateTime approvedAt;

    // 健康监控
    private Integer healthScore;
    private BigDecimal avgUpdateIntervalHours;
    private Integer quietDays;
    private LocalDateTime quietConfirmedAt;

    // 时间戳
    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;
    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;
}
