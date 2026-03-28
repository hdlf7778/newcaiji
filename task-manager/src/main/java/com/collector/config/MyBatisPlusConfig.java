package com.collector.config;

import com.baomidou.mybatisplus.annotation.DbType;
import com.baomidou.mybatisplus.extension.plugins.MybatisPlusInterceptor;
import com.baomidou.mybatisplus.extension.plugins.inner.DynamicTableNameInnerInterceptor;
import com.baomidou.mybatisplus.extension.plugins.inner.PaginationInnerInterceptor;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * MyBatis-Plus 配置
 * - 分页插件
 * - article_detail 动态分表路由（source_id % 16）
 */
@Configuration
public class MyBatisPlusConfig {

    /**
     * 线程局部变量，用于传递当前操作的分表索引
     * 使用方式: DetailTableContext.set(sourceId % 16); 然后执行 Mapper 操作
     */
    public static final ThreadLocal<Integer> DETAIL_TABLE_INDEX = new ThreadLocal<>();

    @Bean
    public MybatisPlusInterceptor mybatisPlusInterceptor() {
        MybatisPlusInterceptor interceptor = new MybatisPlusInterceptor();

        // article_detail 动态表名: article_detail_{0~15}
        DynamicTableNameInnerInterceptor dynamicTable = new DynamicTableNameInnerInterceptor();
        dynamicTable.setTableNameHandler((sql, tableName) -> {
            if ("article_detail".equals(tableName)) {
                Integer index = DETAIL_TABLE_INDEX.get();
                if (index != null) {
                    return "article_detail_" + index;
                }
            }
            return tableName;
        });
        interceptor.addInnerInterceptor(dynamicTable);

        // 分页
        interceptor.addInnerInterceptor(new PaginationInnerInterceptor(DbType.MYSQL));

        return interceptor;
    }
}
