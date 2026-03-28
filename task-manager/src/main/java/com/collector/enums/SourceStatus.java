package com.collector.enums;

import com.baomidou.mybatisplus.annotation.EnumValue;
import lombok.Getter;

@Getter
public enum SourceStatus {
    PENDING_DETECT("pending_detect", "待检测"),
    DETECTING("detecting", "检测中"),
    DETECTED("detected", "检测成功"),
    DETECT_FAILED("detect_failed", "检测失败"),
    TRIAL("trial", "试采中"),
    TRIAL_PASSED("trial_passed", "试采通过"),
    TRIAL_FAILED("trial_failed", "试采失败"),
    PENDING_REVIEW("pending_review", "待人工审核"),
    APPROVED("approved", "审批通过"),
    ACTIVE("active", "生产运行"),
    PAUSED("paused", "暂停"),
    ERROR("error", "异常"),
    RETIRED("retired", "退役");

    @EnumValue
    private final String code;
    private final String label;

    SourceStatus(String code, String label) {
        this.code = code;
        this.label = label;
    }
}
