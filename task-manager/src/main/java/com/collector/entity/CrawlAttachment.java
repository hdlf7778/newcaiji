package com.collector.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@TableName("crawl_attachments")
public class CrawlAttachment {

    @TableId(type = IdType.AUTO)
    private Integer id;
    private Integer articleId;
    private Integer sourceId;
    // detail_table_index 是 GENERATED ALWAYS 列，不需要在 Entity 中映射写入
    private String fileName;
    private String fileUrl;
    private String fileType;         // pdf/doc/docx/xls/xlsx
    private Integer fileSize;
    private String parsedText;       // MEDIUMTEXT
    private String parsedTables;     // JSON
    private String localPath;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;
}
