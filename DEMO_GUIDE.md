# Demo Guide — "Payment Service Under Attack"

Kịch bản demo mô phỏng một sự cố DDoS thực tế: hệ thống bình thường → bị tấn công → hồi phục.
Toàn bộ pipeline AIOps sẽ tự động phát hiện và giải thích bằng tiếng Việt.

---

## Chuẩn bị (1 lần)

```bash
# 1. Copy env và điền OPENAI_API_KEY
cp .env.example .env
# Mở .env, thêm: OPENAI_API_KEY=sk-proj-...

# 2. Khởi động toàn bộ hệ thống
docker-compose up -d --build

# 3. Chờ ~10 giây, kiểm tra health
curl http://localhost:8000/api/health
# Expected: {"status":"ok","clickhouse":"ok","model_loaded":false,...}
```

---

## Chạy Demo

### Terminal 1 — Theo dõi backend logs (realtime)
```bash
docker-compose logs -f backend
```

### Terminal 2 — Chạy kịch bản inject metrics
```bash
pip install clickhouse-connect   # nếu chưa có
python scripts/demo_scenario.py
```

### Trình duyệt — Mở frontend
```
http://localhost:3000
```

---

## Kịch bản 3 giai đoạn

```
Timeline (mỗi giai đoạn ~2 phút):

 0:00 ──────────────── 2:00 ──────────────── 4:00 ──────────────── 6:00
   │                     │                     │                     │
   │   PHASE 1           │   PHASE 2           │   PHASE 3           │
   │   BASELINE          │   INCIDENT          │   RECOVERY          │
   │   (bình thường)     │   (DDoS attack)     │   (hồi phục)        │
   │                     │                     │                     │
   │  cpu ~30%           │  cpu ~92% ⚠         │  cpu 92%→30%        │
   │  latency ~120ms     │  latency ~850ms ⚠   │  latency hạ dần     │
   │  error_rate ~0.5%   │  error_rate ~18% ⚠  │  error_rate hạ dần  │
   │  throughput ~850rps │  throughput ~2100rps │  throughput bình    │
```

### Phase 1 — BASELINE (xanh)
- 3 services inject metric bình thường mỗi 5 giây
- Scheduler backend poll và KHÔNG phát hiện anomaly
- Frontend: MetricTimeline hiện đường thẳng ổn định

### Phase 2 — INCIDENT (đỏ)
**Những gì xảy ra tự động trong vòng 5–15 giây:**
1. Scheduler phát hiện `cpu_usage`, `request_latency`, `error_rate` vượt ngưỡng
2. `rca_narrator.py` gọi OpenAI gpt-4o-mini → sinh narrative tiếng Việt
3. WebSocket broadcast `{"type": "anomaly", "data": {..., "narrative": "..."}}`
4. Frontend:
   - **AlertBanner** slide xuống (critical alert)
   - **MetricTimeline** vùng đỏ highlight anomaly
   - **IncidentCard** hiện narrative + rca_causes badges

**Ví dụ narrative LLM sẽ sinh:**
> *"Service svc-payment đang gặp sự cố nghiêm trọng khi CPU tăng đột biến lên 92% (baseline: 30%), kết hợp với latency tăng 7x lên 850ms và tỷ lệ lỗi 18%. Dấu hiệu này phù hợp với tấn công DDoS hoặc traffic spike bất thường từ bên ngoài, cần kiểm tra ngay load balancer và rate limiting."*

### Phase 3 — RECOVERY (cyan)
- Metrics giảm dần theo đường sigmoid về baseline
- Backend tiếp tục poll — anomaly score giảm dần
- Frontend: vùng đỏ thu hẹp lại

---

## Kiểm tra từng bước sau demo

```bash
# Xem alerts đã được ghi
curl "http://localhost:8000/api/alerts/recent?limit=20" | python -m json.tool

# Xem incidents
curl "http://localhost:8000/api/alerts/incidents?limit=5" | python -m json.tool

# Timeline cpu_usage của payment service
curl "http://localhost:8000/api/metrics/timeline?service_name=svc-payment&metric_name=cpu_usage&minutes=30" | python -m json.tool

# Xem trực tiếp trong ClickHouse
docker exec aiops-anomaly-detection-clickhouse-1 \
  clickhouse-client --query \
  "SELECT service_name, metric_name, anomaly_score, narrative FROM aiops.anomaly_events ORDER BY detected_at DESC LIMIT 10 FORMAT Pretty"
```

---

## Tùy chỉnh demo

```bash
# Demo nhanh hơn (mỗi tick 2s, mỗi phase 10 ticks = 20 giây)
python scripts/demo_scenario.py --baseline-ticks 10 --incident-ticks 10 --recovery-ticks 10 --interval 2

# Demo dài hơn để có nhiều data
python scripts/demo_scenario.py --baseline-ticks 60 --incident-ticks 60 --recovery-ticks 60 --interval 5

# Chỉ chạy phase incident để trigger alert ngay
python scripts/demo_scenario.py --baseline-ticks 0 --incident-ticks 20 --recovery-ticks 0
```

---

## Những điểm highlight khi demo

| Thời điểm | Nói gì | Chỉ vào đâu |
|---|---|---|
| Phase 1 bắt đầu | "Đây là hệ thống bình thường — 3 microservices, metrics ổn định" | MetricTimeline đường xanh |
| ~2:00 chuyển Phase 2 | "Bây giờ mô phỏng DDoS attack — CPU, latency, error rate tăng đột biến" | Terminal logs backend |
| ~2:10 anomaly đầu tiên | "Backend phát hiện anomaly trong vòng 5–10 giây" | Log: `anomalies=3 latency_ms=...` |
| AlertBanner xuất hiện | "Hệ thống tự động tạo alert và gọi GPT-4o-mini giải thích bằng tiếng Việt" | AlertBanner + narrative text |
| IncidentCard | "Nguyên nhân được phân loại tự động: cpu_spike, high_latency..." | rca_causes badges |
| Phase 3 | "Sau khi team xử lý, hệ thống hồi phục — anomaly score giảm dần" | MetricTimeline màu đỏ thu hẹp |

---

## Dọn dẹp sau demo

```bash
docker-compose down -v   # xóa cả data ClickHouse
```
