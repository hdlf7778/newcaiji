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
@TableName("article_list")
public class ArticleList {

    @TableId(type = IdType.AUTO)
    private Integer id;
    private Integer sourceId;
    private String url;
    private String urlHash;          // MD5(url)，用于去重
    private String title;
    private LocalDate publishDate;
    private String author;
    private String summary;
    private Boolean hasDetail;       // 是否已采集详情页

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime fetchedAt;
}
