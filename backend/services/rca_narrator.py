from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)
_client = None


def get_openai_client():
    global _client
    if _client is None:
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise ImportError("openai package not installed. Add 'openai>=1.0' to requirements.txt.") from exc
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set")
        _client = AsyncOpenAI(api_key=api_key)
    return _client


async def generate_rca_narrative(
    service_name: str,
    metric_name: str,
    anomaly_score: float,
    rca_causes: list[str],
    metric_value: float,
    baseline_value: float,
) -> str:
    if not os.getenv("OPENAI_API_KEY"):
        return ""
    try:
        client = get_openai_client()
        causes_text = ", ".join(rca_causes) if rca_causes else "đang phân tích"
        prompt = (
            f"Bạn là chuyên gia AIOps. Giải thích ngắn gọn (2-3 câu, tiếng Việt) "
            f"sự cố sau cho kỹ sư vận hành:\n\n"
            f"- Service: {service_name}\n"
            f"- Metric bất thường: {metric_name} = {metric_value:.2f} (baseline: {baseline_value:.2f})\n"
            f"- Anomaly score: {anomaly_score:.2f}/1.0\n"
            f"- Nguyên nhân có thể: {causes_text}\n\n"
            f"Chỉ trả về đoạn giải thích, không thêm tiêu đề hay bullet point."
        )
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:
        logger.warning(f"LLM narrative failed (non-critical): {exc}")
        return ""
