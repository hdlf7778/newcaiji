package com.collector.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@TableName("collector_rule")
public class CollectorRule {

    @TableId(type = IdType.AUTO)
    private Integer id;
    private Integer sourceId;
    private String listRule;          // JSON
    private String detailRule;        // JSON
    private String antiBotConfig;     // JSON
    private String attachmentConfig;  // JSON
    private String monitorConfig;     // JSON
    private Integer ruleVersion;
    private String previousRuleJson;  // JSON
    private String generatedBy;       // llm/manual/platform

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;
    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;
}
