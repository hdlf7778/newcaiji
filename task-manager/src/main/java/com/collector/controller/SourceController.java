package com.collector.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
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

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/sources")
@RequiredArgsConstructor
public class SourceController {

    private final SourceService sourceService;
    private final CollectorSourceMapper sourceMapper;

    /** GET /api/sources - list with query params */
    @GetMapping
    public Result<PageResult<CollectorSource>> list(
            @RequestParam(required = false) String status,
            @RequestParam(required = false) String template,
            @RequestParam(required = false) String platform,
            @RequestParam(required = false) String region,
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false) Integer healthScoreMin,
            @RequestParam(required = false) Integer healthScoreMax,
            @RequestParam(defaultValue = "1") Integer page,
            @RequestParam(defaultValue = "20") Integer size) {

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
        query.setHealthScoreMin(healthScoreMin);
        query.setHealthScoreMax(healthScoreMax);
        query.setPage(page);
        query.setSize(size);

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

    /** DELETE /api/sources/{id} - delete */
    @DeleteMapping("/{id}")
    public Result<Void> delete(@PathVariable Integer id) {
        sourceService.delete(id);
        return Result.ok();
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
