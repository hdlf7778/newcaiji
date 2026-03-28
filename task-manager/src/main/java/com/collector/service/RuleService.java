package com.collector.service;

import com.collector.entity.CollectorRule;

import java.util.Map;

public interface RuleService {

    CollectorRule getBySourceId(Integer sourceId);

    void create(CollectorRule rule);

    void update(CollectorRule rule);

    void delete(Integer id);

    Map<String, Object> testPreview(Integer sourceId);
}
