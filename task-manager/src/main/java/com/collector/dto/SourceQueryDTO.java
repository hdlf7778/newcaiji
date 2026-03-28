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

    private Integer page = 1;

    private Integer size = 20;
}
