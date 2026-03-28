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
@TableName("collector_task")
public class CollectorTask {

    @TableId(type = IdType.AUTO)
    private Integer id;
    private String taskId;           // UUID，全链路 trace_id
    private Integer sourceId;
    private String template;
    private String queueType;        // http/browser/priority
    private String status;           // pending/processing/success/partial/failed/timeout/dead
    private Integer priority;
    private Integer retryCount;
    private Integer articlesFound;
    private Integer articlesNew;
    private Integer durationMs;
    private String errorMessage;
    private String errorType;        // network_timeout/http_403/http_429/parse_error/template_mismatch/ssl_error/anti_bot_blocked

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;
    private LocalDateTime startedAt;
    private LocalDateTime completedAt;
}
