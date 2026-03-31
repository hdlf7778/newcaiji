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

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.*;

@Slf4j
@Service
@RequiredArgsConstructor
public class SourceDiagnoseService {

    private final CollectorSourceMapper sourceMapper;
    private final CollectorRuleMapper ruleMapper;
    private final com.collector.mapper.CustomTemplateMapper customTemplateMapper;
    private final RestTemplate restTemplate;

    @Value("${collector.worker.api-url}")
    private String workerApiUrl;

    /**
     * Diagnose why a source trial failed.
     * Calls Python Worker /diagnose endpoint and enriches with DB context.
     */
    @SuppressWarnings("unchecked")
    public Map<String, Object> diagnose(Integer sourceId) {
        CollectorSource source = sourceMapper.selectById(sourceId);
        if (source == null) throw new BusinessException("采集源不存在");

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("source_id", sourceId);
        result.put("url", source.getUrl());
        result.put("current_template", source.getTemplate() != null ? source.getTemplate().getCode() : null);
        result.put("current_score", source.getTrialScore());
        result.put("status", source.getStatus().name().toLowerCase());

        // Check if rules exist
        CollectorRule rule = ruleMapper.selectOne(
            new LambdaQueryWrapper<CollectorRule>().eq(CollectorRule::getSourceId, sourceId));
        result.put("has_rules", rule != null);
        result.put("has_list_rule", rule != null && rule.getListRule() != null && !rule.getListRule().isBlank());

        // Call Python Worker /diagnose
        try {
            Map<String, Object> body = Map.of("url", source.getUrl());
            ResponseEntity<Map> resp = restTemplate.postForEntity(
                workerApiUrl + "/diagnose", body, Map.class);
            Map<String, Object> workerResult = resp.getBody() != null ? resp.getBody() : new HashMap<>();
            result.putAll(workerResult);
        } catch (Exception e) {
            log.warn("Worker diagnose failed: {}", e.getMessage());
            result.put("diagnosis", List.of("Worker 诊断服务不可用: " + e.getMessage()));
            result.put("suggested_actions", List.of("check_worker"));
        }

        return result;
    }

    /**
     * Auto-repair a failed source by executing a fix chain:
     * 1. Follow redirects → update URL
     * 2. Switch template if JS-rendered
     * 3. Regenerate rules via LLM
     * 4. Re-trial (test-list + test-detail)
     * 5. Re-score
     */
    @SuppressWarnings("unchecked")
    public Map<String, Object> autoRepair(Integer sourceId) {
        CollectorSource source = sourceMapper.selectById(sourceId);
        if (source == null) throw new BusinessException("采集源不存在");

        BigDecimal previousScore = source.getTrialScore();
        List<Map<String, Object>> repairLog = new ArrayList<>();
        int stepNum = 0;

        // Step 1: Diagnose
        stepNum++;
        Map<String, Object> diagnosis;
        try {
            diagnosis = diagnose(sourceId);
            repairLog.add(logStep(stepNum, "诊断分析", true, "完成诊断"));
        } catch (Exception e) {
            repairLog.add(logStep(stepNum, "诊断分析", false, e.getMessage()));
            return buildRepairResult(false, previousScore, BigDecimal.ZERO, repairLog, null);
        }

        // Step 2: Fix URL redirect
        stepNum++;
        String finalUrl = (String) diagnosis.get("final_url");
        Boolean redirected = Boolean.TRUE.equals(diagnosis.get("redirected"));
        if (redirected && finalUrl != null && !finalUrl.equals(source.getUrl())) {
            source.setUrl(finalUrl);
            sourceMapper.updateById(source);
            repairLog.add(logStep(stepNum, "更新URL", true, "URL已更新为: " + finalUrl));
        } else {
            repairLog.add(logStep(stepNum, "更新URL", true, "URL无需更新"));
        }

        // Step 3: Switch template if needed
        stepNum++;
        String suggestedTemplate = (String) diagnosis.get("suggested_template");
        if (suggestedTemplate != null) {
            try {
                com.collector.enums.TemplateType newTemplate = null;
                for (com.collector.enums.TemplateType t : com.collector.enums.TemplateType.values()) {
                    if (t.getCode().equals(suggestedTemplate)) {
                        newTemplate = t;
                        break;
                    }
                }
                if (newTemplate != null && (source.getTemplate() == null || !source.getTemplate().equals(newTemplate))) {
                    String oldName = source.getTemplate() != null ? source.getTemplate().getCode() : "null";
                    source.setTemplate(newTemplate);
                    sourceMapper.updateById(source);
                    repairLog.add(logStep(stepNum, "切换模板", true, oldName + " → " + newTemplate.getCode()));
                } else {
                    repairLog.add(logStep(stepNum, "切换模板", true, "模板无需切换"));
                }
            } catch (Exception e) {
                repairLog.add(logStep(stepNum, "切换模板", false, e.getMessage()));
            }
        } else {
            repairLog.add(logStep(stepNum, "切换模板", true, "模板无需切换"));
        }

        // Step 4: Regenerate rules via Worker /detect-rules
        stepNum++;
        try {
            source = sourceMapper.selectById(sourceId); // reload after updates
            Map<String, Object> detectBody = new HashMap<>();
            detectBody.put("url", source.getUrl());
            detectBody.put("template", source.getTemplate() != null ? source.getTemplate().getCode() : "static_list");
            ResponseEntity<Map> detectResp = restTemplate.postForEntity(
                workerApiUrl + "/detect-rules", detectBody, Map.class);
            Map<String, Object> detectResult = detectResp.getBody() != null ? detectResp.getBody() : new HashMap<>();

            // Save rules
            Map<String, Object> listRule = (Map<String, Object>) detectResult.get("list_rule");
            Map<String, Object> detailRule = (Map<String, Object>) detectResult.get("detail_rule");

            CollectorRule rule = ruleMapper.selectOne(
                new LambdaQueryWrapper<CollectorRule>().eq(CollectorRule::getSourceId, sourceId));
            if (rule == null) {
                rule = new CollectorRule();
                rule.setSourceId(sourceId);
            }
            if (listRule != null && !listRule.isEmpty()) {
                rule.setListRule(new com.fasterxml.jackson.databind.ObjectMapper().writeValueAsString(listRule));
            }
            if (detailRule != null && !detailRule.isEmpty()) {
                rule.setDetailRule(new com.fasterxml.jackson.databind.ObjectMapper().writeValueAsString(detailRule));
            }
            rule.setGeneratedBy("auto_repair");
            rule.setUpdatedAt(LocalDateTime.now());

            if (rule.getId() != null) {
                ruleMapper.updateById(rule);
            } else {
                rule.setCreatedAt(LocalDateTime.now());
                rule.setRuleVersion(1);
                ruleMapper.insert(rule);
            }
            repairLog.add(logStep(stepNum, "生成规则", true, "采集规则已重新生成"));
        } catch (Exception e) {
            log.warn("Rule regeneration failed: {}", e.getMessage());
            repairLog.add(logStep(stepNum, "生成规则", false, "规则生成失败: " + e.getMessage()));
        }

        // Step 5: Re-trial (test-list + test-detail + scoring)
        stepNum++;
        int checks = 0;
        int articleCount = 0;
        try {
            source = sourceMapper.selectById(sourceId); // reload
            CollectorRule rule = ruleMapper.selectOne(
                new LambdaQueryWrapper<CollectorRule>().eq(CollectorRule::getSourceId, sourceId));

            String template = source.getTemplate() != null ? source.getTemplate().getCode() : "static_list";
            String listRuleJson = rule != null && rule.getListRule() != null ? rule.getListRule() : "{}";
            String detailRuleJson = rule != null && rule.getDetailRule() != null ? rule.getDetailRule() : "{}";

            // Test list
            Map<String, Object> listBody = new HashMap<>();
            listBody.put("source_id", sourceId);
            listBody.put("url", source.getUrl());
            listBody.put("template", template);
            listBody.put("list_rule", new com.fasterxml.jackson.databind.ObjectMapper().readValue(listRuleJson, Map.class));

            ResponseEntity<Map> listResp = restTemplate.postForEntity(
                workerApiUrl + "/test-list", listBody, Map.class);
            Map<String, Object> listResult = listResp.getBody() != null ? listResp.getBody() : new HashMap<>();
            boolean listOk = Boolean.TRUE.equals(listResult.get("success"));
            List<Map<String, Object>> articles = listResult.get("articles") instanceof List
                ? (List<Map<String, Object>>) listResult.get("articles") : List.of();
            articleCount = articles.size();

            // Scoring check 1: list >= 3 articles
            if (listOk && articleCount >= 3) checks++;

            // Scoring check 2: title diversity
            List<String> titles = new ArrayList<>();
            for (Map<String, Object> a : articles) {
                if (a.get("title") != null) titles.add(a.get("title").toString());
            }
            if (titles.size() > 1 && new HashSet<>(titles).size() > 1) checks++;

            // Test detail (first valid article)
            String firstUrl = null;
            for (Map<String, Object> a : articles) {
                String u = a.get("url") != null ? a.get("url").toString() : "";
                if (u.startsWith("http")) { firstUrl = u; break; }
            }
            if (firstUrl != null) {
                try {
                    Map<String, Object> detailBody = new HashMap<>();
                    detailBody.put("source_id", sourceId);
                    detailBody.put("url", firstUrl);
                    detailBody.put("template", template);
                    detailBody.put("detail_rule", new com.fasterxml.jackson.databind.ObjectMapper().readValue(detailRuleJson, Map.class));
                    ResponseEntity<Map> detailResp = restTemplate.postForEntity(
                        workerApiUrl + "/test-detail", detailBody, Map.class);
                    Map<String, Object> detailResult = detailResp.getBody() != null ? detailResp.getBody() : new HashMap<>();
                    boolean detailOk = Boolean.TRUE.equals(detailResult.get("success"));
                    int contentLen = detailResult.get("content_length") != null
                        ? ((Number) detailResult.get("content_length")).intValue() : 0;
                    if (detailOk && contentLen > 0) checks++;
                    if (detailOk && contentLen > 100) checks++;
                    // Check 5: no garbled text
                    String preview = detailResult.get("content_preview") != null
                        ? detailResult.get("content_preview").toString() : "";
                    if (detailOk && preview.length() > 50) {
                        long badChars = preview.chars().filter(ch ->
                            !(ch >= 0x4e00 && ch <= 0x9fff)
                            && !(ch >= 0x3000 && ch <= 0x303f)
                            && !(ch >= 0xff00 && ch <= 0xffef)
                            && !(ch >= 0x20 && ch <= 0x7e)
                            && ch != '\n' && ch != '\r' && ch != '\t'
                        ).count();
                        if ((double) badChars / preview.length() < 0.05) checks++;
                    }
                } catch (Exception ignored) {}
            }

            // If first attempt got 0 articles, try alternative templates
            if (articleCount == 0) {
                repairLog.add(logStep(stepNum, "重新试采", true, "当前模板采集到 0 篇，尝试其他策略..."));

                // Try alternative templates: gov_cloud_platform → static_list → api_json
                String[] altTemplates = {"gov_cloud_platform", "static_list", "api_json"};
                for (String alt : altTemplates) {
                    if (alt.equals(template)) continue; // skip current
                    stepNum++;
                    try {
                        Map<String, Object> altBody = new HashMap<>();
                        altBody.put("source_id", sourceId);
                        altBody.put("url", source.getUrl());
                        altBody.put("template", alt);
                        altBody.put("list_rule", new HashMap<>());
                        ResponseEntity<Map> altResp = restTemplate.postForEntity(
                            workerApiUrl + "/test-list", altBody, Map.class);
                        Map<String, Object> altResult = altResp.getBody() != null ? altResp.getBody() : new HashMap<>();
                        boolean altOk = Boolean.TRUE.equals(altResult.get("success"));
                        List<?> altArticles = altResult.get("articles") instanceof List ? (List<?>) altResult.get("articles") : List.of();

                        if (altOk && altArticles.size() >= 2) {
                            articleCount = altArticles.size();
                            listOk = true;
                            articles = (List<Map<String, Object>>) altArticles;
                            template = alt;

                            // Update source template
                            for (com.collector.enums.TemplateType t : com.collector.enums.TemplateType.values()) {
                                if (t.getCode().equals(alt)) {
                                    source.setTemplate(t);
                                    sourceMapper.updateById(source);
                                    break;
                                }
                            }
                            repairLog.add(logStep(stepNum, "尝试模板 " + alt, true,
                                "成功！采集到 " + articleCount + " 篇文章"));

                            // Re-score with the successful template
                            checks = 0;
                            if (articleCount >= 3) checks++;
                            titles.clear();
                            for (Map<String, Object> a : articles) {
                                if (a.get("title") != null) titles.add(a.get("title").toString());
                            }
                            if (titles.size() > 1 && new HashSet<>(titles).size() > 1) checks++;

                            // Test detail with first valid URL
                            firstUrl = null;
                            for (Map<String, Object> a : articles) {
                                String u = a.get("url") != null ? a.get("url").toString() : "";
                                if (u.startsWith("http")) { firstUrl = u; break; }
                            }
                            if (firstUrl != null) {
                                try {
                                    Map<String, Object> db = new HashMap<>();
                                    db.put("source_id", sourceId);
                                    db.put("url", firstUrl);
                                    db.put("template", template);
                                    db.put("detail_rule", new HashMap<>());
                                    ResponseEntity<Map> dr = restTemplate.postForEntity(
                                        workerApiUrl + "/test-detail", db, Map.class);
                                    Map<String, Object> dRes = dr.getBody() != null ? dr.getBody() : new HashMap<>();
                                    boolean dOk = Boolean.TRUE.equals(dRes.get("success"));
                                    int cLen = dRes.get("content_length") != null
                                        ? ((Number) dRes.get("content_length")).intValue() : 0;
                                    if (dOk && cLen > 0) checks++;
                                    if (dOk && cLen > 100) checks++;
                                    String pv = dRes.get("content_preview") != null ? dRes.get("content_preview").toString() : "";
                                    if (dOk && pv.length() > 50) {
                                        long bad = pv.chars().filter(ch ->
                                            !(ch >= 0x4e00 && ch <= 0x9fff) && !(ch >= 0x3000 && ch <= 0x303f)
                                            && !(ch >= 0xff00 && ch <= 0xffef) && !(ch >= 0x20 && ch <= 0x7e)
                                            && ch != '\n' && ch != '\r' && ch != '\t').count();
                                        if ((double) bad / pv.length() < 0.05) checks++;
                                    }
                                } catch (Exception ignored) {}
                            }
                            break;
                        } else {
                            repairLog.add(logStep(stepNum, "尝试模板 " + alt, false,
                                "采集到 " + altArticles.size() + " 篇，不足"));
                        }
                    } catch (Exception e) {
                        repairLog.add(logStep(stepNum, "尝试模板 " + alt, false, e.getMessage()));
                    }
                }

                // Step 7: LLM deep analysis (only if all templates failed)
                if (articleCount == 0) {
                    stepNum++;
                    try {
                        Map<String, Object> analyzeBody = new HashMap<>();
                        analyzeBody.put("url", source.getUrl());
                        analyzeBody.put("current_template", template);
                        ResponseEntity<Map> analyzeResp = restTemplate.postForEntity(
                            workerApiUrl + "/analyze-deep", analyzeBody, Map.class);
                        Map<String, Object> analyzeResult = analyzeResp.getBody() != null ? analyzeResp.getBody() : new HashMap<>();
                        boolean analyzeOk = Boolean.TRUE.equals(analyzeResult.get("success"));
                        String analysis = analyzeResult.get("analysis") != null ? analyzeResult.get("analysis").toString() : "";

                        if (analyzeOk) {
                            repairLog.add(logStep(stepNum, "LLM\u6df1\u5ea6\u5206\u6790", true, analysis));

                            // Apply LLM suggested rules
                            String sugTemplate = analyzeResult.get("suggested_template") != null
                                ? analyzeResult.get("suggested_template").toString() : null;
                            Map<String, Object> sugListRule = analyzeResult.get("suggested_list_rule") instanceof Map
                                ? (Map<String, Object>) analyzeResult.get("suggested_list_rule") : new HashMap<>();
                            Map<String, Object> sugDetailRule = analyzeResult.get("suggested_detail_rule") instanceof Map
                                ? (Map<String, Object>) analyzeResult.get("suggested_detail_rule") : new HashMap<>();

                            // Update template if suggested
                            if (sugTemplate != null) {
                                for (com.collector.enums.TemplateType t : com.collector.enums.TemplateType.values()) {
                                    if (t.getCode().equals(sugTemplate)) {
                                        source.setTemplate(t);
                                        template = sugTemplate;
                                        break;
                                    }
                                }
                            }

                            // Save LLM-generated rules
                            CollectorRule llmRule = ruleMapper.selectOne(
                                new LambdaQueryWrapper<CollectorRule>().eq(CollectorRule::getSourceId, sourceId));
                            if (llmRule == null) {
                                llmRule = new CollectorRule();
                                llmRule.setSourceId(sourceId);
                                llmRule.setCreatedAt(LocalDateTime.now());
                                llmRule.setRuleVersion(1);
                            }
                            com.fasterxml.jackson.databind.ObjectMapper om = new com.fasterxml.jackson.databind.ObjectMapper();
                            if (!sugListRule.isEmpty()) llmRule.setListRule(om.writeValueAsString(sugListRule));
                            if (!sugDetailRule.isEmpty()) llmRule.setDetailRule(om.writeValueAsString(sugDetailRule));
                            llmRule.setGeneratedBy("llm_deep_analysis");
                            llmRule.setUpdatedAt(LocalDateTime.now());
                            if (llmRule.getId() != null) ruleMapper.updateById(llmRule); else ruleMapper.insert(llmRule);

                            // Test with LLM-suggested approach
                            stepNum++;
                            Map<String, Object> llmTestBody = new HashMap<>();
                            llmTestBody.put("source_id", sourceId);
                            llmTestBody.put("url", source.getUrl());
                            llmTestBody.put("template", template);
                            llmTestBody.put("list_rule", sugListRule);
                            ResponseEntity<Map> llmTestResp = restTemplate.postForEntity(
                                workerApiUrl + "/test-list", llmTestBody, Map.class);
                            Map<String, Object> llmTestResult = llmTestResp.getBody() != null ? llmTestResp.getBody() : new HashMap<>();
                            boolean llmTestOk = Boolean.TRUE.equals(llmTestResult.get("success"));
                            List<?> llmArticles = llmTestResult.get("articles") instanceof List ? (List<?>) llmTestResult.get("articles") : List.of();

                            if (llmTestOk && llmArticles.size() >= 2) {
                                articleCount = llmArticles.size();
                                articles = (List<Map<String, Object>>) llmArticles;
                                sourceMapper.updateById(source);
                                repairLog.add(logStep(stepNum, "LLM\u65b9\u6848\u8bd5\u91c7", true,
                                    "\u6210\u529f\uff01\u91c7\u96c6\u5230 " + articleCount + " \u7bc7\u6587\u7ae0"));

                                // Re-score
                                checks = 0;
                                if (articleCount >= 3) checks++;
                                titles.clear();
                                for (Map<String, Object> a : articles) {
                                    if (a.get("title") != null) titles.add(a.get("title").toString());
                                }
                                if (titles.size() > 1 && new HashSet<>(titles).size() > 1) checks++;
                                firstUrl = null;
                                for (Map<String, Object> a : articles) {
                                    String u = a.get("url") != null ? a.get("url").toString() : "";
                                    if (u.startsWith("http")) { firstUrl = u; break; }
                                }
                                if (firstUrl != null) {
                                    try {
                                        Map<String, Object> db = new HashMap<>();
                                        db.put("source_id", sourceId);
                                        db.put("url", firstUrl);
                                        db.put("template", template);
                                        db.put("detail_rule", sugDetailRule);
                                        ResponseEntity<Map> dr = restTemplate.postForEntity(
                                            workerApiUrl + "/test-detail", db, Map.class);
                                        Map<String, Object> dRes = dr.getBody() != null ? dr.getBody() : new HashMap<>();
                                        boolean dOk = Boolean.TRUE.equals(dRes.get("success"));
                                        int cLen = dRes.get("content_length") != null
                                            ? ((Number) dRes.get("content_length")).intValue() : 0;
                                        if (dOk && cLen > 0) checks++;
                                        if (dOk && cLen > 100) checks++;
                                        String pv = dRes.get("content_preview") != null ? dRes.get("content_preview").toString() : "";
                                        if (dOk && pv.length() > 50) {
                                            long bad = pv.chars().filter(ch ->
                                                !(ch >= 0x4e00 && ch <= 0x9fff) && !(ch >= 0x3000 && ch <= 0x303f)
                                                && !(ch >= 0xff00 && ch <= 0xffef) && !(ch >= 0x20 && ch <= 0x7e)
                                                && ch != '\n' && ch != '\r' && ch != '\t').count();
                                            if ((double) bad / pv.length() < 0.05) checks++;
                                        }
                                    } catch (Exception ignored) {}
                                }

                                // Auto-save as custom template if successful
                                stepNum++;
                                String tplName = analyzeResult.get("template_name") != null
                                    ? analyzeResult.get("template_name").toString() : "LLM\u53d1\u73b0-" + source.getName();
                                String tplDesc = analyzeResult.get("template_description") != null
                                    ? analyzeResult.get("template_description").toString() : analysis;
                                try {
                                    // Check if similar template already exists by name
                                    LambdaQueryWrapper<com.collector.entity.CustomTemplate> tplQuery = new LambdaQueryWrapper<>();
                                    tplQuery.eq(com.collector.entity.CustomTemplate::getName, tplName);
                                    if (customTemplateMapper.selectCount(tplQuery) == 0) {
                                        com.collector.entity.CustomTemplate newTpl = com.collector.entity.CustomTemplate.builder()
                                            .name(tplName)
                                            .code("llm_" + sourceId + "_" + System.currentTimeMillis() % 10000)
                                            .baseTemplate(template)
                                            .description(tplDesc)
                                            .defaultListRule(om.writeValueAsString(sugListRule))
                                            .defaultDetailRule(om.writeValueAsString(sugDetailRule))
                                            .enabled(true)
                                            .sourceCount(1)
                                            .createdAt(LocalDateTime.now())
                                            .updatedAt(LocalDateTime.now())
                                            .build();
                                        customTemplateMapper.insert(newTpl);
                                        repairLog.add(logStep(stepNum, "\u4fdd\u5b58\u65b0\u6a21\u677f", true,
                                            "\u5df2\u4fdd\u5b58\u4e3a\u81ea\u5b9a\u4e49\u6a21\u677f: " + tplName + " (ID: " + newTpl.getId() + ")"));
                                    } else {
                                        repairLog.add(logStep(stepNum, "\u4fdd\u5b58\u65b0\u6a21\u677f", true, "\u540c\u540d\u6a21\u677f\u5df2\u5b58\u5728\uff0c\u8df3\u8fc7\u4fdd\u5b58"));
                                    }
                                } catch (Exception e) {
                                    repairLog.add(logStep(stepNum, "\u4fdd\u5b58\u65b0\u6a21\u677f", false, e.getMessage()));
                                }
                            } else {
                                repairLog.add(logStep(stepNum, "LLM\u65b9\u6848\u8bd5\u91c7", false,
                                    "\u91c7\u96c6\u5230 " + llmArticles.size() + " \u7bc7\uff0c\u4e0d\u8db3"));
                            }
                        } else {
                            repairLog.add(logStep(stepNum, "LLM\u6df1\u5ea6\u5206\u6790", false,
                                analysis.isEmpty() ? "LLM\u672a\u80fd\u53d1\u73b0\u6570\u636e\u52a0\u8f7d\u673a\u5236" : analysis));
                        }
                    } catch (Exception e) {
                        repairLog.add(logStep(stepNum, "LLM\u6df1\u5ea6\u5206\u6790", false,
                            "\u5206\u6790\u5931\u8d25: " + (e.getMessage() != null ? e.getMessage().substring(0, Math.min(100, e.getMessage().length())) : "unknown")));
                    }
                }
            }

            double score = Math.round(checks / 5.0 * 100) / 100.0;
            source = sourceMapper.selectById(sourceId); // reload
            source.setTrialScore(BigDecimal.valueOf(score));
            source.setTrialAt(LocalDateTime.now());
            source.setStatus(score >= 0.4 ? SourceStatus.TRIAL_PASSED : SourceStatus.TRIAL_FAILED);
            sourceMapper.updateById(source);

            repairLog.add(logStep(++stepNum, "评分结果", score >= 0.4,
                "最终采集 " + articleCount + " 篇文章，评分 " + score
                + (score >= 0.4 ? "（通过）" : "（未通过，可能需要浏览器渲染）")));

            return buildRepairResult(score >= 0.4, previousScore, BigDecimal.valueOf(score), repairLog, diagnosis);
        } catch (Exception e) {
            log.warn("Re-trial failed: {}", e.getMessage());
            repairLog.add(logStep(stepNum, "重新试采", false, "试采失败: " + e.getMessage()));
            return buildRepairResult(false, previousScore, BigDecimal.ZERO, repairLog, diagnosis);
        }
    }

    /**
     * Manual-assist repair: user provides analysis hint, LLM generates rules, auto test + score.
     */
    @SuppressWarnings("unchecked")
    public Map<String, Object> manualAssistRepair(Integer sourceId, String hint) {
        CollectorSource source = sourceMapper.selectById(sourceId);
        if (source == null) throw new BusinessException("采集源不存在");

        BigDecimal previousScore = source.getTrialScore();
        List<Map<String, Object>> repairLog = new ArrayList<>();
        int stepNum = 0;

        // Step 1: Call Worker /manual-assist with user hint
        stepNum++;
        Map<String, Object> assistResult;
        try {
            CollectorRule existingRule = ruleMapper.selectOne(
                new LambdaQueryWrapper<CollectorRule>().eq(CollectorRule::getSourceId, sourceId));

            Map<String, Object> body = new HashMap<>();
            body.put("url", source.getUrl());
            body.put("hint", hint);
            body.put("current_template", source.getTemplate() != null ? source.getTemplate().getCode() : "");
            body.put("current_list_rule", existingRule != null && existingRule.getListRule() != null
                ? parseJson(existingRule.getListRule()) : new HashMap<>());
            body.put("current_detail_rule", existingRule != null && existingRule.getDetailRule() != null
                ? parseJson(existingRule.getDetailRule()) : new HashMap<>());

            ResponseEntity<Map> resp = restTemplate.postForEntity(
                workerApiUrl + "/manual-assist", body, Map.class);
            assistResult = resp.getBody() != null ? resp.getBody() : new HashMap<>();

            boolean ok = Boolean.TRUE.equals(assistResult.get("success"));
            String analysis = assistResult.get("analysis") != null ? assistResult.get("analysis").toString() : "";
            repairLog.add(logStep(stepNum, "LLM分析用户线索", ok, analysis));
            if (!ok) {
                return buildRepairResult(false, previousScore, previousScore, repairLog, null);
            }
        } catch (Exception e) {
            repairLog.add(logStep(stepNum, "LLM分析用户线索", false, "调用失败: " + e.getMessage()));
            return buildRepairResult(false, previousScore, previousScore, repairLog, null);
        }

        // Step 2: Apply suggested template
        stepNum++;
        String sugTemplate = assistResult.get("suggested_template") != null
            ? assistResult.get("suggested_template").toString() : null;
        String template = source.getTemplate() != null ? source.getTemplate().getCode() : "static_list";
        if (sugTemplate != null) {
            for (com.collector.enums.TemplateType t : com.collector.enums.TemplateType.values()) {
                if (t.getCode().equals(sugTemplate)) {
                    if (!t.equals(source.getTemplate())) {
                        source.setTemplate(t);
                        sourceMapper.updateById(source);
                        repairLog.add(logStep(stepNum, "切换模板", true, template + " → " + sugTemplate));
                    } else {
                        repairLog.add(logStep(stepNum, "切换模板", true, "模板不变: " + sugTemplate));
                    }
                    template = sugTemplate;
                    break;
                }
            }
        } else {
            repairLog.add(logStep(stepNum, "切换模板", true, "LLM未建议切换模板"));
        }

        // Step 3: Save LLM-generated rules
        stepNum++;
        Map<String, Object> sugListRule = assistResult.get("suggested_list_rule") instanceof Map
            ? (Map<String, Object>) assistResult.get("suggested_list_rule") : new HashMap<>();
        Map<String, Object> sugDetailRule = assistResult.get("suggested_detail_rule") instanceof Map
            ? (Map<String, Object>) assistResult.get("suggested_detail_rule") : new HashMap<>();
        try {
            CollectorRule rule = ruleMapper.selectOne(
                new LambdaQueryWrapper<CollectorRule>().eq(CollectorRule::getSourceId, sourceId));
            if (rule == null) {
                rule = new CollectorRule();
                rule.setSourceId(sourceId);
                rule.setCreatedAt(LocalDateTime.now());
                rule.setRuleVersion(1);
            }
            com.fasterxml.jackson.databind.ObjectMapper om = new com.fasterxml.jackson.databind.ObjectMapper();
            if (!sugListRule.isEmpty()) rule.setListRule(om.writeValueAsString(sugListRule));
            if (!sugDetailRule.isEmpty()) rule.setDetailRule(om.writeValueAsString(sugDetailRule));
            rule.setGeneratedBy("manual_assist_llm");
            rule.setUpdatedAt(LocalDateTime.now());
            if (rule.getId() != null) ruleMapper.updateById(rule); else ruleMapper.insert(rule);
            repairLog.add(logStep(stepNum, "保存规则", true, "已保存LLM根据用户线索生成的规则"));
        } catch (Exception e) {
            repairLog.add(logStep(stepNum, "保存规则", false, e.getMessage()));
        }

        // Step 4: Test list + detail + score
        stepNum++;
        int checks = 0;
        int articleCount = 0;
        try {
            Map<String, Object> listBody = new HashMap<>();
            listBody.put("source_id", sourceId);
            listBody.put("url", source.getUrl());
            listBody.put("template", template);
            listBody.put("list_rule", sugListRule);
            ResponseEntity<Map> listResp = restTemplate.postForEntity(
                workerApiUrl + "/test-list", listBody, Map.class);
            Map<String, Object> listResult = listResp.getBody() != null ? listResp.getBody() : new HashMap<>();
            boolean listOk = Boolean.TRUE.equals(listResult.get("success"));
            List<Map<String, Object>> articles = listResult.get("articles") instanceof List
                ? (List<Map<String, Object>>) listResult.get("articles") : List.of();
            articleCount = articles.size();

            if (listOk && articleCount >= 3) checks++;
            List<String> titles = new ArrayList<>();
            for (Map<String, Object> a : articles) {
                if (a.get("title") != null) titles.add(a.get("title").toString());
            }
            if (titles.size() > 1 && new HashSet<>(titles).size() > 1) checks++;

            String firstUrl = null;
            for (Map<String, Object> a : articles) {
                String u = a.get("url") != null ? a.get("url").toString() : "";
                if (u.startsWith("http")) { firstUrl = u; break; }
            }
            if (firstUrl != null) {
                try {
                    Map<String, Object> detailBody = new HashMap<>();
                    detailBody.put("source_id", sourceId);
                    detailBody.put("url", firstUrl);
                    detailBody.put("template", template);
                    detailBody.put("detail_rule", sugDetailRule);
                    ResponseEntity<Map> detailResp = restTemplate.postForEntity(
                        workerApiUrl + "/test-detail", detailBody, Map.class);
                    Map<String, Object> detailResult = detailResp.getBody() != null ? detailResp.getBody() : new HashMap<>();
                    boolean detailOk = Boolean.TRUE.equals(detailResult.get("success"));
                    int contentLen = detailResult.get("content_length") != null
                        ? ((Number) detailResult.get("content_length")).intValue() : 0;
                    if (detailOk && contentLen > 0) checks++;
                    if (detailOk && contentLen > 100) checks++;
                    String preview = detailResult.get("content_preview") != null
                        ? detailResult.get("content_preview").toString() : "";
                    if (detailOk && preview.length() > 50) {
                        long badChars = preview.chars().filter(ch ->
                            !(ch >= 0x4e00 && ch <= 0x9fff) && !(ch >= 0x3000 && ch <= 0x303f)
                            && !(ch >= 0xff00 && ch <= 0xffef) && !(ch >= 0x20 && ch <= 0x7e)
                            && ch != '\n' && ch != '\r' && ch != '\t').count();
                        if ((double) badChars / preview.length() < 0.05) checks++;
                    }
                } catch (Exception ignored) {}
            }

            double score = Math.round(checks / 5.0 * 100) / 100.0;
            source = sourceMapper.selectById(sourceId);
            source.setTrialScore(BigDecimal.valueOf(score));
            source.setTrialAt(LocalDateTime.now());
            source.setStatus(score >= 0.4 ? SourceStatus.TRIAL_PASSED : SourceStatus.TRIAL_FAILED);
            sourceMapper.updateById(source);

            repairLog.add(logStep(stepNum, "试采验证", articleCount > 0,
                "采集到 " + articleCount + " 篇文章，评分 " + score
                + (score >= 0.4 ? "（通过）" : "（未通过）")));

            return buildRepairResult(score >= 0.4, previousScore, BigDecimal.valueOf(score), repairLog, null);
        } catch (Exception e) {
            repairLog.add(logStep(stepNum, "试采验证", false, "试采失败: " + e.getMessage()));
            return buildRepairResult(false, previousScore, previousScore, repairLog, null);
        }
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> parseJson(String json) {
        try {
            return new com.fasterxml.jackson.databind.ObjectMapper().readValue(json, Map.class);
        } catch (Exception e) {
            return new HashMap<>();
        }
    }

    private Map<String, Object> logStep(int step, String name, boolean success, String message) {
        Map<String, Object> log = new LinkedHashMap<>();
        log.put("step", step);
        log.put("name", name);
        log.put("success", success);
        log.put("message", message);
        return log;
    }

    private Map<String, Object> buildRepairResult(boolean success, BigDecimal previousScore,
                                                   BigDecimal newScore, List<Map<String, Object>> repairLog,
                                                   Map<String, Object> diagnosis) {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("success", success);
        result.put("previousScore", previousScore != null ? previousScore.doubleValue() : 0);
        result.put("newScore", newScore != null ? newScore.doubleValue() : 0);
        result.put("repairLog", repairLog);
        if (diagnosis != null) {
            result.put("diagnosis", diagnosis.get("diagnosis"));
            result.put("suggested_actions", diagnosis.get("suggested_actions"));
        }
        return result;
    }
}
