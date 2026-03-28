package com.collector.enums;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

import static org.assertj.core.api.Assertions.assertThat;

@DisplayName("TemplateType — 10 crawl template types with queue routing")
class TemplateTypeTest {

    @Test
    @DisplayName("exactly 10 templates registered")
    void count() {
        assertThat(TemplateType.values()).hasSize(10);
    }

    @ParameterizedTest
    @CsvSource({
            "STATIC_LIST,      static_list,        A, http",
            "IFRAME_LOADER,    iframe_loader,      B, browser",
            "API_JSON,         api_json,           C, http",
            "WECHAT_ARTICLE,   wechat_article,     D, http",
            "SEARCH_DISCOVERY, search_discovery,   E, http",
            "AUTH_REQUIRED,    auth_required,      F, browser",
            "SPA_RENDER,       spa_render,         G, browser",
            "RSS_FEED,         rss_feed,           H, http",
            "GOV_CLOUD_PLATFORM, gov_cloud_platform, I, http",
            "CAPTURED_API,     captured_api,       J, http",
    })
    @DisplayName("template {0}: code={1}, letter={2}, queue={3}")
    void templateProperties(String enumName, String code, String letter, String queueType) {
        TemplateType t = TemplateType.valueOf(enumName);
        assertThat(t.getCode()).isEqualTo(code);
        assertThat(t.getLetter()).isEqualTo(letter);
        assertThat(t.getQueueType()).isEqualTo(queueType);
    }

    @Test
    @DisplayName("HTTP queue templates")
    void httpQueueTemplates() {
        assertThat(TemplateType.STATIC_LIST.isHttpQueue()).isTrue();
        assertThat(TemplateType.API_JSON.isHttpQueue()).isTrue();
        assertThat(TemplateType.RSS_FEED.isHttpQueue()).isTrue();
        assertThat(TemplateType.GOV_CLOUD_PLATFORM.isHttpQueue()).isTrue();
        assertThat(TemplateType.WECHAT_ARTICLE.isHttpQueue()).isTrue();
        assertThat(TemplateType.CAPTURED_API.isHttpQueue()).isTrue();
    }

    @Test
    @DisplayName("browser queue templates")
    void browserQueueTemplates() {
        assertThat(TemplateType.IFRAME_LOADER.isHttpQueue()).isFalse();
        assertThat(TemplateType.AUTH_REQUIRED.isHttpQueue()).isFalse();
        assertThat(TemplateType.SPA_RENDER.isHttpQueue()).isFalse();
    }

    @Test
    @DisplayName("7 HTTP + 3 browser distribution")
    void queueDistribution() {
        long httpCount = java.util.Arrays.stream(TemplateType.values())
                .filter(TemplateType::isHttpQueue).count();
        assertThat(httpCount).isEqualTo(7);
        assertThat(TemplateType.values().length - httpCount).isEqualTo(3);
    }
}
