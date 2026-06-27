# Task-Model Fit Validation

This document records the required task-model fit analysis before any project code is executed.

## Use ML/LLM

| Component | Fit | Rationale |
|---|---:|---|
| Anomaly scoring | Good | Metrics, logs, and traces are multi-modal and noisy; learned scoring can combine weak signals that deterministic thresholds miss. |
| Root cause ranking | Good | Ranking likely causes can use statistical tests plus model evidence against explicit criteria. |
| Alert narrative generation | Good | Natural-language summaries are appropriate after structured anomaly and RCA data already exist. |
| Log template classification | Good | Log template extraction/classification benefits from learned domain patterns in historical logs. |

## Do Not Use LLM

| Component | Better Method | Rationale |
|---|---|---|
| Threshold arithmetic | EVT/POT | Threshold updates require deterministic numeric behavior. |
| Real-time inference below 100 ms | XGBoost/IsolationForest | Latency-bound serving should use compact deterministic models. |
| Exact metric aggregation | Pandas/ClickHouse | Aggregations must be reproducible and auditable. |

## Implementation Decision

The project keeps LLM-style generation out of the critical path. The basic pipeline uses deterministic data processing, classical ML, and compact neural models. Natural-language alert narratives can be layered on top of canonical anomaly events after the structured contract is satisfied.
