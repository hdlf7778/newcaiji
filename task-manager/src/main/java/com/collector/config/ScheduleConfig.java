package com.collector.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Configuration;

@Configuration
@ConfigurationProperties(prefix = "collector.schedule")
@Data
public class ScheduleConfig {
    private String workHours = "08:00-20:00";
    private int workInterval = 7200;
    private int offInterval = 14400;
    private int manualTriggerPriority = 100;
    private int scheduledPriority = 5;
}
