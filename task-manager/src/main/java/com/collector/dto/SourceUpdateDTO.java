package com.collector.dto;

import com.collector.enums.SourceStatus;
import lombok.Data;
import lombok.EqualsAndHashCode;

@Data
@EqualsAndHashCode(callSuper = true)
public class SourceUpdateDTO extends SourceCreateDTO {

    private SourceStatus status;
}
