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
@TableName("collector_log")
public class CollectorLog {

    @TableId(type = IdType.AUTO)
    private Long id;
    private Integer sourceId;
    private String taskId;
    private String action;           // crawl_success/crawl_failed/detect/trial/approve/reject/pause/resume/retire/reset
    private String level;            // INFO/WARN/ERROR
    private String message;
    private String extra;            // JSON
    private String operator;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;
}
