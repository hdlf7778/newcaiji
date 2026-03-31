package com.collector.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.collector.common.PageResult;
import com.collector.common.Result;
import com.collector.dto.*;
import com.collector.entity.CollectorSource;
import com.collector.enums.SourceStatus;
import com.collector.mapper.CollectorSourceMapper;
import com.collector.service.SourceService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/sources")
@RequiredArgsConstructor
public class SourceController {

    private final SourceService sourceService;
    private final CollectorSourceMapper sourceMapper;
    private final com.collector.mapper.CollectorRuleMapper ruleMapper;
    private final com.collector.service.SourceDetectService sourceDetectService;
    private final org.springframework.web.client.RestTemplate restTemplate;
    private final com.collector.service.SourceDiagnoseService sourceDiagnoseService;

    @org.springframework.beans.factory.annotation.Value("${collector.worker.api-url}")
    private String workerApiUrl;

    /** GET /api/sources - list with query params */
    @GetMapping
    public Result<PageResult<CollectorSource>> list(
            @RequestParam(required = false) String status,
            @RequestParam(required = false) String template,
            @RequestParam(required = false) String platform,
            @RequestParam(required = false) String region,
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false) String scoreRange,
            @RequestParam(required = false) Integer healthScoreMin,
            @RequestParam(required = false) Integer healthScoreMax,
            @RequestParam(defaultValue = "1") Integer page,
            @RequestParam(defaultValue = "20") Integer pageSize) {

        pageSize = Math.min(pageSize, 200);

        SourceQueryDTO query = new SourceQueryDTO();
        if (status != null) {
            query.setStatus(resolveStatus(status));
        }
        if (template != null) {
            query.setTemplate(resolveTemplate(template));
        }
        query.setPlatform(platform);
        query.setRegion(region);
        query.setKeyword(keyword);
        query.setScoreRange(scoreRange);
        query.setHealthScoreMin(healthScoreMin);
        query.setHealthScoreMax(healthScoreMax);
        query.setPage(page);
        query.setSize(pageSize);

        return Result.ok(sourceService.list(query));
    }

    /** GET /api/sources/review-list - pending_review sources */
    @GetMapping("/review-list")
    public Result<PageResult<CollectorSource>> reviewList(
            @RequestParam(defaultValue = "1") Integer page,
            @RequestParam(defaultValue = "20") Integer size) {

        SourceQueryDTO query = new SourceQueryDTO();
        query.setStatus(SourceStatus.PENDING_REVIEW);
        query.setPage(page);
        query.setSize(size);
        return Result.ok(sourceService.list(query));
    }

    /** GET /api/sources/review-all — 审核工作台：所有试采完成的源，支持评分筛选 */
    @GetMapping("/review-all")
    public Result<PageResult<CollectorSource>> reviewAll(
            @RequestParam(defaultValue = "1") Integer page,
            @RequestParam(defaultValue = "20") Integer pageSize,
            @RequestParam(required = false) String scoreFilter) {

        pageSize = Math.min(pageSize, 200);

        LambdaQueryWrapper<CollectorSource> wrapper = new LambdaQueryWrapper<>();
        wrapper.in(CollectorSource::getStatus,
                SourceStatus.TRIAL_PASSED, SourceStatus.TRIAL_FAILED, SourceStatus.PENDING_REVIEW);

        // 按评分范围筛选
        if ("high".equals(scoreFilter)) {
            wrapper.ge(CollectorSource::getTrialScore, 0.8);
        } else if ("medium".equals(scoreFilter)) {
            wrapper.ge(CollectorSource::getTrialScore, 0.6).lt(CollectorSource::getTrialScore, 0.8);
        } else if ("low".equals(scoreFilter)) {
            wrapper.lt(CollectorSource::getTrialScore, 0.6);
        }

        wrapper.orderByDesc(CollectorSource::getTrialScore);
        IPage<CollectorSource> iPage = sourceMapper.selectPage(new Page<>(page, pageSize), wrapper);
        return Result.ok(new PageResult<>(iPage.getRecords(), iPage.getTotal(), iPage.getCurrent(), iPage.getSize()));
    }

    /** GET /api/sources/check-duplicate — 去重检查（name + columnName + url） */
    @GetMapping("/check-duplicate")
    public Result<CollectorSource> checkDuplicate(
            @RequestParam String name,
            @RequestParam(required = false) String columnName,
            @RequestParam String url) {
        LambdaQueryWrapper<CollectorSource> wrapper = new LambdaQueryWrapper<CollectorSource>()
                .and(w -> w
                        .eq(CollectorSource::getUrl, url)
                        .or().eq(CollectorSource::getName, name));
        if (columnName != null && !columnName.isBlank()) {
            wrapper.eq(CollectorSource::getColumnName, columnName);
        }
        CollectorSource existing = sourceMapper.selectOne(wrapper.last("LIMIT 1"));
        return Result.ok(existing); // null 表示不重复
    }

    /** GET /api/sources/stats-by-status */
    @GetMapping("/stats-by-status")
    public Result<Map<String, Long>> statsByStatus() {
        return Result.ok(sourceService.statsByStatus());
    }

    /** GET /api/sources/statistics */
    @GetMapping("/statistics")
    public Result<SourceStatisticsVO> statistics() {
        return Result.ok(sourceService.statistics());
    }

    /** GET /api/sources/{id} - detail */
    @GetMapping("/{id}")
    public Result<SourceDetailVO> detail(@PathVariable Integer id) {
        return Result.ok(sourceService.detail(id));
    }

    /** POST /api/sources - create */
    @PostMapping
    public Result<Integer> create(@Valid @RequestBody SourceCreateDTO dto) {
        return Result.ok(sourceService.create(dto));
    }

    /** PUT /api/sources/{id} - update */
    @PutMapping("/{id}")
    public Result<Void> update(@PathVariable Integer id, @Valid @RequestBody SourceUpdateDTO dto) {
        sourceService.update(id, dto);
        return Result.ok();
    }

    /** POST /api/sources/{id}/trial — 先确保有规则（无则触发检测），再试采写入评分 */
    @PostMapping("/{id}/trial")
    @SuppressWarnings("unchecked")
    public Result<Map<String, Object>> trial(@PathVariable Integer id) {
        CollectorSource source = sourceMapper.selectById(id);
        if (source == null) return Result.fail(404, "采集源不存在");

        // Step 1: 如果没有规则记录，先触发检测生成规则
        Long ruleCount = ruleMapper.selectCount(
            new LambdaQueryWrapper<com.collector.entity.CollectorRule>()
                .eq(com.collector.entity.CollectorRule::getSourceId, id));
        if (ruleCount == 0) {
            try {
                sourceDetectService.detectFull(id);
                source = sourceMapper.selectById(id); // 重新加载
            } catch (Exception ignored) { /* 检测失败不阻塞试采 */ }
        }

        String template = source.getTemplate() != null ? source.getTemplate().getCode() : "static_list";

        // Step 2: 试采
        try {
            Map<String, Object> body = new HashMap<>();
            body.put("source_id", id);
            body.put("url", source.getUrl());
            body.put("template", template);
            body.put("list_rule", new HashMap<>());

            org.springframework.http.ResponseEntity<Map> resp =
                restTemplate
                    .postForEntity(workerApiUrl + "/test-list", body, Map.class);
            Map<String, Object> listRes = resp.getBody() != null ? resp.getBody() : new HashMap<>();

            boolean success = Boolean.TRUE.equals(listRes.get("success"));
            int count = listRes.get("count") != null ? ((Number) listRes.get("count")).intValue() : 0;

            // 评分5维度：列表≥3篇(0.2) + 标题多样(0.2) + 详情有正文(0.2) + 正文>100字(0.2) + 无乱码(0.2)
            int checks = 0;

            // 检查1：列表页匹配≥3篇
            if (success && count >= 3) checks++;

            // 检查2：标题多样性（从列表结果中取）
            java.util.List<String> titles = new java.util.ArrayList<>();
            if (listRes.get("articles") instanceof java.util.List<?> articles) {
                for (Object a : articles) {
                    if (a instanceof Map<?, ?> am) {
                        Object t = am.get("title");
                        if (t != null) titles.add(t.toString());
                    }
                }
            }
            if (titles.size() > 1 && new java.util.HashSet<>(titles).size() > 1) checks++;

            // 检查3-5：详情页正文（取第一篇测试）
            String firstUrl = null;
            if (listRes.get("articles") instanceof java.util.List<?> arts && !arts.isEmpty()) {
                Object first = arts.get(0);
                if (first instanceof Map<?, ?> fm) {
                    Object u = fm.get("url");
                    if (u != null) firstUrl = u.toString();
                }
            }
            if (firstUrl != null) {
                try {
                    Map<String, Object> detailBody = new HashMap<>();
                    detailBody.put("source_id", id);
                    detailBody.put("url", firstUrl);
                    detailBody.put("template", template);
                    detailBody.put("detail_rule", new HashMap<>());
                    var detailResp = restTemplate
                        .postForEntity(workerApiUrl + "/test-detail", detailBody, Map.class);
                    Map<String, Object> detailRes = detailResp.getBody() != null ? detailResp.getBody() : new HashMap<>();
                    boolean detailOk = Boolean.TRUE.equals(detailRes.get("success"));
                    int contentLen = detailRes.get("content_length") != null
                        ? ((Number) detailRes.get("content_length")).intValue() : 0;
                    if (detailOk && contentLen > 0) checks++;       // 检查3：有正文
                    if (detailOk && contentLen > 100) checks++;     // 检查4：正文>100字
                    // 检查5：无乱码（非CJK可打印字符比例<5%视为正常）
                    String preview = detailRes.get("content_preview") != null
                        ? detailRes.get("content_preview").toString() : "";
                    if (detailOk && preview.length() > 50) {
                        long badChars = preview.chars().filter(ch ->
                            !(ch >= 0x4e00 && ch <= 0x9fff)   // 中文
                            && !(ch >= 0x3000 && ch <= 0x303f) // 中文标点
                            && !(ch >= 0xff00 && ch <= 0xffef) // 全角
                            && !(ch >= 0x20 && ch <= 0x7e)     // ASCII可打印
                            && ch != '\n' && ch != '\r' && ch != '\t'
                        ).count();
                        if ((double) badChars / preview.length() < 0.05) checks++;
                    }
                } catch (Exception ignored) {}
            }

            double score = Math.round(checks / 5.0 * 100) / 100.0;

            source.setTrialScore(java.math.BigDecimal.valueOf(score));
            source.setTrialAt(java.time.LocalDateTime.now());
            source.setStatus(score >= 0.4
                ? SourceStatus.TRIAL_PASSED
                : SourceStatus.TRIAL_FAILED);
            sourceMapper.updateById(source);

            return Result.ok(Map.of("success", success, "count", count, "score", score, "checks", checks));
        } catch (Exception e) {
            source.setTrialScore(java.math.BigDecimal.ZERO);
            source.setStatus(SourceStatus.TRIAL_FAILED);
            sourceMapper.updateById(source);
            return Result.ok(Map.of("success", false, "error", String.valueOf(e.getMessage()), "score", 0));
        }
    }

    /** POST /api/sources/{id}/diagnose — analyze why trial failed */
    @PostMapping("/{id}/diagnose")
    public Result<Map<String, Object>> diagnose(@PathVariable Integer id) {
        return Result.ok(sourceDiagnoseService.diagnose(id));
    }

    /** POST /api/sources/{id}/auto-repair — execute fix chain */
    @PostMapping("/{id}/auto-repair")
    public Result<Map<String, Object>> autoRepair(@PathVariable Integer id) {
        return Result.ok(sourceDiagnoseService.autoRepair(id));
    }

    /** POST /api/sources/{id}/manual-assist-repair — user provides hint, LLM generates rules, auto test */
    @PostMapping("/{id}/manual-assist-repair")
    public Result<Map<String, Object>> manualAssistRepair(
            @PathVariable Integer id,
            @RequestBody Map<String, String> body) {
        String hint = body.get("hint");
        if (hint == null || hint.isBlank()) {
            return Result.fail(400, "请输入分析描述");
        }
        return Result.ok(sourceDiagnoseService.manualAssistRepair(id, hint));
    }

    /** DELETE /api/sources/{id} - delete */
    @DeleteMapping("/{id}")
    public Result<Void> delete(@PathVariable Integer id) {
        sourceService.delete(id);
        return Result.ok();
    }

    /** POST /api/sources/batch-create - batch create from JSON array */
    @PostMapping("/batch-create")
    public Result<SourceImportDTO> batchCreate(@RequestBody List<SourceCreateDTO> items) {
        if (items.size() > 500) {
            return Result.fail(400, "单批次最多500条");
        }
        return Result.ok(sourceService.batchCreate(items));
    }

    /** POST /api/sources/import - file upload import */
    @PostMapping("/import")
    public Result<SourceImportDTO> importFile(
            @RequestParam("file") MultipartFile file,
            @RequestParam(required = false, defaultValue = "5") Integer defaultPriority) {
        return Result.ok(sourceService.importFromFile(file, defaultPriority));
    }

    /** POST /api/sources/import-platform - platform import */
    @PostMapping("/import-platform")
    public Result<SourceImportDTO> importPlatform(
            @RequestParam String platform,
            @RequestParam("file") MultipartFile file) {
        return Result.ok(sourceService.importPlatform(platform, file));
    }

    /** POST /api/sources/{id}/approve */
    @PostMapping("/{id}/approve")
    public Result<Void> approve(
            @PathVariable Integer id,
            @RequestParam(required = false, defaultValue = "system") String operator) {
        sourceService.approve(id, operator);
        return Result.ok();
    }

    /** POST /api/sources/{id}/reject */
    @PostMapping("/{id}/reject")
    public Result<Void> reject(@PathVariable Integer id) {
        sourceService.reject(id);
        return Result.ok();
    }

    /** POST /api/sources/batch-approve */
    @PostMapping("/batch-approve")
    public Result<Void> batchApprove(@RequestBody BatchApproveRequest req) {
        sourceService.batchApprove(req.getSourceIds(), req.getOperator());
        return Result.ok();
    }

    /** POST /api/sources/{id}/pause */
    @PostMapping("/{id}/pause")
    public Result<Void> pause(@PathVariable Integer id) {
        sourceService.pause(id);
        return Result.ok();
    }

    /** POST /api/sources/{id}/resume */
    @PostMapping("/{id}/resume")
    public Result<Void> resume(@PathVariable Integer id) {
        sourceService.resume(id);
        return Result.ok();
    }

    /** POST /api/sources/{id}/reset */
    @PostMapping("/{id}/reset")
    public Result<Void> reset(@PathVariable Integer id) {
        sourceService.reset(id);
        return Result.ok();
    }

    /** POST /api/sources/{id}/retire */
    @PostMapping("/{id}/retire")
    public Result<Void> retire(@PathVariable Integer id) {
        sourceService.retire(id);
        return Result.ok();
    }

    // ----------------------------------------------------------------- Helpers

    private SourceStatus resolveStatus(String value) {
        for (SourceStatus s : SourceStatus.values()) {
            if (s.getCode().equalsIgnoreCase(value) || s.name().equalsIgnoreCase(value)) {
                return s;
            }
        }
        throw new com.collector.common.BusinessException("无效的 status 值: " + value);
    }

    private com.collector.enums.TemplateType resolveTemplate(String value) {
        for (com.collector.enums.TemplateType t : com.collector.enums.TemplateType.values()) {
            if (t.getCode().equalsIgnoreCase(value) || t.name().equalsIgnoreCase(value)) {
                return t;
            }
        }
        throw new com.collector.common.BusinessException("无效的 template 值: " + value);
    }

    // ----------------------------------------------------------------- Inner DTO

    @lombok.Data
    public static class BatchApproveRequest {
        private List<Integer> sourceIds;
        private String operator = "system";
    }
}
