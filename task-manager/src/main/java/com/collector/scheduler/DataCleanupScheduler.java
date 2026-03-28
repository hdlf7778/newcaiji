package com.collector.scheduler;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.collector.entity.CollectorLog;
import com.collector.entity.CrawlPageSnapshot;
import com.collector.mapper.CollectorLogMapper;
import com.collector.mapper.CrawlPageSnapshotMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;

@Slf4j
@Component
@RequiredArgsConstructor
public class DataCleanupScheduler {

    private final CollectorLogMapper collectorLogMapper;
    private final CrawlPageSnapshotMapper crawlPageSnapshotMapper;

    /**
     * Clean up old collector_log and crawl_page_snapshots records every day at 04:00 AM.
     * Deletes records older than 30 days.
     */
    @Scheduled(cron = "0 0 4 * * *")
    public void cleanupOldData() {
        log.info("Starting data cleanup (retention: 30 days)...");

        LocalDateTime cutoff = LocalDateTime.now().minusDays(30);

        // DELETE FROM collector_log WHERE created_at < cutoff
        int logsDeleted = collectorLogMapper.delete(
                new LambdaQueryWrapper<CollectorLog>()
                        .lt(CollectorLog::getCreatedAt, cutoff));

        log.info("Deleted {} collector_log records older than 30 days.", logsDeleted);

        // DELETE FROM crawl_page_snapshots WHERE snapshot_at < cutoff
        int snapshotsDeleted = crawlPageSnapshotMapper.delete(
                new LambdaQueryWrapper<CrawlPageSnapshot>()
                        .lt(CrawlPageSnapshot::getSnapshotAt, cutoff));

        log.info("Deleted {} crawl_page_snapshots records older than 30 days.", snapshotsDeleted);

        log.info("Data cleanup complete. Logs: {}, Snapshots: {}.", logsDeleted, snapshotsDeleted);
    }
}
