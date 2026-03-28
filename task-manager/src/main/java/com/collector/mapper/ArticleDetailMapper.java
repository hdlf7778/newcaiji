package com.collector.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.collector.entity.ArticleDetail;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.util.List;

/**
 * 文章详情 Mapper
 *
 * 动态表名通过 MyBatisPlusConfig.DETAIL_TABLE_INDEX 控制。
 * 使用前必须设置: MyBatisPlusConfig.DETAIL_TABLE_INDEX.set(sourceId % 16);
 * 使用后必须清除: MyBatisPlusConfig.DETAIL_TABLE_INDEX.remove();
 */
@Mapper
public interface ArticleDetailMapper extends BaseMapper<ArticleDetail> {

    /**
     * 按 source_id 查询最近文章（需先设置 DETAIL_TABLE_INDEX）
     */
    @Select("SELECT * FROM article_detail_${tableIndex} WHERE source_id = #{sourceId} ORDER BY fetched_at DESC LIMIT #{limit}")
    List<ArticleDetail> selectRecentBySourceId(@Param("tableIndex") int tableIndex,
                                                @Param("sourceId") int sourceId,
                                                @Param("limit") int limit);
}
