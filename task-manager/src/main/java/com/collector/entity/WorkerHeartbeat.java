package com.collector.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@TableName("worker_heartbeat")
public class WorkerHeartbeat {

    @TableId(type = IdType.AUTO)
    private Integer id;
    private String workerId;
    private String workerType;       // http/browser
    private String status;           // running/idle/stopping
    private String currentTaskId;
    private BigDecimal cpuUsage;
    private Integer memoryMb;
    private Integer tasksCompleted;
    private Integer tasksFailed;
    private Integer uptimeSeconds;
    private LocalDateTime heartbeatAt;
}
