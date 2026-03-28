package com.collector.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.ArrayList;
import java.util.List;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class SourceImportDTO {

    private int total;
    private int imported;
    private int duplicates;
    private int invalid;
    private int autoDetectQueued;
    private int directTrialQueued;

    @Builder.Default
    private List<ErrorItem> errors = new ArrayList<>();

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class ErrorItem {
        private int row;
        private String url;
        private String reason;
    }
}
