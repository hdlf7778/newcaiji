package com.collector.dto;

import com.collector.enums.TemplateType;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import lombok.Data;

@Data
public class SourceCreateDTO {

    @NotBlank(message = "名称不能为空")
    private String name;

    @NotBlank(message = "URL不能为空")
    @Pattern(regexp = "^https?://.+", message = "URL必须以http://或https://开头")
    private String url;

    private String columnName;

    private String sourceType;

    private TemplateType template;

    private String platform;

    private String platformParams;

    private String region;

    private Integer priority = 5;

    private Integer checkInterval;

    private String encoding;
}
