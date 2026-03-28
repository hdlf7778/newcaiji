package com.collector.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.collector.common.BusinessException;
import com.collector.entity.CollectorRule;
import com.collector.entity.CollectorSource;
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
public class RuleServiceImpl implements RuleService {

    private final CollectorRuleMapper ruleMapper;
    private final CollectorSourceMapper sourceMapper;
    private final RestTemplate restTemplate;

    @Value("${collector.worker.api-url}")
    private String workerApiUrl;

    @Override
    public CollectorRule getBySourceId(Integer sourceId) {
        return ruleMapper.selectOne(
                new LambdaQueryWrapper<CollectorRule>()
                        .eq(CollectorRule::getSourceId, sourceId)
                        .orderByDesc(CollectorRule::getCreatedAt)
                        .last("LIMIT 1"));
    }

    @Override
    public void create(CollectorRule rule) {
        ruleMapper.insert(rule);
    }

    @Override
    public void update(CollectorRule rule) {
        CollectorRule existing = ruleMapper.selectById(rule.getId());
        if (existing == null) {
            throw new BusinessException(404, "规则不存在: id=" + rule.getId());
        }

        // Save current rule content to previous_rule_json before updating
        String previousJson = buildPreviousRuleJson(existing);
        rule.setPreviousRuleJson(previousJson);

        // Increment rule version
        int nextVersion = existing.getRuleVersion() != null ? existing.getRuleVersion() + 1 : 1;
        rule.setRuleVersion(nextVersion);

        ruleMapper.updateById(rule);
    }

    @Override
    public void delete(Integer id) {
        CollectorRule rule = ruleMapper.selectById(id);
        if (rule == null) {
            throw new BusinessException(404, "规则不存在: id=" + id);
        }
        ruleMapper.deleteById(id);
    }

    @Override
    @SuppressWarnings("unchecked")
    public Map<String, Object> testPreview(Integer sourceId) {
        CollectorSource source = sourceMapper.selectById(sourceId);
        if (source == null) {
            throw new BusinessException(404, "数据源不存在: id=" + sourceId);
        }

        String url = workerApiUrl + "/detect-rules";
        Map<String, String> requestBody = new HashMap<>();
        requestBody.put("url", source.getUrl());

        try {
            ResponseEntity<Map> response = restTemplate.postForEntity(url, requestBody, Map.class);
            return response.getBody() != null ? response.getBody() : new HashMap<>();
        } catch (Exception e) {
            log.error("调用 Python Worker /detect-rules 失败 sourceId={}", sourceId, e);
            throw new BusinessException("规则预览失败: " + e.getMessage());
        }
    }

    // ----------------------------------------------------------------- Helpers

    private String buildPreviousRuleJson(CollectorRule rule) {
        return String.format(
                "{\"list_rule\":%s,\"detail_rule\":%s,\"rule_version\":%s}",
                rule.getListRule() != null ? rule.getListRule() : "null",
                rule.getDetailRule() != null ? rule.getDetailRule() : "null",
                rule.getRuleVersion() != null ? rule.getRuleVersion().toString() : "null"
        );
    }
}
