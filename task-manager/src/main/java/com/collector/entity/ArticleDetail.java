package com.collector.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDate;
import java.time.LocalDateTime;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@TableName("article_detail")  // 动态表名由 MyBatisPlusConfig 拦截替换为 article_detail_{0~15}
public class ArticleDetail {

    @TableId(type = IdType.AUTO)
    private Integer id;
    private Integer articleId;       // 关联 article_list.id
    private Integer sourceId;
    private String title;
    private String url;
    private String content;          // 正文纯文本 (MEDIUMTEXT)
    private String contentHtml;      // 正文原始HTML (MEDIUMTEXT)
    private String publishTime;      // 原始发布时间文本
    private LocalDate publishDate;   // 标准化发布日期
    private String author;
    private String sourceName;       // 来源名称（冗余字段）
    private Integer attachmentCount;
    private String attachments;      // 附件列表 JSON

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime fetchedAt;
}
