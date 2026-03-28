package com.collector.common;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

@DisplayName("BusinessException — custom business error")
class BusinessExceptionTest {

    @Test
    @DisplayName("message-only constructor defaults to code 400")
    void messageOnly() {
        BusinessException ex = new BusinessException("bad request");
        assertThat(ex.getMessage()).isEqualTo("bad request");
        assertThat(ex.getCode()).isEqualTo(400);
    }

    @Test
    @DisplayName("code + message constructor")
    void codeAndMessage() {
        BusinessException ex = new BusinessException(404, "not found");
        assertThat(ex.getCode()).isEqualTo(404);
        assertThat(ex.getMessage()).isEqualTo("not found");
    }

    @Test
    @DisplayName("is a RuntimeException")
    void isRuntimeException() {
        assertThatThrownBy(() -> { throw new BusinessException("test"); })
                .isInstanceOf(RuntimeException.class)
                .hasMessage("test");
    }
}
