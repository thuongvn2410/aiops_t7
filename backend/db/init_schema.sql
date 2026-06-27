CREATE DATABASE IF NOT EXISTS aiops;

CREATE TABLE IF NOT EXISTS aiops.metrics (
    service_name  LowCardinality(String),
    host          LowCardinality(String),
    env           LowCardinality(String)   DEFAULT 'prod',
    timestamp     DateTime64(3)            CODEC(DoubleDelta, LZ4),
    metric_name   LowCardinality(String),
    value         Float64,
    unit          LowCardinality(String)   DEFAULT ''
)
ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(timestamp)
ORDER BY (service_name, metric_name, timestamp)
TTL timestamp + INTERVAL 30 DAY
SETTINGS index_granularity = 8192;

CREATE TABLE IF NOT EXISTS aiops.logs (
    trace_id      String,
    span_id       String                   DEFAULT '',
    service_name  LowCardinality(String),
    host          LowCardinality(String),
    timestamp     DateTime64(3)            CODEC(DoubleDelta, LZ4),
    level         LowCardinality(String),
    message       String                   CODEC(ZSTD(3)),
    logger        String                   DEFAULT ''
)
ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(timestamp)
ORDER BY (service_name, timestamp, trace_id)
TTL timestamp + INTERVAL 30 DAY
SETTINGS index_granularity = 8192;

CREATE TABLE IF NOT EXISTS aiops.traces (
    trace_id        String,
    span_id         String,
    parent_span_id  String                 DEFAULT '',
    service_name    LowCardinality(String),
    operation       String,
    start_time      DateTime64(3)          CODEC(DoubleDelta, LZ4),
    duration_ms     Float64,
    status_code     UInt8                  DEFAULT 0,
    attributes      String                 DEFAULT '' CODEC(ZSTD(3))
)
ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(start_time)
ORDER BY (service_name, trace_id, start_time)
TTL start_time + INTERVAL 30 DAY
SETTINGS index_granularity = 8192;

CREATE TABLE IF NOT EXISTS aiops.anomaly_events (
    event_id      UUID                     DEFAULT generateUUIDv4(),
    detected_at   DateTime64(3)            CODEC(DoubleDelta, LZ4),
    source_table  LowCardinality(String),
    service_name  LowCardinality(String),
    metric_name   String                   DEFAULT '',
    anomaly_score Float64,
    label         UInt8                    DEFAULT 1,
    model_name    LowCardinality(String),
    rca_causes    String                   DEFAULT '' CODEC(ZSTD(3))
)
ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(detected_at)
ORDER BY (service_name, detected_at)
TTL detected_at + INTERVAL 90 DAY
SETTINGS index_granularity = 8192;

CREATE TABLE IF NOT EXISTS aiops.alert_incidents (
    incident_id  UUID                      DEFAULT generateUUIDv4(),
    created_at   DateTime64(3)             CODEC(DoubleDelta, LZ4),
    resolved_at  Nullable(DateTime64(3))   DEFAULT NULL,
    service_name LowCardinality(String),
    severity     LowCardinality(String),
    status       UInt8                     DEFAULT 0,
    event_ids    String                    DEFAULT '' CODEC(ZSTD(3)),
    summary      String                    DEFAULT ''
)
ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(created_at)
ORDER BY (service_name, created_at)
TTL created_at + INTERVAL 180 DAY
SETTINGS index_granularity = 8192;
