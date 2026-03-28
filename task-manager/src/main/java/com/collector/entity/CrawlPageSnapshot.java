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
@TableName("crawl_page_snapshots")
public class CrawlPageSnapshot {

    @TableId(type = IdType.AUTO)
    private Integer id;
    private Integer sourceId;
    private String pageHash;
    private String keywordsFound;    // JSON
    private Boolean contentChanged;
    private LocalDateTime snapshotAt;
}
