package com.collector.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.collector.common.PageResult;
import com.collector.common.Result;
import com.collector.entity.DeadLetterQueue;
import com.collector.mapper.DeadLetterQueueMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.util.StringUtils;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

@Slf4j
@RestController
@RequestMapping("/api/dead-letters")
@RequiredArgsConstructor
public class DeadLetterController {

    private final DeadLetterQueueMapper deadLetterMapper;
    private final StringRedisTemplate redisTemplate;

    /**
     * GET /api/dead-letters - paginated list with optional filters
     */
    @GetMapping
    public Result<PageResult<DeadLetterQueue>> list(
            @RequestParam(required = false) String errorType,
            @RequestParam(required = false) String handleStatus,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) LocalDateTime startTime,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) LocalDateTime endTime,
            @RequestParam(defaultValue = "1") long page,
            @RequestParam(defaultValue = "20") long size) {

        LambdaQueryWrapper<DeadLetterQueue> wrapper = new LambdaQueryWrapper<>();
        if (StringUtils.hasText(errorType)) {
            wrapper.eq(DeadLetterQueue::getErrorType, errorType);
        }
        if (StringUtils.hasText(handleStatus)) {
            wrapper.eq(DeadLetterQueue::getHandleStatus, handleStatus);
        }
        if (startTime != null) {
            wrapper.ge(DeadLetterQueue::getCreatedAt, startTime);
        }
        if (endTime != null) {
            wrapper.le(DeadLetterQueue::getCreatedAt, endTime);
        }
        wrapper.orderByDesc(DeadLetterQueue::getCreatedAt);

        IPage<DeadLetterQueue> iPage = deadLetterMapper.selectPage(new Page<>(page, size), wrapper);
        PageResult<DeadLetterQueue> result = new PageResult<>(
                iPage.getRecords(), iPage.getTotal(), iPage.getCurrent(), iPage.getSize());
        return Result.ok(result);
    }

    /**
     * POST /api/dead-letters/{id}/retry - retry a single dead letter task
     */
    @PostMapping("/{id}/retry")
    public Result<Void> retry(@PathVariable Integer id) {
        DeadLetterQueue item = deadLetterMapper.selectById(id);
        if (item == null) {
            return Result.fail("Dead letter not found: " + id);
        }
        pushToQueue(item);

        item.setHandleStatus("retried");
        item.setHandledAt(LocalDateTime.now());
        deadLetterMapper.updateById(item);

        log.info("Dead letter retried: id={}, url={}", id, item.getUrl());
        return Result.ok();
    }

    /**
     * POST /api/dead-letters/{id}/ignore - mark a dead letter as ignored
     */
    @PostMapping("/{id}/ignore")
    public Result<Void> ignore(@PathVariable Integer id) {
        DeadLetterQueue item = deadLetterMapper.selectById(id);
        if (item == null) {
            return Result.fail("Dead letter not found: " + id);
        }
        item.setHandleStatus("ignored");
        item.setHandledAt(LocalDateTime.now());
        deadLetterMapper.updateById(item);

        log.info("Dead letter ignored: id={}, url={}", id, item.getUrl());
        return Result.ok();
    }

    /**
     * POST /api/dead-letters/batch-retry - batch retry by IDs
     */
    @PostMapping("/batch-retry")
    public Result<Map<String, Object>> batchRetry(@RequestBody Map<String, List<Integer>> body) {
        List<Integer> ids = body.get("ids");
        if (ids == null || ids.isEmpty()) {
            return Result.fail("ids must not be empty");
        }

        int succeeded = 0;
        for (Integer id : ids) {
            DeadLetterQueue item = deadLetterMapper.selectById(id);
            if (item != null) {
                pushToQueue(item);
                item.setHandleStatus("retried");
                item.setHandledAt(LocalDateTime.now());
                deadLetterMapper.updateById(item);
                succeeded++;
            }
        }

        log.info("Batch retry: requested={}, succeeded={}", ids.size(), succeeded);
        return Result.ok(Map.of("requested", ids.size(), "succeeded", succeeded));
    }

    /**
     * POST /api/dead-letters/batch-ignore - batch ignore by IDs
     */
    @PostMapping("/batch-ignore")
    public Result<Map<String, Object>> batchIgnore(@RequestBody Map<String, List<Integer>> body) {
        List<Integer> ids = body.get("ids");
        if (ids == null || ids.isEmpty()) {
            return Result.fail("ids must not be empty");
        }

        int succeeded = 0;
        for (Integer id : ids) {
            DeadLetterQueue item = deadLetterMapper.selectById(id);
            if (item != null) {
                item.setHandleStatus("ignored");
                item.setHandledAt(LocalDateTime.now());
                deadLetterMapper.updateById(item);
                succeeded++;
            }
        }

        log.info("Batch ignore: requested={}, succeeded={}", ids.size(), succeeded);
        return Result.ok(Map.of("requested", ids.size(), "succeeded", succeeded));
    }

    /**
     * Push a dead letter task back to the appropriate Redis queue
     */
    private void pushToQueue(DeadLetterQueue item) {
        try {
            String queueKey = "browser".equalsIgnoreCase(item.getTemplate())
                    ? "task:browser:pending"
                    : "task:http:pending";
            double score = System.currentTimeMillis();
            redisTemplate.opsForZSet().add(queueKey, item.getTaskId(), score);
            log.debug("Pushed task {} back to queue {}", item.getTaskId(), queueKey);
        } catch (Exception e) {
            log.warn("Failed to push task {} to Redis queue: {}", item.getTaskId(), e.getMessage());
        }
    }
}
