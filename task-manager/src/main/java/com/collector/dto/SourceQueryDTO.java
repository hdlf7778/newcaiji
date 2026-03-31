package com.collector.dto;

import com.collector.enums.SourceStatus;
import com.collector.enums.TemplateType;
import lombok.Data;

@Data
public class SourceQueryDTO {

    private SourceStatus status;

    private TemplateType template;

    private String platform;

    private String region;

    /** Searches name / url / columnName */
    private String keyword;

    private Integer healthScoreMin;

    private Integer healthScoreMax;

    /** 试采评分范围: high(>=0.8), medium(0.6-0.8), low(<0.6), none(未试采) */
    private String scoreRange;

    private Integer page = 1;

    private Integer size = 20;
}
