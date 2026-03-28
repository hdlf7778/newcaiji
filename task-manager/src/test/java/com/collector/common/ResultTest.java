package com.collector.common;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

@DisplayName("Result — API response wrapper")
class ResultTest {

    @Test
    @DisplayName("ok() with data returns success")
    void okWithData() {
        Result<String> r = Result.ok("hello");
        assertThat(r.isSuccess()).isTrue();
        assertThat(r.getData()).isEqualTo("hello");
        assertThat(r.getCode()).isEqualTo(200);
        assertThat(r.getMessage()).isNull();
    }

    @Test
    @DisplayName("ok() without data returns success with null data")
    void okNoData() {
        Result<Void> r = Result.ok();
        assertThat(r.isSuccess()).isTrue();
        assertThat(r.getData()).isNull();
        assertThat(r.getCode()).isEqualTo(200);
    }

    @Test
    @DisplayName("fail(message) returns 400 with message")
    void failMessage() {
        Result<Void> r = Result.fail("something went wrong");
        assertThat(r.isSuccess()).isFalse();
        assertThat(r.getCode()).isEqualTo(400);
        assertThat(r.getMessage()).isEqualTo("something went wrong");
        assertThat(r.getData()).isNull();
    }

    @Test
    @DisplayName("fail(code, message) returns custom code")
    void failCodeMessage() {
        Result<Void> r = Result.fail(404, "not found");
        assertThat(r.isSuccess()).isFalse();
        assertThat(r.getCode()).isEqualTo(404);
        assertThat(r.getMessage()).isEqualTo("not found");
    }

    @Test
    @DisplayName("fail(500) for server errors")
    void failServerError() {
        Result<Void> r = Result.fail(500, "internal error");
        assertThat(r.getCode()).isEqualTo(500);
    }

    @Test
    @DisplayName("fail(429) for rate limiting")
    void failRateLimit() {
        Result<Void> r = Result.fail(429, "too many requests");
        assertThat(r.getCode()).isEqualTo(429);
    }
}
