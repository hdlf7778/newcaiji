package com.collector.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.collector.common.BusinessException;
import com.collector.common.Result;
import com.collector.entity.CustomTemplate;
import com.collector.mapper.CustomTemplateMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 自定义模板控制器 — 管理用户自定义的采集模板
 * <p>
 * 模板基于 baseTemplate 扩展，包含默认的列表规则、详情规则和反爬配置。
 * code 字段全局唯一，创建时校验。
 * </p>
 */
@RestController
@RequestMapping("/api/custom-templates")
@RequiredArgsConstructor
public class CustomTemplateController {

    private final CustomTemplateMapper mapper;

    /** 查询所有自定义模板（按创建时间倒序，不分页） */
    @GetMapping
    public Result<List<CustomTemplate>> list() {
        List<CustomTemplate> list = mapper.selectList(
                new LambdaQueryWrapper<CustomTemplate>().orderByDesc(CustomTemplate::getCreatedAt));
        return Result.ok(list);
    }

    @GetMapping("/{id}")
    public Result<CustomTemplate> detail(@PathVariable Integer id) {
        CustomTemplate t = mapper.selectById(id);
        if (t == null) return Result.fail(404, "自定义模板不存在");
        return Result.ok(t);
    }

    /** 创建自定义模板 — 校验 name/code/baseTemplate 非空，且 code 全局唯一 */
    @PostMapping
    public Result<CustomTemplate> create(@RequestBody CustomTemplate template) {
        if (template.getName() == null || template.getName().isBlank())
            throw new BusinessException("模板名称不能为空");
        if (template.getCode() == null || template.getCode().isBlank())
            throw new BusinessException("模板代码不能为空");
        if (template.getBaseTemplate() == null || template.getBaseTemplate().isBlank())
            throw new BusinessException("基础模板不能为空");

        Long exists = mapper.selectCount(
                new LambdaQueryWrapper<CustomTemplate>().eq(CustomTemplate::getCode, template.getCode()));
        if (exists > 0) throw new BusinessException("模板代码已存在: " + template.getCode());

        template.setEnabled(true);
        template.setSourceCount(0);
        mapper.insert(template);
        return Result.ok(template);
    }

    /**
     * 更新自定义模板
     * <p>
     * 注意：更新时未校验 code 唯一性，可能导致与其他模板 code 冲突。
     * </p>
     */
    @PutMapping("/{id}")
    public Result<Void> update(@PathVariable Integer id, @RequestBody CustomTemplate template) {
        if (mapper.selectById(id) == null) throw new BusinessException(404, "自定义模板不存在");
        template.setId(id);
        mapper.updateById(template);
        return Result.ok();
    }

    /** 删除自定义模板 — 未检查是否有数据源正在使用该模板 */
    @DeleteMapping("/{id}")
    public Result<Void> delete(@PathVariable Integer id) {
        if (mapper.selectById(id) == null) throw new BusinessException(404, "自定义模板不存在");
        mapper.deleteById(id);
        return Result.ok();
    }
}
