package com.collector.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.collector.common.PageResult;
import com.collector.common.Result;
import com.collector.entity.ArticleList;
import com.collector.mapper.ArticleListMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.util.StringUtils;
import org.springframework.web.bind.annotation.*;

/**
 * 文章控制器 — 提供已采集文章的分页列表和详情查询
 * <p>
 * 只读接口，数据由采集任务写入，此处仅做展示查询。
 * </p>
 */
@RestController
@RequestMapping("/api/articles")
@RequiredArgsConstructor
public class ArticleController {

    private final ArticleListMapper articleListMapper;

    /** 分页查询文章列表，支持按数据源ID和标题关键词过滤 */
    @GetMapping
    public Result<PageResult<ArticleList>> list(
            @RequestParam(required = false) Integer sourceId,
            @RequestParam(required = false) String keyword,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int pageSize) {

        LambdaQueryWrapper<ArticleList> wrapper = new LambdaQueryWrapper<>();
        if (sourceId != null) {
            wrapper.eq(ArticleList::getSourceId, sourceId);
        }
        if (StringUtils.hasText(keyword)) {
            wrapper.like(ArticleList::getTitle, keyword);
        }
        wrapper.orderByDesc(ArticleList::getFetchedAt);

        IPage<ArticleList> iPage = articleListMapper.selectPage(new Page<>(page, pageSize), wrapper);
        return Result.ok(new PageResult<>(iPage.getRecords(), iPage.getTotal(), iPage.getCurrent(), iPage.getSize()));
    }

    /** 根据 ID 查询文章详情，不存在时返回 404 */
    @GetMapping("/{id}")
    public Result<ArticleList> detail(@PathVariable Integer id) {
        ArticleList article = articleListMapper.selectById(id);
        if (article == null) {
            return Result.fail(404, "文章不存在");
        }
        return Result.ok(article);
    }
}
