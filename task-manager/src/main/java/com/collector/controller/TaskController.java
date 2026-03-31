package com.collector.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.collector.common.BusinessException;
import com.collector.common.PageResult;
import com.collector.common.Result;
import com.collector.config.ScheduleConfig;
import com.collector.entity.CollectorTask;
import com.collector.mapper.CollectorTaskMapper;
import com.collector.scheduler.CollectorTaskScheduler;
import lombok.RequiredArgsConstructor;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 采集任务控制器
 * <p>
 * 提供任务列表查询、任务详情、手动触发/重试、任务统计以及调度配置的读写。
 * schedule-config 使用 Map 返回而非直接返回 ScheduleConfig 对象，
 * 以避免 Jackson 序列化驼峰/下划线不一致的问题。
 * </p>
 */
@RestController
@RequestMapping("/api/tasks")
@RequiredArgsConstructor
public class TaskController {

    private final CollectorTaskMapper taskMapper;
    private final CollectorTaskScheduler taskScheduler;
    /** 调度配置（内存中可变对象，修改后立即生效但重启后丢失） */
    private final ScheduleConfig scheduleConfig;

    /** GET /api/tasks - 分页查询任务列表 */
    @GetMapping
    public Result<PageResult<CollectorTask>> list(
            @RequestParam(required = false) String status,
            @RequestParam(required = false) String template,
            @RequestParam(required = false) Integer sourceId,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int size) {

        size = Math.min(size, 200);

        LambdaQueryWrapper<CollectorTask> wrapper = new LambdaQueryWrapper<>();
        if (status != null && !status.isEmpty()) {
            wrapper.eq(CollectorTask::getStatus, status);
        }
        if (template != null && !template.isEmpty()) {
            wrapper.eq(CollectorTask::getTemplate, template);
        }
        if (sourceId != null) {
            wrapper.eq(CollectorTask::getSourceId, sourceId);
        }
        wrapper.orderByDesc(CollectorTask::getCreatedAt);

        IPage<CollectorTask> iPage = taskMapper.selectPage(new Page<>(page, size), wrapper);
        return Result.ok(new PageResult<>(iPage.getRecords(), iPage.getTotal(), iPage.getCurrent(), iPage.getSize()));
    }

    /** GET /api/tasks/{id} - 任务详情 */
    @GetMapping("/{id}")
    public Result<CollectorTask> detail(@PathVariable Integer id) {
        CollectorTask task = taskMapper.selectById(id);
        if (task == null) {
            throw new BusinessException(404, "任务不存在: id=" + id);
        }
        return Result.ok(task);
    }

    /** POST /api/tasks/{id}/retry - 重试失败任务 */
    @PostMapping("/{id}/retry")
    public Result<Void> retry(@PathVariable Integer id) {
        CollectorTask task = taskMapper.selectById(id);
        if (task == null) {
            throw new BusinessException(404, "任务不存在: id=" + id);
        }
        if (!"failed".equals(task.getStatus()) && !"dead".equals(task.getStatus())) {
            throw new BusinessException("只有 failed 或 dead 状态的任务可以重试");
        }
        taskScheduler.manualTrigger(Collections.singletonList(task.getSourceId()));
        return Result.ok();
    }

    /** POST /api/tasks/trigger - 手动触发单个数据源 */
    @PostMapping("/trigger")
    public Result<Void> trigger(@RequestBody Map<String, Integer> body) {
        Integer sourceId = body.get("sourceId");
        if (sourceId == null) {
            throw new BusinessException("sourceId 不能为空");
        }
        taskScheduler.manualTrigger(Collections.singletonList(sourceId));
        return Result.ok();
    }

    /** POST /api/tasks/batch-trigger - 批量手动触发 */
    @PostMapping("/batch-trigger")
    public Result<Void> batchTrigger(@RequestBody Map<String, List<Integer>> body) {
        List<Integer> sourceIds = body.get("sourceIds");
        if (sourceIds == null || sourceIds.isEmpty()) {
            throw new BusinessException("sourceIds 不能为空");
        }
        taskScheduler.manualTrigger(sourceIds);
        return Result.ok();
    }

    /**
     * 任务统计 — 返回当前队列中 pending/processing 数及今日成功/失败数
     * <p>
     * todaySuccess/todayFailed 基于 createdAt 而非 completedAt 统计，
     * 跨日执行的任务会被归入创建日而非完成日。
     * </p>
     */
    @GetMapping("/stats")
    public Result<Map<String, Object>> stats() {
        LocalDateTime todayStart = LocalDate.now().atStartOfDay();

        long pending    = countByStatus("pending");
        long processing = countByStatus("processing");
        long todaySuccess = taskMapper.selectCount(
                new LambdaQueryWrapper<CollectorTask>()
                        .eq(CollectorTask::getStatus, "success")
                        .ge(CollectorTask::getCreatedAt, todayStart));
        long todayFailed = taskMapper.selectCount(
                new LambdaQueryWrapper<CollectorTask>()
                        .in(CollectorTask::getStatus, List.of("failed", "dead"))
                        .ge(CollectorTask::getCreatedAt, todayStart));

        Map<String, Object> stats = new HashMap<>();
        stats.put("pending", pending);
        stats.put("processing", processing);
        stats.put("today_success", todaySuccess);
        stats.put("today_failed", todayFailed);
        return Result.ok(stats);
    }

    /** GET /api/tasks/schedule-config - 获取当前调度配置 */
    @GetMapping("/schedule-config")
    public Result<Map<String, Object>> getScheduleConfig() {
        Map<String, Object> config = new HashMap<>();
        config.put("work_hours", scheduleConfig.getWorkHours());
        config.put("work_interval", scheduleConfig.getWorkInterval());
        config.put("off_interval", scheduleConfig.getOffInterval());
        config.put("manual_trigger_priority", scheduleConfig.getManualTriggerPriority());
        config.put("scheduled_priority", scheduleConfig.getScheduledPriority());
        return Result.ok(config);
    }

    /**
     * 更新调度配置（仅修改内存，不持久化）
     * <p>
     * 仅在字段值 > 0 时才更新，因此无法将 interval 设为 0。
     * workHours 为空/null 时跳过，不会清空已有配置。
     * 注意：配置变更不会持久化到数据库或文件，重启后恢复默认值。
     * </p>
     */
    @PutMapping("/schedule-config")
    public Result<Void> updateScheduleConfig(@RequestBody ScheduleConfig newConfig) {
        if (newConfig.getWorkInterval() > 0) {
            scheduleConfig.setWorkInterval(newConfig.getWorkInterval());
        }
        if (newConfig.getOffInterval() > 0) {
            scheduleConfig.setOffInterval(newConfig.getOffInterval());
        }
        if (newConfig.getManualTriggerPriority() > 0) {
            scheduleConfig.setManualTriggerPriority(newConfig.getManualTriggerPriority());
        }
        if (newConfig.getScheduledPriority() > 0) {
            scheduleConfig.setScheduledPriority(newConfig.getScheduledPriority());
        }
        if (newConfig.getWorkHours() != null && !newConfig.getWorkHours().isEmpty()) {
            scheduleConfig.setWorkHours(newConfig.getWorkHours());
        }
        return Result.ok();
    }

    // ----------------------------------------------------------------- private

    private long countByStatus(String status) {
        return taskMapper.selectCount(
                new LambdaQueryWrapper<CollectorTask>().eq(CollectorTask::getStatus, status));
    }
}
