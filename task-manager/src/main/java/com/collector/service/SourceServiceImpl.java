package com.collector.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.collector.common.BusinessException;
import com.collector.common.PageResult;
import com.collector.dto.*;
import com.collector.entity.CollectorLog;
import com.collector.entity.CollectorRule;
import com.collector.entity.CollectorSource;
import com.collector.enums.SourceStatus;
import com.collector.enums.TemplateType;
import com.collector.mapper.CollectorLogMapper;
import com.collector.mapper.CollectorRuleMapper;
import com.collector.mapper.CollectorSourceMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.apache.poi.ss.usermodel.*;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;
import org.springframework.web.multipart.MultipartFile;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.time.LocalDateTime;
import java.util.*;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

/**
 * 数据源服务实现 — 管理采集数据源的完整生命周期
 * <p>
 * 包含：CRUD、文件导入（CSV/Excel）、状态流转（审批/拒绝/暂停/恢复/重置/退役）、统计。
 * detail() 返回的日志使用 snake_case 键名（如 created_at）以匹配前端约定。
 * buildRulInfoJson() 手动拼接 JSON 字符串，如果字段值包含引号或特殊字符可能导致 JSON 格式错误。
 * </p>
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class SourceServiceImpl implements SourceService {

    /** URL 格式校验：要求以 http:// 或 https:// 开头且包含至少一个点号 */
    private static final Pattern URL_PATTERN = Pattern.compile("^https?://.+\\..+");

    private final CollectorSourceMapper sourceMapper;
    private final CollectorLogMapper logMapper;
    private final CollectorRuleMapper ruleMapper;

    // ------------------------------------------------------------------ CRUD

    @Override
    public PageResult<CollectorSource> list(SourceQueryDTO query) {
        LambdaQueryWrapper<CollectorSource> wrapper = new LambdaQueryWrapper<>();

        if (query.getStatus() != null) {
            wrapper.eq(CollectorSource::getStatus, query.getStatus());
        }
        if (query.getTemplate() != null) {
            wrapper.eq(CollectorSource::getTemplate, query.getTemplate());
        }
        if (StringUtils.hasText(query.getPlatform())) {
            wrapper.eq(CollectorSource::getPlatform, query.getPlatform());
        }
        if (StringUtils.hasText(query.getRegion())) {
            wrapper.eq(CollectorSource::getRegion, query.getRegion());
        }
        // MyBatis-Plus like() 自动加 %，无需手动包裹
        if (StringUtils.hasText(query.getKeyword())) {
            wrapper.and(w -> w
                    .like(CollectorSource::getName, query.getKeyword())
                    .or().like(CollectorSource::getUrl, query.getKeyword())
                    .or().like(CollectorSource::getColumnName, query.getKeyword()));
        }
        if (query.getHealthScoreMin() != null) {
            wrapper.ge(CollectorSource::getHealthScore, query.getHealthScoreMin());
        }
        if (query.getHealthScoreMax() != null) {
            wrapper.le(CollectorSource::getHealthScore, query.getHealthScoreMax());
        }

        wrapper.orderByDesc(CollectorSource::getCreatedAt);

        int page = query.getPage() == null ? 1 : query.getPage();
        int size = query.getSize() == null ? 20 : query.getSize();

        IPage<CollectorSource> iPage = sourceMapper.selectPage(new Page<>(page, size), wrapper);
        return new PageResult<>(iPage.getRecords(), iPage.getTotal(), iPage.getCurrent(), iPage.getSize());
    }

    /**
     * 数据源详情 — 包含最新规则信息和最近20条操作日志
     * <p>
     * 日志 Map 的 key 使用 snake_case（如 created_at）以适配前端。
     * rulInfo 变量名疑似拼写错误，应为 ruleInfo。
     * </p>
     */
    @Override
    public SourceDetailVO detail(Integer id) {
        CollectorSource source = getSourceOrThrow(id);

        // 获取该数据源最新的一条采集规则
        CollectorRule rule = ruleMapper.selectOne(
                new LambdaQueryWrapper<CollectorRule>()
                        .eq(CollectorRule::getSourceId, id)
                        .orderByDesc(CollectorRule::getCreatedAt)
                        .last("LIMIT 1"));

        // 获取最近20条操作日志
        List<CollectorLog> logs = logMapper.selectList(
                new LambdaQueryWrapper<CollectorLog>()
                        .eq(CollectorLog::getSourceId, id)
                        .orderByDesc(CollectorLog::getCreatedAt)
                        .last("LIMIT 20"));

        List<Map<String, Object>> recentLogs = logs.stream()
                .map(l -> {
                    Map<String, Object> m = new LinkedHashMap<>();
                    m.put("id", l.getId());
                    m.put("action", l.getAction());
                    m.put("level", l.getLevel());
                    m.put("message", l.getMessage());
                    m.put("operator", l.getOperator());
                    m.put("created_at", l.getCreatedAt());
                    return m;
                })
                .collect(Collectors.toList());

        // 注意：变量名 rulInfo 疑似拼写错误（应为 ruleInfo），但需同步修改 VO 字段
        String rulInfo = null;
        if (rule != null) {
            rulInfo = buildRulInfoJson(rule);
        }

        return SourceDetailVO.builder()
                .id(source.getId())
                .name(source.getName())
                .columnName(source.getColumnName())
                .url(source.getUrl())
                .sourceType(source.getSourceType())
                .template(source.getTemplate())
                .platform(source.getPlatform())
                .platformParams(source.getPlatformParams())
                .region(source.getRegion())
                .priority(source.getPriority())
                .checkInterval(source.getCheckInterval())
                .encoding(source.getEncoding())
                .status(source.getStatus())
                .failCount(source.getFailCount())
                .totalArticles(source.getTotalArticles())
                .lastSuccessAt(source.getLastSuccessAt())
                .lastArticleDate(source.getLastArticleDate())
                .trialScore(source.getTrialScore())
                .trialResult(source.getTrialResult())
                .trialAt(source.getTrialAt())
                .approvedBy(source.getApprovedBy())
                .approvedAt(source.getApprovedAt())
                .healthScore(source.getHealthScore())
                .avgUpdateIntervalHours(source.getAvgUpdateIntervalHours())
                .quietDays(source.getQuietDays())
                .quietConfirmedAt(source.getQuietConfirmedAt())
                .createdAt(source.getCreatedAt())
                .updatedAt(source.getUpdatedAt())
                .rulInfo(rulInfo)
                .recentLogs(recentLogs)
                .build();
    }

    @Override
    public Integer create(SourceCreateDTO dto) {
        validateUrl(dto.getUrl());
        checkUrlColumnNameUnique(dto.getUrl(), dto.getColumnName(), null);

        CollectorSource source = CollectorSource.builder()
                .name(dto.getName())
                .url(dto.getUrl())
                .columnName(dto.getColumnName())
                .sourceType(dto.getSourceType())
                .template(dto.getTemplate())
                .platform(dto.getPlatform())
                .platformParams(dto.getPlatformParams())
                .region(dto.getRegion())
                .priority(dto.getPriority() != null ? dto.getPriority() : 5)
                .checkInterval(dto.getCheckInterval())
                .encoding(dto.getEncoding())
                .status(SourceStatus.PENDING_DETECT)
                .build();

        sourceMapper.insert(source);
        return source.getId();
    }

    @Override
    public void update(Integer id, SourceUpdateDTO dto) {
        CollectorSource existing = getSourceOrThrow(id);
        validateUrl(dto.getUrl());
        checkUrlColumnNameUnique(dto.getUrl(), dto.getColumnName(), id);

        existing.setName(dto.getName());
        existing.setUrl(dto.getUrl());
        existing.setColumnName(dto.getColumnName());
        existing.setSourceType(dto.getSourceType());
        existing.setTemplate(dto.getTemplate());
        existing.setPlatform(dto.getPlatform());
        existing.setPlatformParams(dto.getPlatformParams());
        existing.setRegion(dto.getRegion());
        existing.setPriority(dto.getPriority() != null ? dto.getPriority() : 5);
        existing.setCheckInterval(dto.getCheckInterval());
        existing.setEncoding(dto.getEncoding());
        if (dto.getStatus() != null) {
            existing.setStatus(dto.getStatus());
        }

        sourceMapper.updateById(existing);
    }

    @Override
    public void delete(Integer id) {
        getSourceOrThrow(id);
        sourceMapper.deleteById(id);
    }

    // --------------------------------------------------------------- Import

    @Override
    public SourceImportDTO importFromFile(MultipartFile file, Integer defaultPriority) {
        String filename = file.getOriginalFilename() != null ? file.getOriginalFilename().toLowerCase() : "";
        if (filename.endsWith(".csv")) {
            return importFromCsv(file, null, defaultPriority);
        } else if (filename.endsWith(".xlsx") || filename.endsWith(".xls")) {
            return importFromExcel(file, null, defaultPriority);
        } else {
            throw new BusinessException("不支持的文件格式，请上传 CSV 或 Excel 文件");
        }
    }

    @Override
    public SourceImportDTO importPlatform(String platform, MultipartFile file) {
        String filename = file.getOriginalFilename() != null ? file.getOriginalFilename().toLowerCase() : "";
        if (filename.endsWith(".csv")) {
            return importFromCsv(file, platform, null);
        } else if (filename.endsWith(".xlsx") || filename.endsWith(".xls")) {
            return importFromExcel(file, platform, null);
        } else {
            throw new BusinessException("不支持的文件格式，请上传 CSV 或 Excel 文件");
        }
    }

    // -------------------------------------------------- Status management

    @Override
    public void approve(Integer id, String operator) {
        CollectorSource source = getSourceOrThrow(id);
        if (source.getStatus() != SourceStatus.PENDING_REVIEW
                && source.getStatus() != SourceStatus.TRIAL_PASSED) {
            throw new BusinessException("当前状态不允许审批通过，需处于 pending_review 或 trial_passed 状态");
        }
        source.setStatus(SourceStatus.APPROVED);
        source.setApprovedBy(operator);
        source.setApprovedAt(LocalDateTime.now());
        sourceMapper.updateById(source);
        writeLog(id, "approve", "INFO", "审批通过", operator);
    }

    @Override
    public void reject(Integer id) {
        CollectorSource source = getSourceOrThrow(id);
        if (source.getStatus() != SourceStatus.PENDING_REVIEW
                && source.getStatus() != SourceStatus.TRIAL_PASSED
                && source.getStatus() != SourceStatus.TRIAL_FAILED) {
            throw new BusinessException("当前状态不允许拒绝");
        }
        source.setStatus(SourceStatus.RETIRED);
        sourceMapper.updateById(source);
        writeLog(id, "reject", "INFO", "审批拒绝，已退役", null);
    }

    @Override
    public void batchApprove(List<Integer> ids, String operator) {
        if (ids == null || ids.isEmpty()) {
            throw new BusinessException("ids 不能为空");
        }
        for (Integer id : ids) {
            approve(id, operator);
        }
    }

    @Override
    public void pause(Integer id) {
        CollectorSource source = getSourceOrThrow(id);
        if (source.getStatus() != SourceStatus.ACTIVE) {
            throw new BusinessException("只有 active 状态的数据源才能暂停");
        }
        source.setStatus(SourceStatus.PAUSED);
        sourceMapper.updateById(source);
        writeLog(id, "pause", "INFO", "已暂停", null);
    }

    @Override
    public void resume(Integer id) {
        CollectorSource source = getSourceOrThrow(id);
        if (source.getStatus() != SourceStatus.PAUSED) {
            throw new BusinessException("只有 paused 状态的数据源才能恢复");
        }
        source.setStatus(SourceStatus.ACTIVE);
        sourceMapper.updateById(source);
        writeLog(id, "resume", "INFO", "已恢复运行", null);
    }

    @Override
    public void reset(Integer id) {
        CollectorSource source = getSourceOrThrow(id);
        source.setStatus(SourceStatus.PENDING_DETECT);
        source.setFailCount(0);
        sourceMapper.updateById(source);
        writeLog(id, "reset", "INFO", "已重置为待检测", null);
    }

    @Override
    public void retire(Integer id) {
        CollectorSource source = getSourceOrThrow(id);
        source.setStatus(SourceStatus.RETIRED);
        sourceMapper.updateById(source);
        writeLog(id, "retire", "INFO", "已退役", null);
    }

    // ----------------------------------------------------------- Statistics

    @Override
    public SourceStatisticsVO statistics() {
        List<CollectorSource> all = sourceMapper.selectList(null);

        long total = all.size();

        Map<String, Long> statusCounts = all.stream()
                .filter(s -> s.getStatus() != null)
                .collect(Collectors.groupingBy(s -> s.getStatus().getCode(), Collectors.counting()));

        Map<String, Long> templateCounts = all.stream()
                .filter(s -> s.getTemplate() != null)
                .collect(Collectors.groupingBy(s -> s.getTemplate().getCode(), Collectors.counting()));

        Map<String, Long> healthDistribution = new LinkedHashMap<>();
        healthDistribution.put("excellent", all.stream().filter(s -> s.getHealthScore() != null && s.getHealthScore() >= 90).count());
        healthDistribution.put("good", all.stream().filter(s -> s.getHealthScore() != null && s.getHealthScore() >= 70 && s.getHealthScore() < 90).count());
        healthDistribution.put("warning", all.stream().filter(s -> s.getHealthScore() != null && s.getHealthScore() >= 50 && s.getHealthScore() < 70).count());
        healthDistribution.put("danger", all.stream().filter(s -> s.getHealthScore() != null && s.getHealthScore() < 50).count());

        return SourceStatisticsVO.builder()
                .total(total)
                .statusCounts(statusCounts)
                .templateCounts(templateCounts)
                .healthDistribution(healthDistribution)
                .build();
    }

    @Override
    public Map<String, Long> statsByStatus() {
        List<CollectorSource> all = sourceMapper.selectList(
                new LambdaQueryWrapper<CollectorSource>().select(CollectorSource::getStatus));
        return all.stream()
                .filter(s -> s.getStatus() != null)
                .collect(Collectors.groupingBy(s -> s.getStatus().getCode(), Collectors.counting()));
    }

    // --------------------------------------------------------- Private helpers

    private CollectorSource getSourceOrThrow(Integer id) {
        CollectorSource source = sourceMapper.selectById(id);
        if (source == null) {
            throw new BusinessException(404, "数据源不存在: id=" + id);
        }
        return source;
    }

    private void validateUrl(String url) {
        if (!StringUtils.hasText(url) || !URL_PATTERN.matcher(url).matches()) {
            throw new BusinessException("URL 格式不合法，需以 http:// 或 https:// 开头");
        }
    }

    /** 校验 url + columnName 组合唯一性，excludeId 用于更新时排除自身 */
    private void checkUrlColumnNameUnique(String url, String columnName, Integer excludeId) {
        LambdaQueryWrapper<CollectorSource> wrapper = new LambdaQueryWrapper<CollectorSource>()
                .eq(CollectorSource::getUrl, url);
        if (StringUtils.hasText(columnName)) {
            wrapper.eq(CollectorSource::getColumnName, columnName);
        } else {
            wrapper.isNull(CollectorSource::getColumnName);
        }
        if (excludeId != null) {
            wrapper.ne(CollectorSource::getId, excludeId);
        }
        Long count = sourceMapper.selectCount(wrapper);
        if (count > 0) {
            throw new BusinessException("url + columnName 组合已存在，请勿重复添加");
        }
    }

    /** 写入操作日志，失败时仅打印警告不抛异常（日志写入不影响主流程） */
    private void writeLog(Integer sourceId, String action, String level, String message, String operator) {
        try {
            CollectorLog logEntry = CollectorLog.builder()
                    .sourceId(sourceId)
                    .action(action)
                    .level(level)
                    .message(message)
                    .operator(operator)
                    .build();
            logMapper.insert(logEntry);
        } catch (Exception e) {
            log.warn("写入操作日志失败 sourceId={} action={}", sourceId, action, e);
        }
    }

    /**
     * 手动拼接规则摘要 JSON — 存在注入风险
     * <p>
     * 如果 generatedBy、listRule、detailRule 包含双引号或反斜杠等特殊字符，
     * 会导致生成的 JSON 格式错误。建议改用 Jackson ObjectMapper 序列化。
     * </p>
     */
    private String buildRulInfoJson(CollectorRule rule) {
        return String.format(
                "{\"id\":%d,\"ruleVersion\":%s,\"generatedBy\":\"%s\",\"listRule\":%s,\"detailRule\":%s}",
                rule.getId(),
                rule.getRuleVersion() != null ? rule.getRuleVersion().toString() : "null",
                rule.getGeneratedBy() != null ? rule.getGeneratedBy() : "",
                rule.getListRule() != null ? rule.getListRule() : "null",
                rule.getDetailRule() != null ? rule.getDetailRule() : "null"
        );
    }

    // ------------------------------------------------------- CSV / Excel 导入

    /**
     * CSV 导入 — 期望列顺序：url, name, column_name, region, category, priority, template, platform
     * <p>
     * 第一行视为表头跳过。逐行校验 URL 格式并检查重复。
     * 注意：CSV 解析使用简单 split(",")，无法处理字段内含逗号（带引号）的情况。
     * </p>
     */
    private SourceImportDTO importFromCsv(MultipartFile file, String platformOverride, Integer defaultPriority) {
        SourceImportDTO.SourceImportDTOBuilder result = SourceImportDTO.builder();
        List<SourceImportDTO.ErrorItem> errors = new ArrayList<>();
        int total = 0, imported = 0, duplicates = 0, invalid = 0;

        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(file.getInputStream(), "UTF-8"))) {

            String headerLine = reader.readLine(); // skip header
            if (headerLine == null) {
                return result.total(0).imported(0).duplicates(0).invalid(0).errors(errors).build();
            }

            String line;
            int row = 1;
            while ((line = reader.readLine()) != null) {
                row++;
                if (!StringUtils.hasText(line)) continue;
                total++;

                String[] cols = line.split(",", -1);
                // Expected columns: url,name,column_name,region,category,priority,template,platform
                String url = cols.length > 0 ? cols[0].trim() : "";
                String name = cols.length > 1 ? cols[1].trim() : "";
                String columnName = cols.length > 2 ? cols[2].trim() : "";
                String region = cols.length > 3 ? cols[3].trim() : "";
                String priority = cols.length > 5 ? cols[5].trim() : "";
                String templateCode = cols.length > 6 ? cols[6].trim() : "";
                String platform = platformOverride != null ? platformOverride : (cols.length > 7 ? cols[7].trim() : "");

                if (!StringUtils.hasText(url) || !URL_PATTERN.matcher(url).matches()) {
                    invalid++;
                    errors.add(SourceImportDTO.ErrorItem.builder().row(row).url(url).reason("URL格式不合法").build());
                    continue;
                }
                if (!StringUtils.hasText(name)) {
                    name = url;
                }

                // Dedup check
                LambdaQueryWrapper<CollectorSource> dupWrapper = new LambdaQueryWrapper<CollectorSource>()
                        .eq(CollectorSource::getUrl, url);
                if (StringUtils.hasText(columnName)) {
                    dupWrapper.eq(CollectorSource::getColumnName, columnName);
                } else {
                    dupWrapper.isNull(CollectorSource::getColumnName);
                }
                if (sourceMapper.selectCount(dupWrapper) > 0) {
                    duplicates++;
                    continue;
                }

                TemplateType templateType = resolveTemplate(templateCode);

                int prio = defaultPriority != null ? defaultPriority : 5;
                if (StringUtils.hasText(priority)) {
                    try { prio = Integer.parseInt(priority); } catch (NumberFormatException ignored) {}
                }

                CollectorSource source = CollectorSource.builder()
                        .url(url)
                        .name(name)
                        .columnName(StringUtils.hasText(columnName) ? columnName : null)
                        .region(StringUtils.hasText(region) ? region : null)
                        .platform(StringUtils.hasText(platform) ? platform : null)
                        .priority(prio)
                        .template(templateType)
                        .status(SourceStatus.PENDING_DETECT)
                        .build();
                sourceMapper.insert(source);
                imported++;
            }
        } catch (Exception e) {
            log.error("CSV导入失败", e);
            throw new BusinessException("CSV文件解析失败: " + e.getMessage());
        }

        return result.total(total).imported(imported).duplicates(duplicates).invalid(invalid).errors(errors).build();
    }

    /** Excel 导入 — 列顺序与 CSV 相同，仅读取第一个 Sheet */
    private SourceImportDTO importFromExcel(MultipartFile file, String platformOverride, Integer defaultPriority) {
        SourceImportDTO.SourceImportDTOBuilder result = SourceImportDTO.builder();
        List<SourceImportDTO.ErrorItem> errors = new ArrayList<>();
        int total = 0, imported = 0, duplicates = 0, invalid = 0;

        try (Workbook workbook = new XSSFWorkbook(file.getInputStream())) {
            Sheet sheet = workbook.getSheetAt(0);
            int lastRow = sheet.getLastRowNum();

            for (int i = 1; i <= lastRow; i++) {
                Row row = sheet.getRow(i);
                if (row == null) continue;

                String url = getCellString(row, 0);
                String name = getCellString(row, 1);
                String columnName = getCellString(row, 2);
                String region = getCellString(row, 3);
                String priorityStr = getCellString(row, 5);
                String templateCode = getCellString(row, 6);
                String platform = platformOverride != null ? platformOverride : getCellString(row, 7);

                if (!StringUtils.hasText(url)) continue;
                total++;

                if (!URL_PATTERN.matcher(url).matches()) {
                    invalid++;
                    errors.add(SourceImportDTO.ErrorItem.builder().row(i + 1).url(url).reason("URL格式不合法").build());
                    continue;
                }
                if (!StringUtils.hasText(name)) {
                    name = url;
                }

                LambdaQueryWrapper<CollectorSource> dupWrapper = new LambdaQueryWrapper<CollectorSource>()
                        .eq(CollectorSource::getUrl, url);
                if (StringUtils.hasText(columnName)) {
                    dupWrapper.eq(CollectorSource::getColumnName, columnName);
                } else {
                    dupWrapper.isNull(CollectorSource::getColumnName);
                }
                if (sourceMapper.selectCount(dupWrapper) > 0) {
                    duplicates++;
                    continue;
                }

                TemplateType templateType = resolveTemplate(templateCode);

                int prio = defaultPriority != null ? defaultPriority : 5;
                if (StringUtils.hasText(priorityStr)) {
                    try { prio = Integer.parseInt(priorityStr); } catch (NumberFormatException ignored) {}
                }

                CollectorSource source = CollectorSource.builder()
                        .url(url)
                        .name(name)
                        .columnName(StringUtils.hasText(columnName) ? columnName : null)
                        .region(StringUtils.hasText(region) ? region : null)
                        .platform(StringUtils.hasText(platform) ? platform : null)
                        .priority(prio)
                        .template(templateType)
                        .status(SourceStatus.PENDING_DETECT)
                        .build();
                sourceMapper.insert(source);
                imported++;
            }
        } catch (Exception e) {
            log.error("Excel导入失败", e);
            throw new BusinessException("Excel文件解析失败: " + e.getMessage());
        }

        return result.total(total).imported(imported).duplicates(duplicates).invalid(invalid).errors(errors).build();
    }

    /** 读取 Excel 单元格值为字符串，数字类型转为 long 再转字符串（会丢失小数部分） */
    private String getCellString(Row row, int col) {
        Cell cell = row.getCell(col);
        if (cell == null) return "";
        return switch (cell.getCellType()) {
            case STRING -> cell.getStringCellValue().trim();
            case NUMERIC -> String.valueOf((long) cell.getNumericCellValue());
            default -> "";
        };
    }

    /** 根据 code 或 letter 匹配模板类型枚举，匹配不到时返回 null */
    private TemplateType resolveTemplate(String code) {
        if (!StringUtils.hasText(code)) return null;
        for (TemplateType t : TemplateType.values()) {
            if (t.getCode().equalsIgnoreCase(code) || t.getLetter().equalsIgnoreCase(code)) {
                return t;
            }
        }
        return null;
    }
}
