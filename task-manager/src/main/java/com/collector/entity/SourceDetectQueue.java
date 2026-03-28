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
@TableName("source_detect_queue")
public class SourceDetectQueue {

    @TableId(type = IdType.AUTO)
    private Integer id;
    private Integer sourceId;
    private String detectType;       // full/template_only/rule_only
    private String status;           // pending/processing/completed/failed
    private Integer priority;
    private String result;           // JSON
    private String errorMessage;
    private Integer retryCount;
    private LocalDateTime createdAt;
    private LocalDateTime completedAt;
}
