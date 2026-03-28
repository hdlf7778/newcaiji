package com.collector.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.collector.entity.CollectorSource;
import com.collector.entity.CollectorTask;
import com.collector.enums.SourceStatus;
import com.collector.mapper.CollectorSourceMapper;
import com.collector.mapper.CollectorTaskMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;

/**
 * 告警服务 — 四级告警分发
 *
 * P0 紧急: Worker全挂/Redis宕机/成功率<50%     → 电话+短信(通过Webhook模拟)
 * P1 严重: 成功率<80%/队列积压>10000            → 钉钉/企微即时消息
 * P2 警告: 单站连续失败≥5/规则失效>20个/天       → Webhook→管理后台红点
 * P3 关注: 异常静默/长期静默>30天               → 每日巡检报告
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AlertService {

    private final CollectorSourceMapper sourceMapper;
    private final CollectorTaskMapper taskMapper;
    private final StringRedisTemplate redisTemplate;
    private final WebhookService webhookService;

    /**
     * 执行一轮告警检查（可被定时任务或手动触发调用）
     */
    public void checkAlerts() {
        checkP0();
        checkP1();
        checkP2();
        // P3 在日报中处理
    }

    /**
     * P0: Worker 全挂 / 队列积压严重 / 成功率极低
     */
    private void checkP0() {
        // 检查 Worker 心跳
        Long httpPending = redisTemplate.opsForZSet().size("task:http:pending");
        Long browserPending = redisTemplate.opsForZSet().size("task:browser:pending");
        long totalPending = (httpPending != null ? httpPending : 0) + (browserPending != null ? browserPending : 0);

        if (totalPending > 20000) {
            webhookService.sendAlert("P0", "队列严重积压",
                    String.format("待处理任务: %d (HTTP: %d, Browser: %d)，可能 Worker 全部宕机",
                            totalPending, httpPending, browserPending));
        }

        // 检查今日成功率
        LocalDateTime todayStart = LocalDate.now().atStartOfDay();
        long todayTotal = taskMapper.selectCount(
                new LambdaQueryWrapper<CollectorTask>().ge(CollectorTask::getCreatedAt, todayStart));
        long todaySuccess = taskMapper.selectCount(
                new LambdaQueryWrapper<CollectorTask>()
                        .ge(CollectorTask::getCreatedAt, todayStart)
                        .eq(CollectorTask::getStatus, "success"));

        if (todayTotal > 100) {
            double rate = (double) todaySuccess / todayTotal * 100;
            if (rate < 50) {
                webhookService.sendAlert("P0", "采集成功率极低",
                        String.format("今日成功率: %.1f%% (%d/%d)，低于50%%", rate, todaySuccess, todayTotal));
            }
        }
    }

    /**
     * P1: 成功率 < 80% / 队列积压 > 10000
     */
    private void checkP1() {
        Long httpPending = redisTemplate.opsForZSet().size("task:http:pending");
        Long browserPending = redisTemplate.opsForZSet().size("task:browser:pending");
        long totalPending = (httpPending != null ? httpPending : 0) + (browserPending != null ? browserPending : 0);

        if (totalPending > 10000) {
            webhookService.sendAlert("P1", "队列积压",
                    String.format("待处理任务: %d，超过阈值 10000", totalPending));
        }

        LocalDateTime todayStart = LocalDate.now().atStartOfDay();
        long todayTotal = taskMapper.selectCount(
                new LambdaQueryWrapper<CollectorTask>().ge(CollectorTask::getCreatedAt, todayStart));
        long todaySuccess = taskMapper.selectCount(
                new LambdaQueryWrapper<CollectorTask>()
                        .ge(CollectorTask::getCreatedAt, todayStart)
                        .eq(CollectorTask::getStatus, "success"));

        if (todayTotal > 100) {
            double rate = (double) todaySuccess / todayTotal * 100;
            if (rate < 80 && rate >= 50) {
                webhookService.sendAlert("P1", "采集成功率偏低",
                        String.format("今日成功率: %.1f%% (%d/%d)，低于80%%", rate, todaySuccess, todayTotal));
            }
        }
    }

    /**
     * P2: 单站连续失败 ≥ 5 / 规则失效数 > 20
     */
    private void checkP2() {
        // 连续失败 ≥ 5 的源
        long failingSources = sourceMapper.selectCount(
                new LambdaQueryWrapper<CollectorSource>()
                        .eq(CollectorSource::getStatus, SourceStatus.ERROR)
                        .ge(CollectorSource::getFailCount, 5));

        if (failingSources > 0) {
            webhookService.sendAlert("P2", "采集源连续失败",
                    String.format("%d 个采集源连续失败 ≥ 5 次，已自动标记为异常", failingSources));
        }

        // 检测失败的源数
        long detectFailed = sourceMapper.selectCount(
                new LambdaQueryWrapper<CollectorSource>()
                        .eq(CollectorSource::getStatus, SourceStatus.DETECT_FAILED));

        if (detectFailed > 20) {
            webhookService.sendAlert("P2", "规则失效数量过多",
                    String.format("当前 %d 个采集源检测失败（规则失效），超过阈值 20", detectFailed));
        }
    }
}
