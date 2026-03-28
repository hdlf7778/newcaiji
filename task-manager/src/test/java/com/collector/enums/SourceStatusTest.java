package com.collector.enums;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

@DisplayName("SourceStatus — 13 lifecycle states")
class SourceStatusTest {

    @Test
    @DisplayName("exactly 13 states")
    void count() {
        assertThat(SourceStatus.values()).hasSize(13);
    }

    @Test
    @DisplayName("detection flow states")
    void detectionStates() {
        assertThat(SourceStatus.PENDING_DETECT.getCode()).isEqualTo("pending_detect");
        assertThat(SourceStatus.DETECTING.getCode()).isEqualTo("detecting");
        assertThat(SourceStatus.DETECTED.getCode()).isEqualTo("detected");
        assertThat(SourceStatus.DETECT_FAILED.getCode()).isEqualTo("detect_failed");
    }

    @Test
    @DisplayName("trial flow states")
    void trialStates() {
        assertThat(SourceStatus.TRIAL.getCode()).isEqualTo("trial");
        assertThat(SourceStatus.TRIAL_PASSED.getCode()).isEqualTo("trial_passed");
        assertThat(SourceStatus.TRIAL_FAILED.getCode()).isEqualTo("trial_failed");
    }

    @Test
    @DisplayName("production lifecycle states")
    void productionStates() {
        assertThat(SourceStatus.APPROVED.getCode()).isEqualTo("approved");
        assertThat(SourceStatus.ACTIVE.getCode()).isEqualTo("active");
        assertThat(SourceStatus.PAUSED.getCode()).isEqualTo("paused");
        assertThat(SourceStatus.ERROR.getCode()).isEqualTo("error");
        assertThat(SourceStatus.RETIRED.getCode()).isEqualTo("retired");
    }

    @Test
    @DisplayName("labels are non-empty Chinese strings")
    void labelsNotEmpty() {
        for (SourceStatus status : SourceStatus.values()) {
            assertThat(status.getLabel()).isNotBlank();
        }
    }

    @Test
    @DisplayName("codes are unique")
    void codesUnique() {
        var codes = java.util.Arrays.stream(SourceStatus.values())
                .map(SourceStatus::getCode)
                .toList();
        assertThat(codes).doesNotHaveDuplicates();
    }
}
