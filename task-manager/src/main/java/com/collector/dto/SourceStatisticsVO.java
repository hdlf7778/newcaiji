package com.collector.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.Map;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class SourceStatisticsVO {

    /** status code -> count */
    private Map<String, Long> statusCounts;

    /** template code -> count */
    private Map<String, Long> templateCounts;

    /** "excellent"/"good"/"warning"/"danger" -> count */
    private Map<String, Long> healthDistribution;

    private Long total;
}
