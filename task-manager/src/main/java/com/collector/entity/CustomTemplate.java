package com.collector.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

/**
 * 自定义采集模板实体 — 对应 custom_template 表
 * <p>
 * 用户可基于系统内置模板（baseTemplate）创建自定义模板，
 * 预设默认的列表规则、详情规则、反爬策略和平台参数。
 * code 字段在业务层保证唯一性。
 * </p>
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@TableName("custom_template")
public class CustomTemplate {

    @TableId(type = IdType.AUTO)
    private Integer id;

    /** 模板显示名称 */
    private String name;

    /** 模板唯一编码（业务层校验唯一） */
    private String code;

    /** 继承的基础模板类型 */
    private String baseTemplate;

    private String description;

    /** 默认列表页采集规则（JSON 格式） */
    private String defaultListRule;

    /** 默认详情页采集规则（JSON 格式） */
    private String defaultDetailRule;

    /** 默认反爬策略配置（JSON 格式） */
    private String defaultAntiBot;

    /** 默认平台参数（JSON 格式） */
    private String defaultPlatformParams;

    /** 是否启用，创建时默认 true */
    private Boolean enabled;

    /** 使用此模板的数据源数量（冗余计数，创建时初始化为 0） */
    private Integer sourceCount;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;
}
