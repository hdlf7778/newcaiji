package com.collector.common;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

@DisplayName("GlobalExceptionHandler — exception to Result mapping")
class GlobalExceptionHandlerTest {

    private GlobalExceptionHandler handler;

    @BeforeEach
    void setUp() {
        handler = new GlobalExceptionHandler();
    }

    @Test
    @DisplayName("BusinessException maps to fail result with code")
    void handleBusiness() {
        BusinessException ex = new BusinessException(404, "not found");
        Result<Void> result = handler.handleBusiness(ex);
        assertThat(result.isSuccess()).isFalse();
        assertThat(result.getCode()).isEqualTo(404);
        assertThat(result.getMessage()).isEqualTo("not found");
    }

    @Test
    @DisplayName("BusinessException message truncated at 200 chars")
    void handleBusinessLongMessage() {
        String longMsg = "x".repeat(500);
        BusinessException ex = new BusinessException(400, longMsg);
        Result<Void> result = handler.handleBusiness(ex);
        assertThat(result.getMessage()).hasSize(200);
    }

    @Test
    @DisplayName("generic Exception returns 500 with safe message")
    void handleGenericException() {
        Exception ex = new RuntimeException("internal details should not leak");
        Result<Void> result = handler.handleException(ex);
        assertThat(result.isSuccess()).isFalse();
        assertThat(result.getCode()).isEqualTo(500);
        assertThat(result.getMessage()).isEqualTo("服务器内部错误");
        assertThat(result.getMessage()).doesNotContain("internal details");
    }

    @Test
    @DisplayName("NullPointerException returns safe 500")
    void handleNpe() {
        Result<Void> result = handler.handleException(new NullPointerException("field is null"));
        assertThat(result.getCode()).isEqualTo(500);
        assertThat(result.getMessage()).doesNotContain("null");
    }
}
