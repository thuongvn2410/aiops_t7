# PROJECT OVERVIEW — AIOps Anomaly Detection

> Tài liệu được tạo tự động bởi audit script. Ngày: 2026-06-27

---

## Mục lục

1. [Tổng quan project](#1-tổng-quan-project)
2. [Cấu trúc thư mục](#2-cấu-trúc-thư-mục)
3. [ClickHouse Schema](#3-clickhouse-schema)
4. [Backend](#4-backend)
5. [Frontend](#5-frontend)
6. [Luồng dữ liệu end-to-end](#6-luồng-dữ-liệu-end-to-end)
7. [Checklist Audit](#7-checklist-audit)
8. [Hướng dẫn chạy](#8-hướng-dẫn-chạy)
9. [Vấn đề còn lại](#9-vấn-đề-còn-lại)

---

## 1. Tổng quan project

### Mục tiêu

AIOps Anomaly Detection là hệ thống giám sát vận hành realtime cho microservices. Hệ thống thu thập metrics (CPU, latency, error rate, request rate…), tự động phát hiện anomaly bằng machine learning (IsolationForest), và đẩy cảnh báo tức thì đến dashboard qua WebSocket. Khi phát hiện anomaly, một LLM (GPT-4o-mini) sinh ra đoạn giải thích ngắn gọn bằng tiếng Việt để kỹ sư vận hành nắm tình hình nhanh.

### Tech Stack

| Layer | Công nghệ |
|---|---|
| Database | ClickHouse 24.3 (columnar, OLAP) |
| Backend | FastAPI + Uvicorn (Python 3.11+) |
| ML | scikit-learn IsolationForest, pandas, numpy, joblib |
| Scheduler | APScheduler (AsyncIOScheduler) |
| LLM | OpenAI GPT-4o-mini (AsyncOpenAI) |
| WebSocket | FastAPI native WebSocket |
| Frontend | React + TypeScript + Vite |
| State | Zustand |
| Chart | Recharts |
| Container | Docker Compose |

### Kiến trúc tổng thể (ASCII Diagram)

```
┌─────────────────────────────────────────────────────────────────────┐
│                          DOCKER NETWORK                             │
│                                                                     │
│  ┌──────────────┐     HTTP/9000     ┌─────────────────────────────┐ │
│  │  ClickHouse  │◄──────────────────│         BACKEND              │ │
│  │  (port 8123) │                   │  ┌──────────────────────┐   │ │
│  │              │   init_schema.sql │  │  FastAPI app         │   │ │
│  │  5 tables:   │◄──────────────────│  │  /api/metrics        │   │ │
│  │  - metrics   │                   │  │  /api/alerts         │   │ │
│  │  - logs      │                   │  │  /api/health         │   │ │
│  │  - traces    │                   │  │  /api/model/retrain  │   │ │
│  │  - anomaly_  │                   │  │  /ws (WebSocket)     │   │ │
│  │    events    │                   │  └──────────────────────┘   │ │
│  │  - alert_    │                   │  ┌──────────────────────┐   │ │
│  │    incidents │                   │  │  APScheduler (5s)    │   │ │
│  └──────────────┘                   │  │  poll → ML detect    │   │ │
│                                     │  │  → LLM narrative     │   │ │
│                                     │  │  → write DB          │   │ │
│                                     │  │  → dedup → WS push   │   │ │
│                                     │  └──────────────────────┘   │ │
│                                     │  ┌──────────────────────┐   │ │
│                                     │  │  IsolationForest     │   │ │
│                                     │  │  model_store/*.pkl   │   │ │
│                                     │  └──────────────────────┘   │ │
│                                     └─────────────────────────────┘ │
│                                               │ WebSocket /ws        │
│  ┌──────────────────────────────────────────┐ │                      │
│  │         FRONTEND (React + Vite)          │◄┘                      │
│  │  port 3000                               │                        │
│  │  ┌─────────┐ ┌────────────┐ ┌─────────┐ │                        │
│  │  │ TopBar  │ │MetricTimel.│ │AlertFeed│ │                        │
│  │  ├─────────┤ ├────────────┤ ├─────────┤ │                        │
│  │  │ Sidebar │ │ServiceGrid │ │IncCard  │ │                        │
│  │  └─────────┘ └────────────┘ └─────────┘ │                        │
│  │  Zustand store ← useWebSocket hook       │                        │
│  └──────────────────────────────────────────┘                        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Cấu trúc thư mục

```
aiops-anomaly-detection/
├── docker-compose.yml          # Orchestration: clickhouse + backend + frontend
├── .env.example                # Template biến môi trường
├── .env                        # Biến môi trường thực (không commit)
│
├── db/
│   └── init_schema.sql         # DDL tạo 5 bảng ClickHouse khi container khởi động
│
├── backend/
│   ├── Dockerfile              # Build image Python backend
│   ├── requirements.txt        # Phụ thuộc Python
│   ├── config.py               # Đọc env vars, export constants
│   ├── main.py                 # FastAPI app, lifespan, CORS, router, WS endpoint
│   │
│   ├── db/
│   │   ├── client.py           # clickhouse-connect client (singleton via lru_cache)
│   │   └── queries.py          # Toàn bộ SQL query functions
│   │
│   ├── models/
│   │   ├── detector.py         # Detector class, load_or_train_detector()
│   │   ├── trainer.py          # train_from_clickhouse(), save_model()
│   │   └── features.py         # Feature engineering: rolling mean/std, rate-of-change
│   │
│   ├── services/
│   │   ├── scheduler.py        # PollingService: APScheduler poll mỗi POLL_INTERVAL_SEC
│   │   ├── anomaly_writer.py   # Tạo anomaly payload, ghi vào ClickHouse
│   │   ├── alert_dedup.py      # Dedup incident 5 phút per service
│   │   └── rca_narrator.py     # LLM GPT-4o-mini sinh narrative tiếng Việt
│   │
│   ├── routers/
│   │   ├── metrics.py          # GET /api/metrics/timeline, /services, /metric-names
│   │   ├── alerts.py           # GET /api/alerts/recent, /incidents
│   │   └── health.py           # GET /api/health
│   │
│   ├── ws/
│   │   └── manager.py          # ConnectionManager: connect/disconnect/broadcast/heartbeat
│   │
│   └── model_store/            # Lưu isolation_forest.pkl + manifest.json (tạo runtime)
│
└── frontend/
    ├── index.html              # Trang gốc, import fonts Google (Inter + JetBrains Mono)
    ├── package.json
    ├── vite.config.ts
    │
    └── src/
        ├── main.tsx            # React entry point
        ├── App.tsx             # Root component, layout, health polling
        │
        ├── api/
        │   ├── http.ts         # Axios instance
        │   └── websocket.ts    # WS_URL const, TypeScript interfaces
        │
        ├── store/
        │   └── anomalyStore.ts # Zustand store: alerts[], lastCritical, dismissedCriticalId
        │
        ├── hooks/
        │   ├── useWebSocket.ts # Auto-connect/reconnect WS, dispatch to Zustand
        │   └── useMetrics.ts   # useServices, useMetricTimeline, useMetricNames
        │
        ├── styles/
        │   └── theme.css       # CSS variables, layout classes, dark theme
        │
        └── components/
            ├── layout/
            │   ├── TopBar.tsx      # WS status dot, digital clock, model info
            │   └── Sidebar.tsx     # Navigation sidebar
            ├── monitor/
            │   ├── MetricTimeline.tsx  # Recharts ComposedChart, sliding window 200pts
            │   ├── ServiceGrid.tsx     # Lưới service cards
            │   └── AnomalyOverlay.tsx  # Highlight anomaly points trên chart
            ├── alerts/
            │   ├── AlertBanner.tsx     # Banner critical-only, auto-hide 30s
            │   ├── AlertFeed.tsx       # Danh sách events với filter
            │   └── IncidentCard.tsx    # Chi tiết event, narrative, rca_causes badges
            └── shared/
                ├── StatusBadge.tsx     # Badge màu theo severity
                └── Sparkline.tsx       # Mini chart
```

---

## 3. ClickHouse Schema

File: `db/init_schema.sql`

Tất cả 5 bảng đều dùng engine **MergeTree**, partition theo ngày, có TTL tự xóa dữ liệu cũ. Các cột có cardinality thấp (service_name, host, env…) được khai báo `LowCardinality(String)` để nén hiệu quả. Timestamp dùng `CODEC(DoubleDelta, LZ4)` — tối ưu cho chuỗi số tăng đều. Text dài dùng `CODEC(ZSTD(3))`.

### Bảng `metrics`

Lưu các điểm đo metric theo thời gian từ mọi service.

```sql
ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(timestamp)
ORDER BY (service_name, metric_name, timestamp)
TTL toDateTime(timestamp) + INTERVAL 30 DAY
```

| Cột | Kiểu | Ghi chú |
|---|---|---|
| service_name | LowCardinality(String) | Tên service |
| host | LowCardinality(String) | Host chạy service |
| env | LowCardinality(String) | Default 'prod' |
| timestamp | DateTime64(3) CODEC(DoubleDelta, LZ4) | Millisecond precision |
| metric_name | LowCardinality(String) | cpu_usage, latency_ms… |
| value | Float64 | Giá trị đo |
| unit | LowCardinality(String) | ms, %, req/s… |

### Bảng `logs`

Lưu structured logs từ các service.

```sql
ORDER BY (service_name, timestamp, trace_id)
TTL toDateTime(timestamp) + INTERVAL 30 DAY
```

Trường `message` dùng `CODEC(ZSTD(3))` vì text tự do có thể dài.

### Bảng `traces`

Lưu distributed traces (span model tương tự OpenTelemetry).

```sql
ORDER BY (service_name, trace_id, start_time)
TTL toDateTime(start_time) + INTERVAL 30 DAY
```

Trường `attributes` JSON dùng `CODEC(ZSTD(3))`.

### Bảng `anomaly_events`

Kết quả phát hiện anomaly từ ML model.

```sql
ORDER BY (service_name, detected_at)
TTL toDateTime(detected_at) + INTERVAL 90 DAY
```

| Cột quan trọng | Kiểu | Ghi chú |
|---|---|---|
| event_id | UUID DEFAULT generateUUIDv4() | Auto-generated UUID |
| anomaly_score | Float64 | 0.0–1.0 |
| rca_causes | String CODEC(ZSTD(3)) | JSON array |
| narrative | String CODEC(ZSTD(3)) | Giải thích LLM tiếng Việt |

### Bảng `alert_incidents`

Nhóm nhiều anomaly events thành một incident (dedup 5 phút per service).

```sql
ORDER BY (service_name, created_at)
TTL toDateTime(created_at) + INTERVAL 180 DAY
```

| Cột quan trọng | Kiểu | Ghi chú |
|---|---|---|
| incident_id | UUID DEFAULT generateUUIDv4() | Auto-generated |
| resolved_at | Nullable(DateTime64(3)) | NULL khi còn mở |
| severity | LowCardinality(String) | critical/warning/info |
| status | UInt8 | 0=open, 1=resolved |
| event_ids | String | CSV các event_id thuộc incident |

---

## 4. Backend

### 4.1 Config (`backend/config.py`)

Đọc toàn bộ cấu hình từ environment variables qua `python-dotenv`. Các hằng số chính:

| Biến | Default | Ý nghĩa |
|---|---|---|
| CLICKHOUSE_HOST | localhost | Host DB |
| CLICKHOUSE_PORT | 9000 | Port (native protocol) |
| CLICKHOUSE_DB | aiops | Database name |
| POLL_INTERVAL_SEC | 5 | Tần suất poll metrics |
| LOOKBACK_SEC | 60 | Cửa sổ thời gian lấy data |
| ANOMALY_THRESHOLD | 0.6 | Ngưỡng anomaly score |
| MODEL_STORE | backend/model_store/ | Nơi lưu pkl và manifest |

> **Lưu ý:** docker-compose truyền `CLICKHOUSE_PORT=8123` (HTTP port), override port 9000 default trong config. clickhouse-connect hỗ trợ cả hai.

### 4.2 DB Layer (`backend/db/`)

**`client.py`** — Sử dụng `clickhouse-connect` (thư viện HTTP-based chính thức của ClickHouse). Client được cache bằng `@lru_cache(maxsize=1)` — tức là chỉ tạo một kết nối duy nhất trong suốt vòng đời ứng dụng (connection pool reuse). Hàm `clickhouse_status()` kiểm tra TCP socket trước khi query để tránh exception chậm.

**`queries.py`** — Tập trung 100% câu SQL tại đây, không có inline SQL ở nơi khác. Các hàm trả về string SQL với tham số parameterized:
- `q_recent_metrics(lookback_sec)` — lấy metrics cho scheduler
- `q_training_metrics(lookback_minutes)` — lấy data train model
- `q_timeline(service_name, metric_name, minutes)` — dữ liệu cho chart
- `q_services()` — danh sách service trong 24h
- `q_recent_alerts(status)` — JOIN anomaly_events với alert_incidents
- `q_incidents(severity)` — danh sách incidents
- `q_open_incident_for_service()` — kiểm tra incident 5 phút gần nhất

### 4.3 ML Model (`backend/models/`)

**Feature Engineering (`features.py`):**
- Rolling mean 12 điểm (`rolling_mean_12`)
- Rolling std 12 điểm (`rolling_std_12`)
- Rate of change (`rate_of_change` = diff giá trị liên tiếp)

**Trainer (`trainer.py` — `train_from_clickhouse`):**
```python
model = IsolationForest(contamination=0.05, n_estimators=100, random_state=42)
```
- Nếu có ít hơn 100 rows: **không crash**, trả về `(None, 0.6, rows_used)` — fallback threshold
- Threshold tự động tính tại percentile 95 của scores training data
- Lưu pkl bằng `joblib.dump()` vào `model_store/isolation_forest.pkl`
- Ghi `manifest.json` với `trained_at`, `rows_used`, `threshold`

**Detector (`detector.py` — class `Detector`):**
- Nếu model được load: dùng `decision_function()` + sigmoid để chuẩn hóa score 0–1
- Nếu không có model (fallback): tính z-score từ rolling mean/std, có logic đặc biệt cho từng metric:
  - `error_rate`: score tỉ lệ với value/0.35
  - `cpu_usage`: threshold cứng 65%, max 90%
  - `latency_ms`: threshold 220ms, cộng thêm rate-of-change
  - `request_rate`: dựa vào rate-of-change
- `load_or_train_detector()`: kiểm tra pkl + manifest tồn tại → load, không retrain; nếu không → train từ ClickHouse; nếu ClickHouse lỗi → fallback detector

### 4.4 Scheduler (`backend/services/scheduler.py`)

`PollingService` dùng `AsyncIOScheduler` của APScheduler, chạy `poll_once()` mỗi `POLL_INTERVAL_SEC` giây (default 5s).

**Luồng `poll_once()`:**
1. Query ClickHouse lấy metrics `LOOKBACK_SEC` giây gần nhất
2. Build features (rolling mean/std, rate-of-change)
3. `detector.predict()` → DataFrame với `anomaly_score`, `is_anomaly`
4. Với mỗi row `is_anomaly == True`:
   a. Tạo `anomaly_payload` (event dict)
   b. Gọi `generate_rca_narrative()` (async, LLM) → gán `event["narrative"]`
   c. `write_anomaly()` → INSERT vào `anomaly_events`
   d. `dedup_process()` → tạo/cập nhật `alert_incidents`
   e. `ws_manager.broadcast()` → push JSON đến tất cả WebSocket client

Scheduler được khởi động trong FastAPI `lifespan` (startup hook) và shutdown gracefully khi app tắt.

### 4.5 WebSocket Manager (`backend/ws/manager.py`)

```python
class ConnectionManager:
    active: list[WebSocket]
```

- `connect(ws)`: accept và thêm vào danh sách
- `disconnect(ws)`: xóa khỏi danh sách
- `broadcast(message)`: gửi JSON đến tất cả client; nếu gửi lỗi → tự động remove client stale
- `heartbeat_loop(stop_event)`: vòng lặp async gửi `{"type": "heartbeat", "data": {"sent_at": ...}}` mỗi **10 giây** (dùng `asyncio.wait_for(stop_event.wait(), timeout=10)`)

Module-level singleton: `ws_manager = ConnectionManager()` được import chung bởi `main.py` và `health.py`.

### 4.6 LLM Narrator (`backend/services/rca_narrator.py`)

```python
async def generate_rca_narrative(service_name, metric_name, anomaly_score,
                                  rca_causes, metric_value, baseline_value) -> str
```

- Kiểm tra `OPENAI_API_KEY` ngay đầu hàm — nếu không có, trả `""` ngay
- Dùng `AsyncOpenAI` (singleton `_client`)
- Model: `gpt-4o-mini`, `temperature=0.3`, `max_tokens=150`
- Prompt tiếng Việt: "Bạn là chuyên gia AIOps. Giải thích ngắn gọn (2-3 câu, tiếng Việt)…"
- Bọc trong `try/except`: mọi lỗi (network, API quota, timeout…) đều log warning và trả `""` — **không bao giờ crash scheduler**

### 4.7 Alert Dedup (`backend/services/alert_dedup.py`)

**Severity mapping:**
```
anomaly_score >= 0.85 → "critical"
anomaly_score >= 0.70 → "warning"
else                  → "info"
```

**Logic dedup:**
- Tìm incident đang mở (`status=0`) của cùng `service_name` trong **5 phút** gần nhất
- Nếu tìm thấy: thêm `event_id` vào `event_ids` (CSV), upgrade severity nếu cần, cập nhật summary
- Nếu không: tạo incident mới

### 4.8 REST API

Tất cả routes đều có error handling trả về list rỗng hoặc HTTP 503 thay vì crash.

| Method | Path | Mô tả |
|---|---|---|
| GET | `/api/metrics/timeline` | Chuỗi thời gian metric, params: service_name, metric_name, minutes (1-1440) |
| GET | `/api/metrics/services` | Danh sách service trong 24h |
| GET | `/api/metrics/metric-names` | Danh sách metric names (optional filter by service) |
| GET | `/api/alerts/recent` | Anomaly events JOIN incidents, params: limit, status |
| GET | `/api/alerts/incidents` | Danh sách incidents, params: limit, severity |
| POST | `/api/model/retrain` | Retrain IsolationForest từ dữ liệu mới, cập nhật detector đang chạy |
| GET | `/api/health` | Status: clickhouse, model_loaded, model_name, threshold, ws_clients |
| WS | `/ws` | WebSocket endpoint, hỗ trợ nhiều client đồng thời |

**CORS:** `allow_origins=["*"]`, `allow_methods=["*"]`, `allow_headers=["*"]` — phù hợp cho dev/internal.

### 4.9 FastAPI Lifespan (`backend/main.py`)

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    app.state.detector = load_or_train_detector()
    app.state.stop_event = asyncio.Event()
    app.state.heartbeat_task = asyncio.create_task(ws_manager.heartbeat_loop(...))
    app.state.poller = PollingService(...); app.state.poller.start()
    yield
    # Shutdown
    app.state.stop_event.set()
    await app.state.poller.shutdown()
    await app.state.heartbeat_task
```

---

## 5. Frontend

### 5.1 Theme (`frontend/src/styles/theme.css`)

Định nghĩa CSS variables theo dark theme (GitHub-inspired):

```css
--bg-base: #0D1117          /* Nền toàn trang */
--bg-surface: #161B22       /* Card, panel, topbar */
--bg-elevated: #21262D      /* Input, button, tooltip */
--border: #30363D
--text-primary: #E6EDF3
--text-secondary: #8B949E
--accent-red: #F85149       /* Critical alerts */
--accent-green: #3FB950     /* OK status */
--accent-yellow: #D29922    /* Warning */
--accent-blue: #388BFD      /* Charts, links */
--accent-purple: #BC8CFF    /* Service chips, mono elements */
--font-mono: 'JetBrains Mono', 'Fira Code', monospace
--font-sans: 'Inter', system-ui, sans-serif
```

Fonts được import trong `index.html` từ Google Fonts: `Inter` (400/500/600/650) + `JetBrains Mono` (400/500).

Có responsive breakpoint tại 980px: sidebar chuyển thành horizontal nav, service grid từ 4 cột → 2 cột.

### 5.2 Zustand Store (`frontend/src/store/anomalyStore.ts`)

```typescript
interface AnomalyState {
  alerts: AnomalyEvent[]          // Tối đa 100 events, mới nhất đứng đầu
  lastCritical?: AnomalyEvent     // Event critical gần nhất (cho AlertBanner)
  dismissedCriticalId?: string    // ID đã dismiss (tránh hiện lại)
  addAlert(event)                 // Thêm/cập nhật event, dedup theo event_id
  dismissCritical()               // Ghi nhận đã đọc critical
  setInitialAlerts(events)        // Load lịch sử từ REST API
}
```

### 5.3 WebSocket Hook (`frontend/src/hooks/useWebSocket.ts`)

- Kết nối đến `VITE_WS_URL` (default `ws://localhost:8000/ws`)
- Phân loại message: `heartbeat` → cập nhật `lastHeartbeat`; `anomaly` → dispatch `addAlert` vào Zustand + gọi callback `onAnomaly`
- **Auto-reconnect:** khi `onclose`, đặt timeout 3 giây rồi gọi `connect()` lại
- Cleanup đúng khi unmount (cancel timeout, close socket)

### 5.4 Metrics Hooks (`frontend/src/hooks/useMetrics.ts`)

- `useServices()` — fetch `/api/metrics/services` một lần khi mount
- `useMetricTimeline(serviceName, metricName)` — fetch `/api/metrics/timeline?minutes=60`, giữ tối đa 200 điểm; hàm `append()` cho phép thêm điểm real-time từ WS
- `useMetricNames(serviceName)` — fetch danh sách metric names cho dropdown

### 5.5 Components

#### `TopBar`
- Hiển thị title "Realtime Operations Monitor"
- **Status dot** WebSocket: `connected` → badge green "ok", `reconnecting` → yellow "warning", `disconnected` → red "critical"
- **Digital clock** cập nhật mỗi giây (dùng `setInterval`)
- **Model pill** hiển thị `IsolationForest` hoặc `fallback` + threshold

#### `AlertBanner`
- Ẩn theo mặc định, chỉ hiện khi có event severity `critical`
- **Auto-hide sau 30 giây** bằng `setTimeout`
- Hiển thị: service name, metric name, score, và **narrative text** từ LLM (nếu có)
- Nút "Dismiss" ghi vào `dismissedCriticalId` để không hiện lại event đó

#### `IncidentCard`
- Dùng HTML `<details>` collapsible
- Summary row: timestamp | service chip | metric name | score (mono font) | severity badge
- Body expanded: **narrative** LLM (hoặc "Đang phân tích…" nếu rỗng) + **rca_causes badges** (pill shape, font mono, màu accent-purple)

#### `MetricTimeline`
- Chart dùng `recharts` `ComposedChart` + `ResponsiveContainer`
- **Sliding window** tối đa 200 điểm (slice(-200))
- **Dropdown** chọn service và metric name
- Append điểm real-time từ WS event (không cần reload)
- `AnomalyOverlay` component highlight các điểm anomaly trên chart

#### `ServiceGrid`
- Lưới 4 cột (responsive 2 cột mobile) hiển thị cards từng service
- Highlight service đang chọn bằng border accent-blue

#### `AlertFeed`
- Danh sách `IncidentCard`, có filter button theo severity
- Scroll container với max-height 420px

---

## 6. Luồng dữ liệu end-to-end

```
[External service] ──► INSERT INTO aiops.metrics (timestamp, service_name, metric_name, value)
                                │
                    mỗi 5 giây (APScheduler)
                                │
                                ▼
               ClickHouse: SELECT metrics WHERE timestamp >= now() - 60s
                                │
                                ▼
               Feature Engineering (rolling mean/std 12pt, rate-of-change)
                                │
                                ▼
               IsolationForest.predict() hoặc fallback z-score
                                │
               anomaly_score > 0.6 ?
                       YES │             NO
                           ▼              └─► (bỏ qua)
               generate_rca_narrative()
               [GPT-4o-mini async, tiếng Việt, 2-3 câu]
                           │
                           ▼
               INSERT anomaly_events (event_id, score, narrative, ...)
                           │
                           ▼
               alert_dedup: tìm incident mở trong 5 phút
               ├─ Tồn tại → UPDATE event_ids, severity
               └─ Không có → INSERT alert_incidents mới
                           │
                           ▼
               ws_manager.broadcast({"type": "anomaly", "data": event})
                           │
                    ┌──────┴──────┐
                    ▼             ▼
             [Browser 1]   [Browser 2]  ... (tất cả WS client)
                    │
                    ▼
             useWebSocket hook nhận message
                    │
                    ▼
             Zustand addAlert() → alerts[], lastCritical
                    │
          ┌─────────┼──────────────┐
          ▼         ▼              ▼
    AlertBanner  IncidentCard  MetricTimeline
    (nếu critical) (feed list)  (append điểm)
```

---

## 7. Checklist Audit

### ClickHouse Schema

| # | Checklist Item | Kết quả | Ghi chú |
|---|---|---|---|
| 1 | 5 tables: metrics, logs, traces, anomaly_events, alert_incidents | **PASS** | Đủ 5 bảng trong init_schema.sql |
| 2 | ENGINE MergeTree, PARTITION BY, ORDER BY, TTL cho mỗi bảng | **PASS** | Tất cả 5 bảng đều có đầy đủ |
| 3 | LowCardinality cho low-cardinality columns | **PASS** | service_name, host, env, metric_name, level, model_name… đều là LowCardinality |
| 4 | CODEC DoubleDelta+LZ4 cho timestamp, ZSTD cho long text | **PASS** | timestamp/start_time: DoubleDelta+LZ4; message/attributes/rca_causes/narrative: ZSTD(3) |
| 5 | anomaly_events: UUID event_id với DEFAULT generateUUIDv4() | **PASS** | `event_id UUID DEFAULT generateUUIDv4()` |
| 6 | alert_incidents: resolved_at Nullable(DateTime64(3)) | **PASS** | `resolved_at Nullable(DateTime64(3)) DEFAULT NULL` |
| 7 | TTL dùng toDateTime() wrapper (required cho DateTime64 trong CH 24.x) | **PASS** | Mọi TTL dùng `toDateTime(timestamp)` wrapper |

### Backend DB Layer

| # | Checklist Item | Kết quả | Ghi chú |
|---|---|---|---|
| 8 | Dùng clickhouse-connect (không dùng clickhouse-driver) | **PASS** | requirements.txt: `clickhouse-connect>=0.7` |
| 9 | Connection pool reused, không tạo lại mỗi request | **PASS** | `@lru_cache(maxsize=1)` trên `get_client()` |
| 10 | Tất cả SQL trong db/queries.py, không inline | **PASS** | Mọi SQL function đều ở queries.py |
| 11 | Query WHERE với indexed columns | **PASS** | WHERE service_name, metric_name, timestamp — tất cả đều là ORDER BY key |

### Backend ML Model

| # | Checklist Item | Kết quả | Ghi chú |
|---|---|---|---|
| 12 | IsolationForest với contamination=0.05, n_estimators=100 | **PASS** | `IsolationForest(contamination=0.05, n_estimators=100, random_state=42)` |
| 13 | Train từ ClickHouse data khi startup | **PASS** | `load_or_train_detector()` trong lifespan |
| 14 | Fallback nếu < 100 rows: dùng fixed threshold, không crash | **PASS** | `if rows_used < 100: return None, 0.6, rows_used` |
| 15 | Lưu model pkl bằng joblib vào model_store/ | **PASS** | `joblib.dump(model, model_path)` vào MODEL_STORE |
| 16 | Load pkl nếu tồn tại, không retrain | **PASS** | Kiểm tra `model_path.exists() and manifest_path.exists() and not retrain` |
| 17 | manifest.json ghi lại train timestamp | **PASS** | manifest có `trained_at`, `rows_used`, `threshold`, `model_path` |

### Backend Scheduler

| # | Checklist Item | Kết quả | Ghi chú |
|---|---|---|---|
| 18 | APScheduler chạy mỗi POLL_INTERVAL_SEC (default 5s) | **PASS** | `add_job(poll_once, "interval", seconds=POLL_INTERVAL_SEC)` |
| 19 | Khởi động trong FastAPI lifespan, shutdown gracefully | **PASS** | Start trong lifespan startup; `await poller.shutdown()` trong teardown |
| 20 | Feature extraction: rolling mean/std window 12 + rate-of-change | **PASS** | `rolling_mean_12`, `rolling_std_12`, `rate_of_change` trong features.py |
| 21 | Sau inference: write anomaly_events → dedup → WS broadcast | **PASS** | `write_anomaly` → `dedup_process` → `ws_manager.broadcast` |
| 22 | Gọi generate_rca_narrative() và gắn narrative vào event | **PASS** | `event["narrative"] = await generate_rca_narrative(...)` trước khi write/broadcast |

### Backend WebSocket

| # | Checklist Item | Kết quả | Ghi chú |
|---|---|---|---|
| 23 | ConnectionManager giữ list active connections | **PASS** | `self.active: list[WebSocket]` |
| 24 | broadcast() gửi JSON schema đúng với narrative field | **PASS** | `ws.send_json(message)`; event dict có key `narrative` |
| 25 | Heartbeat mỗi 10 giây | **PASS** | `asyncio.wait_for(stop_event.wait(), timeout=10)` |
| 26 | disconnect() xóa client khỏi list | **PASS** | `self.active.remove(ws)` |

### Backend LLM (rca_narrator.py)

| # | Checklist Item | Kết quả | Ghi chú |
|---|---|---|---|
| 27 | File tồn tại tại backend/services/rca_narrator.py | **PASS** | File tồn tại |
| 28 | Dùng AsyncOpenAI | **PASS** | `from openai import AsyncOpenAI` |
| 29 | API key từ env OPENAI_API_KEY | **PASS** | `api_key = os.getenv("OPENAI_API_KEY")` |
| 30 | Prompt tiếng Việt, 2-3 câu | **PASS** | "Giải thích ngắn gọn (2-3 câu, tiếng Việt)" |
| 31 | temperature=0.3, max_tokens=150 | **PASS** | `temperature=0.3, max_tokens=150` |
| 32 | try/except: trả "" khi lỗi, không bao giờ crash | **PASS** | `except Exception: logger.warning(...); return ""` |

### Backend Alert Dedup

| # | Checklist Item | Kết quả | Ghi chú |
|---|---|---|---|
| 33 | Cửa sổ 5 phút per service_name | **PASS** | `WHERE created_at >= now() - INTERVAL 5 MINUTE AND service_name = ...` |
| 34 | Severity mapping: >=0.85 critical, >=0.70 warning, else info | **PASS** | `severity_for_score()` trong anomaly_writer.py, được import vào alert_dedup.py |

### Backend REST API

| # | Checklist Item | Kết quả | Ghi chú |
|---|---|---|---|
| 35 | GET /api/metrics/timeline | **PASS** | `routers/metrics.py` |
| 36 | GET /api/metrics/services | **PASS** | `routers/metrics.py` |
| 37 | GET /api/alerts/recent | **PASS** | `routers/alerts.py` |
| 38 | GET /api/alerts/incidents | **PASS** | `routers/alerts.py` |
| 39 | POST /api/model/retrain | **PASS** | `main.py` |
| 40 | GET /api/health | **PASS** | `routers/health.py` |
| 41 | GET /ws WebSocket | **PASS** | `@app.websocket("/ws")` trong `main.py` |
| 42 | CORS enabled | **PASS** | `CORSMiddleware(allow_origins=["*"], ...)` |

### Frontend

| # | Checklist Item | Kết quả | Ghi chú |
|---|---|---|---|
| 43 | theme.css có --bg-base, --bg-surface, --accent-red, --accent-green | **PASS** | Đầy đủ tất cả variables |
| 44 | Inter + JetBrains Mono fonts imported | **PASS** | Import từ Google Fonts trong index.html |
| 45 | WS hook: auto-reconnect, phân loại message, Zustand dispatch | **PASS** | Reconnect 3s; phân loại heartbeat/anomaly; `addAlert()` dispatch |
| 46 | MetricTimeline với Recharts, sliding window, dropdown | **PASS** | ComposedChart, slice(-200), dropdown service+metric |
| 47 | AlertBanner: ẩn mặc định, critical only, narrative text, auto-hide 30s | **PASS** | `setVisible(false)` after `setTimeout(30000)`; hiển thị `lastCritical.narrative` |
| 48 | IncidentCard: narrative, rca_causes badges, severity badge | **PASS** | Đầy đủ: narrative || "Đang phân tích…", cause badges, StatusBadge |
| 49 | TopBar: dot indicator, digital clock, model text | **PASS** | StatusBadge WS status, `setInterval` clock 1s, model-pill |

### Docker

| # | Checklist Item | Kết quả | Ghi chú |
|---|---|---|---|
| 50 | 3 services: clickhouse, backend, frontend | **PASS** | docker-compose.yml có đủ 3 services |
| 51 | clickhouse mount init_schema.sql | **PASS** | `./db/init_schema.sql:/docker-entrypoint-initdb.d/init.sql` |
| 52 | backend depends_on clickhouse | **PASS** | `depends_on: - clickhouse` |
| 53 | .env.example tồn tại | **PASS** | File `.env.example` tồn tại với đầy đủ keys |

### Tổng kết Checklist

| Kết quả | Số lượng |
|---|---|
| **PASS** | **53 / 53** |
| **FAIL** | **0** |
| **MISSING** | **0** |

**Tất cả 53 mục đều PASS.**

---

## 8. Hướng dẫn chạy

### 8.1 Yêu cầu

- Docker Desktop (hoặc Docker Engine + Compose plugin)
- OpenAI API Key (tùy chọn — LLM narrator sẽ bị tắt nếu thiếu)

### 8.2 Cấu hình môi trường

```bash
cp .env.example .env
# Sửa .env, ít nhất đặt OPENAI_API_KEY nếu muốn dùng LLM:
# OPENAI_API_KEY=sk-...
```

Nội dung `.env.example`:
```
OPENAI_API_KEY=sk-...
CLICKHOUSE_HOST=localhost
CLICKHOUSE_PORT=8123
CLICKHOUSE_DB=aiops
CLICKHOUSE_USER=default
CLICKHOUSE_PASS=
POLL_INTERVAL_SEC=5
LOOKBACK_SEC=60
ANOMALY_THRESHOLD=0.6
MODEL_STORE=model_store
```

### 8.3 Khởi động toàn bộ stack

```bash
docker compose up --build
```

Sau khi khởi động:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- ClickHouse HTTP: http://localhost:8123
- ClickHouse native: localhost:9000

### 8.4 Kiểm tra health

```bash
curl http://localhost:8000/api/health
# Expected:
# {"status":"ok","clickhouse":"ok","model_loaded":true,"model_name":"IsolationForest","threshold":0.6,"ws_clients":0}
```

### 8.5 Nạp test data vào ClickHouse

```bash
# Kết nối vào ClickHouse và insert sample metrics
docker exec -it <clickhouse-container> clickhouse-client --database aiops

INSERT INTO aiops.metrics (service_name, host, metric_name, value, timestamp)
VALUES
  ('svc-order', 'host-1', 'latency_ms', 125.0, now()),
  ('svc-order', 'host-1', 'cpu_usage', 45.2, now()),
  ('svc-payment', 'host-2', 'error_rate', 0.02, now());
```

### 8.6 Trigger retrain model

```bash
curl -X POST http://localhost:8000/api/model/retrain
```

### 8.7 Kiểm tra APIs

```bash
# Danh sách services
curl http://localhost:8000/api/metrics/services

# Timeline metric
curl "http://localhost:8000/api/metrics/timeline?service_name=svc-order&metric_name=latency_ms&minutes=60"

# Recent alerts
curl "http://localhost:8000/api/alerts/recent?limit=20&status=open"

# Incidents
curl "http://localhost:8000/api/alerts/incidents?severity=critical"
```

### 8.8 Chạy selftest ML

```bash
docker exec -it <backend-container> python -m backend.models.detector --selftest
# Expected output:
# {"rows": 10, "max_score": 0.8xx, "model_loaded": true}
```

### 8.9 Dừng stack

```bash
docker compose down
# Xóa cả volume ClickHouse (reset data):
docker compose down -v
```

---

## 9. Vấn đề còn lại

Qua quá trình audit, **không có FAIL hay MISSING item** nào trong checklist 53 mục. Tuy nhiên, có một số điểm nên lưu ý khi triển khai thực tế:

### 9.1 Điểm cần chú ý (không phải lỗi, nhưng nên biết)

**CORS quá rộng:**
`allow_origins=["*"]` phù hợp cho dev/internal nhưng cần giới hạn trong môi trường production. Nên đặt origin list cụ thể qua env var.

**ClickHouse port trong config vs docker-compose:**
`config.py` default `CLICKHOUSE_PORT=9000` (native), nhưng `docker-compose.yml` set `CLICKHOUSE_PORT=8123` (HTTP). `clickhouse-connect` hỗ trợ cả hai, nhưng nên đồng nhất documentation để tránh nhầm lẫn. Hiện tại hoạt động đúng vì env var override.

**rca_causes luôn là list rỗng:**
Trong `anomaly_writer.py`, `anomaly_payload()` luôn set `rca_causes: []`. Không có logic tự động điền nguyên nhân. LLM prompt có fallback text "đang phân tích" cho trường hợp này. Nếu muốn có causes cụ thể, cần thêm rule-based engine hoặc LLM phân tích sâu hơn.

**Không có authentication:**
API và WebSocket không có auth. Không phải vấn đề nếu đây là internal tool, nhưng cần thêm nếu expose public.

**rca_causes trong DB lưu dạng JSON string:**
`write_anomaly()` dùng `json.dumps(event.get("rca_causes", []))` để chuyển list → string trước khi insert. Query `q_recent_alerts` trả về string thô, router `alerts.py` parse lại bằng `_parse_rca()`. Hoạt động đúng, nhưng là pattern dễ gây bug nếu format thay đổi.

**Model không tự retrain định kỳ:**
Model chỉ train khi startup (nếu pkl chưa có) hoặc khi gọi `POST /api/model/retrain`. Không có scheduled retrain. Trong môi trường production với data drift, nên thêm cronjob retrain hàng ngày.

**Frontend không load lịch sử alerts khi mount:**
`anomalyStore` chỉ nhận events qua WebSocket. Nếu reload trang, danh sách alerts trống cho đến khi có event mới. `setInitialAlerts()` đã được định nghĩa trong store nhưng **không được gọi** trong `App.tsx`. Nên thêm `useEffect` fetch `/api/alerts/recent` khi mount và gọi `setInitialAlerts()`.

### 9.2 Cải tiến đề xuất (ngoài phạm vi checklist)

1. **Load initial alerts:** Gọi `GET /api/alerts/recent` khi App mount và populate store
2. **Scheduled model retrain:** Thêm APScheduler job retrain mỗi 24h
3. **Production CORS:** Giới hạn origins qua env var `CORS_ORIGINS`
4. **Authentication:** JWT hoặc API key cho REST và WS
5. **Metrics ingestion API:** Thêm `POST /api/metrics/ingest` để services đẩy data trực tiếp thay vì phải insert thẳng vào ClickHouse
6. **Alert resolve flow:** Thêm `PATCH /api/alerts/incidents/{id}/resolve` để đóng incident

---

*Tài liệu này phản ánh trạng thái source code tại thời điểm audit ngày 2026-06-27. Mọi thay đổi sau đó cần được cập nhật thủ công.*
