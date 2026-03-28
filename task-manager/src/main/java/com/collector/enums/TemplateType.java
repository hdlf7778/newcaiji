package com.collector.enums;

import com.baomidou.mybatisplus.annotation.EnumValue;
import lombok.Getter;

@Getter
public enum TemplateType {
    STATIC_LIST("static_list", "A", "静态列表页", "http"),
    IFRAME_LOADER("iframe_loader", "B", "iframe加载", "browser"),
    API_JSON("api_json", "C", "API接口型", "http"),
    WECHAT_ARTICLE("wechat_article", "D", "微信公众号", "http"),
    SEARCH_DISCOVERY("search_discovery", "E", "搜索监控", "http"),
    AUTH_REQUIRED("auth_required", "F", "登录态", "browser"),
    SPA_RENDER("spa_render", "G", "SPA渲染", "browser"),
    RSS_FEED("rss_feed", "H", "RSS订阅", "http"),
    GOV_CLOUD_PLATFORM("gov_cloud_platform", "I", "政务云", "http"),
    CAPTURED_API("captured_api", "J", "抓包API", "http");

    @EnumValue
    private final String code;
    private final String letter;
    private final String label;
    private final String queueType; // http or browser

    TemplateType(String code, String letter, String label, String queueType) {
        this.code = code;
        this.letter = letter;
        this.label = label;
        this.queueType = queueType;
    }

    public boolean isHttpQueue() {
        return "http".equals(queueType);
    }
}
