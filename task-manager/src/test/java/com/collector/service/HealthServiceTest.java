package com.collector.service;

import com.collector.entity.CollectorSource;
import com.collector.entity.CollectorTask;
import com.collector.enums.SourceStatus;
import com.collector.mapper.CollectorSourceMapper;
import com.collector.mapper.CollectorTaskMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

@ExtendWith(MockitoExtension.class)
@DisplayName("HealthService — 5-dimension health scoring")
class HealthServiceTest {

    @Mock
    private CollectorSourceMapper sourceMapper;
    @Mock
    private CollectorTaskMapper taskMapper;

    private HealthService healthService;

    @BeforeEach
    void setUp() {
        healthService = new HealthService(sourceMapper, taskMapper);
    }

    private CollectorSource makeSource(Integer id, int failCount, LocalDateTime lastSuccess, LocalDateTime createdAt) {
        CollectorSource s = new CollectorSource();
        s.setId(id);
        s.setFailCount(failCount);
        s.setLastSuccessAt(lastSuccess);
        s.setCreatedAt(createdAt);
        s.setStatus(SourceStatus.ACTIVE);
        return s;
    }

    private CollectorTask makeTask(String status, Integer articlesNew, LocalDateTime completedAt) {
        CollectorTask t = new CollectorTask();
        t.setStatus(status);
        t.setArticlesNew(articlesNew);
        t.setCompletedAt(completedAt);
        t.setSourceId(1);
        return t;
    }

    @Nested
    @DisplayName("computeHealth with task list")
    class ComputeHealth {

        @Test
        @DisplayName("perfect source scores 90-100")
        void perfectSource() {
            CollectorSource source = makeSource(1, 0, LocalDateTime.now().minusHours(2), LocalDateTime.now().minusMonths(1));
            List<CollectorTask> tasks = List.of(
                    makeTask("success", 5, LocalDateTime.now().minusHours(2)),
                    makeTask("success", 3, LocalDateTime.now().minusHours(4)),
                    makeTask("success", 7, LocalDateTime.now().minusDays(1))
            );

            HealthService.HealthDetail detail = healthService.computeHealth(source, tasks);

            assertThat(detail.getHealthScore()).isBetween(90, 100);
            assertThat(detail.getLevel()).isEqualTo("excellent");
            assertThat(detail.getSuccessRateScore()).isEqualTo(40.0);
            assertThat(detail.getFailPenaltyScore()).isEqualTo(20.0);
        }

        @Test
        @DisplayName("all-failed source scores low")
        void allFailedSource() {
            CollectorSource source = makeSource(1, 5, LocalDateTime.now().minusDays(10), LocalDateTime.now().minusMonths(1));
            List<CollectorTask> tasks = List.of(
                    makeTask("failed", 0, LocalDateTime.now().minusHours(2)),
                    makeTask("failed", 0, LocalDateTime.now().minusHours(4)),
                    makeTask("timeout", 0, LocalDateTime.now().minusDays(1))
            );

            HealthService.HealthDetail detail = healthService.computeHealth(source, tasks);

            assertThat(detail.getHealthScore()).isLessThan(50);
            assertThat(detail.getLevel()).isEqualTo("danger");
            assertThat(detail.getSuccessRateScore()).isEqualTo(0.0);
        }

        @Test
        @DisplayName("empty tasks use baseline scores")
        void emptyTasks() {
            CollectorSource source = makeSource(1, 0, null, LocalDateTime.now().minusMonths(1));

            HealthService.HealthDetail detail = healthService.computeHealth(source, Collections.emptyList());

            assertThat(detail.getSuccessRateScore()).isEqualTo(20.0); // baseline for no tasks
            assertThat(detail.getContentQualityScore()).isEqualTo(10.0);
        }

        @Test
        @DisplayName("fail penalty: failCount=5 -> penalty=0")
        void failPenaltyMax() {
            CollectorSource source = makeSource(1, 5, LocalDateTime.now(), LocalDateTime.now());

            HealthService.HealthDetail detail = healthService.computeHealth(source, Collections.emptyList());

            assertThat(detail.getFailPenaltyScore()).isEqualTo(0.0);
        }

        @Test
        @DisplayName("fail penalty: failCount=0 -> full 20 points")
        void failPenaltyNone() {
            CollectorSource source = makeSource(1, 0, LocalDateTime.now(), LocalDateTime.now());

            HealthService.HealthDetail detail = healthService.computeHealth(source, Collections.emptyList());

            assertThat(detail.getFailPenaltyScore()).isEqualTo(20.0);
        }

        @Test
        @DisplayName("fail penalty: failCount=3 -> 20-12=8")
        void failPenaltyPartial() {
            CollectorSource source = makeSource(1, 3, LocalDateTime.now(), LocalDateTime.now());

            HealthService.HealthDetail detail = healthService.computeHealth(source, Collections.emptyList());

            assertThat(detail.getFailPenaltyScore()).isEqualTo(8.0);
        }
    }

    @Nested
    @DisplayName("quiet days scoring")
    class QuietDays {

        @Test
        @DisplayName("no lastSuccessAt -> 0 quiet days")
        void noLastSuccess() {
            CollectorSource source = makeSource(1, 0, null, LocalDateTime.now());

            HealthService.HealthDetail detail = healthService.computeHealth(source, Collections.emptyList());

            assertThat(detail.getQuietDays()).isEqualTo(0);
            assertThat(detail.getQuietScore()).isEqualTo(20.0);
        }

        @Test
        @DisplayName("recent success -> full quiet score")
        void recentSuccess() {
            CollectorSource source = makeSource(1, 0, LocalDateTime.now().minusHours(2), LocalDateTime.now());

            HealthService.HealthDetail detail = healthService.computeHealth(source, Collections.emptyList());

            assertThat(detail.getQuietScore()).isEqualTo(20.0);
        }

        @Test
        @DisplayName(">90 days quiet -> 0 score")
        void veryQuiet() {
            CollectorSource source = makeSource(1, 0, LocalDateTime.now().minusDays(100), LocalDateTime.now());

            HealthService.HealthDetail detail = healthService.computeHealth(source, Collections.emptyList());

            assertThat(detail.getQuietScore()).isEqualTo(0.0);
        }

        @Test
        @DisplayName("30-90 days quiet -> 5 score")
        void moderatelyQuiet() {
            CollectorSource source = makeSource(1, 0, LocalDateTime.now().minusDays(45), LocalDateTime.now());

            HealthService.HealthDetail detail = healthService.computeHealth(source, Collections.emptyList());

            assertThat(detail.getQuietScore()).isEqualTo(5.0);
        }
    }

    @Nested
    @DisplayName("rule age scoring")
    class RuleAge {

        @Test
        @DisplayName("recent creation -> full 10 points")
        void recentRule() {
            CollectorSource source = makeSource(1, 0, LocalDateTime.now(), LocalDateTime.now().minusMonths(1));

            HealthService.HealthDetail detail = healthService.computeHealth(source, Collections.emptyList());

            assertThat(detail.getRuleAgeScore()).isEqualTo(10.0);
        }

        @Test
        @DisplayName("3-6 months -> 5 points")
        void midAgeRule() {
            CollectorSource source = makeSource(1, 0, LocalDateTime.now(), LocalDateTime.now().minusMonths(4));

            HealthService.HealthDetail detail = healthService.computeHealth(source, Collections.emptyList());

            assertThat(detail.getRuleAgeScore()).isEqualTo(5.0);
        }

        @Test
        @DisplayName(">6 months -> 0 points")
        void oldRule() {
            CollectorSource source = makeSource(1, 0, LocalDateTime.now(), LocalDateTime.now().minusMonths(8));

            HealthService.HealthDetail detail = healthService.computeHealth(source, Collections.emptyList());

            assertThat(detail.getRuleAgeScore()).isEqualTo(0.0);
        }

        @Test
        @DisplayName("null createdAt -> full 10 points")
        void nullCreatedAt() {
            CollectorSource source = makeSource(1, 0, LocalDateTime.now(), null);

            HealthService.HealthDetail detail = healthService.computeHealth(source, Collections.emptyList());

            assertThat(detail.getRuleAgeScore()).isEqualTo(10.0);
        }
    }

    @Nested
    @DisplayName("content quality scoring")
    class ContentQuality {

        @Test
        @DisplayName("all tasks have articles -> 10 points")
        void fullQuality() {
            CollectorSource source = makeSource(1, 0, LocalDateTime.now(), LocalDateTime.now());
            List<CollectorTask> tasks = List.of(
                    makeTask("success", 5, LocalDateTime.now()),
                    makeTask("success", 3, LocalDateTime.now())
            );

            HealthService.HealthDetail detail = healthService.computeHealth(source, tasks);

            assertThat(detail.getContentQualityScore()).isEqualTo(10.0);
        }

        @Test
        @DisplayName("no tasks with articles -> 0 points")
        void noQuality() {
            CollectorSource source = makeSource(1, 0, LocalDateTime.now(), LocalDateTime.now());
            List<CollectorTask> tasks = List.of(
                    makeTask("success", 0, LocalDateTime.now()),
                    makeTask("failed", 0, LocalDateTime.now())
            );

            HealthService.HealthDetail detail = healthService.computeHealth(source, tasks);

            assertThat(detail.getContentQualityScore()).isEqualTo(0.0);
        }
    }

    @Nested
    @DisplayName("quiet anomaly detection")
    class QuietAnomaly {

        @Test
        @DisplayName("no quiet days -> not anomaly")
        void noQuiet() {
            CollectorSource source = makeSource(1, 0, LocalDateTime.now(), LocalDateTime.now());

            HealthService.HealthDetail detail = healthService.computeHealth(source, Collections.emptyList());

            assertThat(detail.isQuietAnomaly()).isFalse();
        }

        @Test
        @DisplayName(">30 days without baseline -> anomaly")
        void longQuietNoBaseline() {
            CollectorSource source = makeSource(1, 0, LocalDateTime.now().minusDays(35), LocalDateTime.now());

            HealthService.HealthDetail detail = healthService.computeHealth(source, Collections.emptyList());

            assertThat(detail.isQuietAnomaly()).isTrue();
        }
    }

    @Nested
    @DisplayName("score levels")
    class ScoreLevels {

        @Test
        @DisplayName("score boundaries map to correct levels")
        void scoreLevelMapping() {
            // Perfect source
            CollectorSource source = makeSource(1, 0, LocalDateTime.now(), LocalDateTime.now());
            List<CollectorTask> tasks = List.of(
                    makeTask("success", 5, LocalDateTime.now().minusHours(2)),
                    makeTask("success", 3, LocalDateTime.now().minusHours(4))
            );
            HealthService.HealthDetail detail = healthService.computeHealth(source, tasks);
            assertThat(detail.getLevel()).isIn("excellent", "good");

            // Score is clamped 0-100
            assertThat(detail.getHealthScore()).isBetween(0, 100);
        }
    }

    @Nested
    @DisplayName("avg interval calculation")
    class AvgInterval {

        @Test
        @DisplayName("< 2 success tasks -> null interval")
        void tooFewTasks() {
            CollectorSource source = makeSource(1, 0, LocalDateTime.now(), LocalDateTime.now());
            List<CollectorTask> tasks = List.of(
                    makeTask("success", 5, LocalDateTime.now())
            );

            HealthService.HealthDetail detail = healthService.computeHealth(source, tasks);

            assertThat(detail.getAvgUpdateIntervalHours()).isNull();
        }

        @Test
        @DisplayName("2+ success tasks -> calculated interval")
        void enoughTasks() {
            CollectorSource source = makeSource(1, 0, LocalDateTime.now(), LocalDateTime.now());
            List<CollectorTask> tasks = List.of(
                    makeTask("success", 5, LocalDateTime.now().minusHours(4)),
                    makeTask("success", 3, LocalDateTime.now().minusHours(2)),
                    makeTask("success", 2, LocalDateTime.now())
            );

            HealthService.HealthDetail detail = healthService.computeHealth(source, tasks);

            assertThat(detail.getAvgUpdateIntervalHours()).isNotNull();
            assertThat(detail.getAvgUpdateIntervalHours()).isGreaterThan(BigDecimal.ZERO);
        }
    }
}
