package com.collector.service;

import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import java.util.HashMap;
import java.util.Map;

/**
 * Webhook 推送服务 — 支持钉钉/企微/通用 Webhook
 */
@Slf4j
@Service
public class WebhookService {

    private final RestTemplate restTemplate;

    @Value("${collector.alert.webhook-url:}")
    private String webhookUrl;

    @Value("${collector.alert.channel:webhook}")
    private String channel;

    public WebhookService(RestTemplate restTemplate) {
        this.restTemplate = restTemplate;
    }

    /**
     * 发送文本消息
     */
    public boolean send(String title, String content) {
        if (webhookUrl == null || webhookUrl.isBlank()) {
            log.warn("Webhook URL 未配置，跳过推送: {}", title);
            return false;
        }

        try {
            Map<String, Object> body = buildMessage(title, content);
            restTemplate.postForEntity(webhookUrl, body, String.class);
            log.info("Webhook 推送成功: {}", title);
            return true;
        } catch (Exception e) {
            log.error("Webhook 推送失败: {} - {}", title, e.getMessage());
            return false;
        }
    }

    /**
     * 发送告警消息（带级别）
     */
    public boolean sendAlert(String level, String title, String content) {
        String prefix = switch (level) {
            case "P0" -> "🚨 [P0 紧急] ";
            case "P1" -> "⚠️ [P1 严重] ";
            case "P2" -> "🔶 [P2 警告] ";
            case "P3" -> "ℹ️ [P3 关注] ";
            default -> "[" + level + "] ";
        };
        return send(prefix + title, content);
    }

    private Map<String, Object> buildMessage(String title, String content) {
        Map<String, Object> body = new HashMap<>();

        if (webhookUrl.contains("dingtalk") || webhookUrl.contains("oapi.dingtalk.com")) {
            // 钉钉格式
            body.put("msgtype", "markdown");
            Map<String, String> markdown = new HashMap<>();
            markdown.put("title", title);
            markdown.put("text", "### " + title + "\n\n" + content);
            body.put("markdown", markdown);
        } else if (webhookUrl.contains("qyapi.weixin.qq.com")) {
            // 企业微信格式
            body.put("msgtype", "markdown");
            Map<String, String> markdown = new HashMap<>();
            markdown.put("content", "### " + title + "\n\n" + content);
            body.put("markdown", markdown);
        } else {
            // 通用格式
            body.put("title", title);
            body.put("content", content);
            body.put("timestamp", System.currentTimeMillis());
        }

        return body;
    }
}
