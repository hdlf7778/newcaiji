package com.collector.controller;

import com.collector.common.Result;
import com.collector.service.SourceDetectService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/sources")
@RequiredArgsConstructor
public class SourceDetectController {

    private final SourceDetectService sourceDetectService;

    /** POST /api/sources/{id}/detect - trigger full LLM detection */
    @PostMapping("/{id}/detect")
    public Result<Map<String, Object>> detect(@PathVariable Integer id) {
        return Result.ok(sourceDetectService.detectFull(id));
    }

    /** POST /api/sources/{id}/detect-template - trigger template-only detection */
    @PostMapping("/{id}/detect-template")
    public Result<Map<String, Object>> detectTemplate(@PathVariable Integer id) {
        return Result.ok(sourceDetectService.detectTemplate(id));
    }
}
