package com.collector.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.collector.common.BusinessException;
import com.collector.entity.CollectorRule;
import com.collector.entity.CollectorSource;
import com.collector.enums.SourceStatus;
import com.collector.mapper.CollectorRuleMapper;
import com.collector.mapper.CollectorSourceMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import java.util.HashMap;
import java.util.Map;

@Slf4j
@Service
@RequiredArgsConstructor
public class SourceDetectService {

    private final CollectorSourceMapper sourceMapper;
    private final CollectorRuleMapper ruleMapper;
    private final RestTemplate restTemplate;

    @Value("${collector.worker.api-url}")
    private String workerApiUrl;

    /**
     * Trigger full LLM detection: calls Python POST /detect-full,
     * saves the generated rule to collector_rule, updates source status.
     */
    @SuppressWarnings("unchecked")
    public Map<String, Object> detectFull(Integer sourceId) {
        CollectorSource source = getSourceOrThrow(sourceId);

        // Update status to detecting
        source.setStatus(SourceStatus.DETECTING);
        sourceMapper.updateById(source);

        String apiUrl = workerApiUrl + "/detect-full";
        Map<String, String> requestBody = new HashMap<>();
        requestBody.put("url", source.getUrl());

        try {
            ResponseEntity<Map> response = restTemplate.postForEntity(apiUrl, requestBody, Map.class);
            Map<String, Object> result = response.getBody() != null ? response.getBody() : new HashMap<>();

            // Save generated rule
            saveDetectedRule(sourceId, result);

            // Update source status to detected
            source.setStatus(SourceStatus.DETECTED);
            sourceMapper.updateById(source);

            log.info("LLM 全量检测成功 sourceId={}", sourceId);
            return result;

        } catch (Exception e) {
            log.error("LLM 全量检测失败 sourceId={}", sourceId, e);
            // Update source status to detect_failed
            source.setStatus(SourceStatus.DETECT_FAILED);
            sourceMapper.updateById(source);
            throw new BusinessException("LLM 检测失败: " + e.getMessage());
        }
    }

    /**
     * Trigger template-only detection: calls Python POST /detect-template,
     * returns template type info only.
     */
    @SuppressWarnings("unchecked")
    public Map<String, Object> detectTemplate(Integer sourceId) {
        CollectorSource source = getSourceOrThrow(sourceId);

        String apiUrl = workerApiUrl + "/detect-template";
        Map<String, String> requestBody = new HashMap<>();
        requestBody.put("url", source.getUrl());

        try {
            ResponseEntity<Map> response = restTemplate.postForEntity(apiUrl, requestBody, Map.class);
            Map<String, Object> result = response.getBody() != null ? response.getBody() : new HashMap<>();
            log.info("模板检测成功 sourceId={} result={}", sourceId, result);
            return result;
        } catch (Exception e) {
            log.error("模板检测失败 sourceId={}", sourceId, e);
            throw new BusinessException("模板检测失败: " + e.getMessage());
        }
    }

    // ----------------------------------------------------------------- Helpers

    private CollectorSource getSourceOrThrow(Integer id) {
        CollectorSource source = sourceMapper.selectById(id);
        if (source == null) {
            throw new BusinessException(404, "数据源不存在: id=" + id);
        }
        return source;
    }

    private void saveDetectedRule(Integer sourceId, Map<String, Object> detectResult) {
        try {
            // Extract rule fields from Python response
            Object listRuleObj = detectResult.get("list_rule");
            Object detailRuleObj = detectResult.get("detail_rule");
            Object templateObj = detectResult.get("template");

            String listRuleJson = listRuleObj != null ? toJsonString(listRuleObj) : null;
            String detailRuleJson = detailRuleObj != null ? toJsonString(detailRuleObj) : null;
            String generatedBy = "llm";

            // Check if rule already exists for this source
            CollectorRule existing = ruleMapper.selectOne(
                    new LambdaQueryWrapper<CollectorRule>()
                            .eq(CollectorRule::getSourceId, sourceId)
                            .last("LIMIT 1"));

            if (existing != null) {
                // Save current as previous before updating
                String previousJson = String.format(
                        "{\"list_rule\":%s,\"detail_rule\":%s,\"rule_version\":%s}",
                        existing.getListRule() != null ? existing.getListRule() : "null",
                        existing.getDetailRule() != null ? existing.getDetailRule() : "null",
                        existing.getRuleVersion() != null ? existing.getRuleVersion().toString() : "null"
                );
                existing.setPreviousRuleJson(previousJson);
                existing.setListRule(listRuleJson);
                existing.setDetailRule(detailRuleJson);
                existing.setGeneratedBy(generatedBy);
                int nextVersion = existing.getRuleVersion() != null ? existing.getRuleVersion() + 1 : 1;
                existing.setRuleVersion(nextVersion);
                ruleMapper.updateById(existing);
            } else {
                CollectorRule rule = CollectorRule.builder()
                        .sourceId(sourceId)
                        .listRule(listRuleJson)
                        .detailRule(detailRuleJson)
                        .generatedBy(generatedBy)
                        .ruleVersion(1)
                        .build();
                ruleMapper.insert(rule);
            }
        } catch (Exception e) {
            log.error("保存检测规则失败 sourceId={}", sourceId, e);
        }
    }

    @SuppressWarnings("unchecked")
    private String toJsonString(Object obj) {
        if (obj instanceof String) {
            return (String) obj;
        }
        if (obj instanceof Map) {
            Map<String, Object> map = (Map<String, Object>) obj;
            StringBuilder sb = new StringBuilder("{");
            boolean first = true;
            for (Map.Entry<String, Object> entry : map.entrySet()) {
                if (!first) sb.append(",");
                sb.append("\"").append(entry.getKey()).append("\":");
                Object val = entry.getValue();
                if (val instanceof String) {
                    sb.append("\"").append(val).append("\"");
                } else if (val == null) {
                    sb.append("null");
                } else {
                    sb.append(val);
                }
                first = false;
            }
            sb.append("}");
            return sb.toString();
        }
        return obj.toString();
    }
}
