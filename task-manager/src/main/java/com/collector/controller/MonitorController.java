package com.collector.controller;

import com.collector.common.Result;
import com.collector.entity.WorkerHeartbeat;
import com.collector.service.MonitorService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/monitor")
@RequiredArgsConstructor
public class MonitorController {

    private final MonitorService monitorService;

    /**
     * GET /api/monitor/dashboard - dashboard overview data
     */
    @GetMapping("/dashboard")
    public Result<Map<String, Object>> dashboard() {
        return Result.ok(monitorService.dashboard());
    }

    /**
     * GET /api/monitor/workers - list online workers
     */
    @GetMapping("/workers")
    public Result<List<WorkerHeartbeat>> workers() {
        return Result.ok(monitorService.workerStatus());
    }

    /**
     * GET /api/monitor/queue - Redis queue status
     */
    @GetMapping("/queue")
    public Result<Map<String, Object>> queue() {
        return Result.ok(monitorService.queueStatus());
    }

    /**
     * GET /api/monitor/templates - template health stats
     */
    @GetMapping("/templates")
    public Result<List<Map<String, Object>>> templates() {
        return Result.ok(monitorService.templateHealth());
    }
}
