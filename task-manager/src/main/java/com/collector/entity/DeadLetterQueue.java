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
@TableName("dead_letter_queue")
public class DeadLetterQueue {

    @TableId(type = IdType.AUTO)
    private Integer id;
    private String taskId;
    private Integer sourceId;
    private String template;
    private String url;
    private String errorType;
    private String errorMessage;
    private Integer retryCount;
    private String handleStatus;     // pending/retried/ignored/reconfigured
    private String handledBy;
    private LocalDateTime createdAt;
    private LocalDateTime handledAt;
}
