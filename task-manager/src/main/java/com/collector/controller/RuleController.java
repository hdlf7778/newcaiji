package com.collector.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.collector.common.PageResult;
import com.collector.common.Result;
import com.collector.entity.CollectorRule;
import com.collector.mapper.CollectorRuleMapper;
import com.collector.service.RuleService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.RestTemplate;

import java.util.HashMap;
import java.util.Map;

/**
 * 采集规则控制器
 * <p>
 * 提供规则的 CRUD 操作，以及代理转发到 Worker 的测试/LLM生成接口。
 * test-list、test-detail、llm-generate 三个端点通过 RestTemplate 转发请求到 Worker API。
 * </p>
 */
@Slf4j
@RestController
@RequestMapping("/api/rules")
@RequiredArgsConstructor
public class RuleController {

    private final RuleService ruleService;
    private final CollectorRuleMapper ruleMapper;
    /** 用于代理转发请求到 Worker 服务 */
    private final RestTemplate restTemplate;

    /** Worker 服务的 API 基础地址，从配置文件注入 */
    @Value("${collector.worker.api-url}")
    private String workerApiUrl;

    /** 分页查询规则列表，支持按 sourceId 和 keyword 过滤 */
    @GetMapping
    public Result<PageResult<CollectorRule>> list(
            @RequestParam(required = false) Integer sourceId,
            @RequestParam(required = false) String keyword,
            @RequestParam(defaultValue = "1") Integer page,
            @RequestParam(defaultValue = "20") Integer pageSize) {
        LambdaQueryWrapper<CollectorRule> wrapper = new LambdaQueryWrapper<>();
        if (sourceId != null) {
            wrapper.eq(CollectorRule::getSourceId, sourceId);
        }
        if (keyword != null && !keyword.isBlank()) {
            wrapper.inSql(CollectorRule::getSourceId,
                    "SELECT id FROM collector_source WHERE name LIKE '%" + keyword.replace("'", "") + "%'");
        }
        wrapper.orderByDesc(CollectorRule::getCreatedAt);
        Page<CollectorRule> p = ruleMapper.selectPage(new Page<>(page, pageSize), wrapper);
        return Result.ok(new PageResult<>(p.getRecords(), p.getTotal(), p.getCurrent(), p.getSize()));
    }

    /** GET /api/rules/{id} — 规则详情 */
    @GetMapping("/{id}")
    public Result<CollectorRule> detail(@PathVariable Integer id) {
        CollectorRule rule = ruleMapper.selectById(id);
        if (rule == null) {
            return Result.fail(404, "规则不存在");
        }
        return Result.ok(rule);
    }

    /** POST /api/rules */
    @PostMapping
    public Result<Void> create(@RequestBody CollectorRule rule) {
        ruleService.create(rule);
        return Result.ok();
    }

    /** PUT /api/rules/{id} */
    @PutMapping("/{id}")
    public Result<Void> update(@PathVariable Integer id, @RequestBody CollectorRule rule) {
        rule.setId(id);
        ruleService.update(rule);
        return Result.ok();
    }

    /** DELETE /api/rules/{id} */
    @DeleteMapping("/{id}")
    public Result<Void> delete(@PathVariable Integer id) {
        ruleService.delete(id);
        return Result.ok();
    }

    /** POST /api/rules/test */
    @PostMapping("/test")
    public Result<Map<String, Object>> testPreview(@RequestParam Integer sourceId) {
        return Result.ok(ruleService.testPreview(sourceId));
    }

    /**
     * 测试列表规则 — 代理转发到 Worker 的 /test-list 端点
     * <p>
     * 异常时返回 Result.ok 包裹的 fallback 而非 Result.fail，前端需检查 body 里的 success 字段。
     * </p>
     */
    @PostMapping("/test-list")
    @SuppressWarnings("unchecked")
    public Result<Map<String, Object>> testList(@RequestBody Map<String, Object> body) {
        try {
            ResponseEntity<Map> resp = restTemplate.postForEntity(
                    workerApiUrl + "/test-list", body, Map.class);
            return Result.ok(resp.getBody() != null ? resp.getBody() : new HashMap<>());
        } catch (Exception e) {
            log.warn("test-list failed: {}", e.getMessage());
            Map<String, Object> fallback = new HashMap<>();
            fallback.put("success", false);
            fallback.put("error", "Worker API 调用失败: " + e.getMessage());
            fallback.put("count", 0);
            return Result.ok(fallback);
        }
    }

    /** POST /api/rules/test-detail — 测试详情规则 */
    @PostMapping("/test-detail")
    @SuppressWarnings("unchecked")
    public Result<Map<String, Object>> testDetail(@RequestBody Map<String, Object> body) {
        try {
            ResponseEntity<Map> resp = restTemplate.postForEntity(
                    workerApiUrl + "/test-detail", body, Map.class);
            return Result.ok(resp.getBody() != null ? resp.getBody() : new HashMap<>());
        } catch (Exception e) {
            log.warn("test-detail failed: {}", e.getMessage());
            Map<String, Object> fallback = new HashMap<>();
            fallback.put("success", false);
            fallback.put("error", "Worker API 调用失败: " + e.getMessage());
            return Result.ok(fallback);
        }
    }

    /** POST /api/rules/llm-generate — LLM 生成规则 */
    @PostMapping("/llm-generate")
    @SuppressWarnings("unchecked")
    public Result<Map<String, Object>> llmGenerate(@RequestBody Map<String, Object> body) {
        try {
            ResponseEntity<Map> resp = restTemplate.postForEntity(
                    workerApiUrl + "/detect-rules", body, Map.class);
            return Result.ok(resp.getBody() != null ? resp.getBody() : new HashMap<>());
        } catch (Exception e) {
            log.warn("llm-generate failed: {}", e.getMessage());
            Map<String, Object> fallback = new HashMap<>();
            fallback.put("success", false);
            fallback.put("error", "LLM 生成失败: " + e.getMessage());
            return Result.ok(fallback);
        }
    }
}
