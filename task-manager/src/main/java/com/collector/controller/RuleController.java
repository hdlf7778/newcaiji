package com.collector.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.collector.common.BusinessException;
import com.collector.common.PageResult;
import com.collector.common.Result;
import com.collector.entity.CollectorRule;
import com.collector.entity.CollectorSource;
import com.collector.mapper.CollectorRuleMapper;
import com.collector.mapper.CollectorSourceMapper;
import com.collector.service.RuleService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.RestTemplate;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

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
    private final CollectorSourceMapper sourceMapper;
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
        pageSize = Math.min(pageSize, 200);

        LambdaQueryWrapper<CollectorRule> wrapper = new LambdaQueryWrapper<>();
        if (sourceId != null) {
            wrapper.eq(CollectorRule::getSourceId, sourceId);
        }
        if (keyword != null && !keyword.isBlank()) {
            List<Integer> matchingSourceIds = sourceMapper.selectList(
                    new LambdaQueryWrapper<CollectorSource>()
                            .like(CollectorSource::getName, keyword)
                            .select(CollectorSource::getId))
                    .stream()
                    .map(CollectorSource::getId)
                    .collect(Collectors.toList());
            if (matchingSourceIds.isEmpty()) {
                return Result.ok(new PageResult<>(List.of(), 0L, (long) page, (long) pageSize));
            }
            wrapper.in(CollectorRule::getSourceId, matchingSourceIds);
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
        rule.setId(null);
        rule.setCreatedAt(null);
        rule.setUpdatedAt(null);
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
    /** 确保 Worker 请求体中 template 字段非空 */
    private void ensureTemplate(Map<String, Object> body) {
        if (body.get("template") == null || body.get("template").toString().isBlank()) {
            body.put("template", "static_list");
        }
    }

    /** 校验 URL 防止 SSRF 攻击 */
    private void validateUserUrl(String url) {
        if (url == null || url.isBlank()) return;
        try {
            java.net.URI uri = java.net.URI.create(url);
            String scheme = uri.getScheme();
            if (scheme == null || (!scheme.equals("http") && !scheme.equals("https"))) {
                throw new BusinessException("仅允许 http/https 协议");
            }
            String host = uri.getHost();
            if (host == null) throw new BusinessException("无效的URL");
            String lower = host.toLowerCase();
            if (lower.equals("localhost") || lower.equals("127.0.0.1") || lower.equals("0.0.0.0")
                || lower.equals("::1") || lower.startsWith("169.254.") || lower.startsWith("10.")
                || lower.startsWith("172.16.") || lower.startsWith("192.168.") || lower.endsWith(".local")
                || lower.endsWith(".internal")) {
                throw new BusinessException("禁止访问内网地址");
            }
        } catch (IllegalArgumentException e) {
            throw new BusinessException("URL格式无效");
        }
    }

    @PostMapping("/test-list")
    @SuppressWarnings("unchecked")
    public Result<Map<String, Object>> testList(@RequestBody Map<String, Object> body) {
        try {
            validateUserUrl(body.get("url") != null ? body.get("url").toString() : null);
            ensureTemplate(body);
            ResponseEntity<Map> resp = restTemplate.postForEntity(
                    workerApiUrl + "/test-list", body, Map.class);
            return Result.ok(resp.getBody() != null ? resp.getBody() : new HashMap<>());
        } catch (Exception e) {
            log.warn("test-list failed: {}", e.getMessage(), e);
            Map<String, Object> fallback = new HashMap<>();
            fallback.put("success", false);
            fallback.put("error", e instanceof BusinessException ? e.getMessage() : "规则测试暂时不可用，请稍后重试");
            fallback.put("count", 0);
            return Result.ok(fallback);
        }
    }

    /** POST /api/rules/test-detail — 测试详情规则 */
    @PostMapping("/test-detail")
    @SuppressWarnings("unchecked")
    public Result<Map<String, Object>> testDetail(@RequestBody Map<String, Object> body) {
        try {
            validateUserUrl(body.get("url") != null ? body.get("url").toString() : null);
            ensureTemplate(body);
            ResponseEntity<Map> resp = restTemplate.postForEntity(
                    workerApiUrl + "/test-detail", body, Map.class);
            return Result.ok(resp.getBody() != null ? resp.getBody() : new HashMap<>());
        } catch (Exception e) {
            log.warn("test-detail failed: {}", e.getMessage(), e);
            Map<String, Object> fallback = new HashMap<>();
            fallback.put("success", false);
            fallback.put("error", e instanceof BusinessException ? e.getMessage() : "规则测试暂时不可用，请稍后重试");
            return Result.ok(fallback);
        }
    }

    /** POST /api/rules/llm-generate — LLM 生成规则 */
    @PostMapping("/llm-generate")
    @SuppressWarnings("unchecked")
    public Result<Map<String, Object>> llmGenerate(@RequestBody Map<String, Object> body) {
        try {
            validateUserUrl(body.get("url") != null ? body.get("url").toString() : null);
            ResponseEntity<Map> resp = restTemplate.postForEntity(
                    workerApiUrl + "/detect-rules", body, Map.class);
            return Result.ok(resp.getBody() != null ? resp.getBody() : new HashMap<>());
        } catch (Exception e) {
            log.error("llm-generate failed: {}", e.getMessage(), e);
            Map<String, Object> fallback = new HashMap<>();
            fallback.put("success", false);
            fallback.put("error", e instanceof BusinessException ? e.getMessage() : "规则测试暂时不可用，请稍后重试");
            return Result.ok(fallback);
        }
    }
}
