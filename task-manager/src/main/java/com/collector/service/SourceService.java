package com.collector.service;

import com.collector.common.PageResult;
import com.collector.dto.*;
import com.collector.entity.CollectorSource;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;
import java.util.Map;

public interface SourceService {

    // ---------- CRUD ----------

    PageResult<CollectorSource> list(SourceQueryDTO query);

    SourceDetailVO detail(Integer id);

    Integer create(SourceCreateDTO dto);

    void update(Integer id, SourceUpdateDTO dto);

    void delete(Integer id);

    // ---------- Import ----------

    SourceImportDTO importFromFile(MultipartFile file, Integer defaultPriority);

    SourceImportDTO importPlatform(String platform, MultipartFile file);

    // ---------- Status management ----------

    void approve(Integer id, String operator);

    void reject(Integer id);

    void batchApprove(List<Integer> ids, String operator);

    void pause(Integer id);

    void resume(Integer id);

    void reset(Integer id);

    void retire(Integer id);

    // ---------- Statistics ----------

    SourceStatisticsVO statistics();

    Map<String, Long> statsByStatus();
}
