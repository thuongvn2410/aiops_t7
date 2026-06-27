from __future__ import annotations

from src.pipeline.state import report_dir


def test_render_outputs(rendered_run: str) -> None:
    root = report_dir(rendered_run)
    for name in ["roc_curves.png", "pr_curves.png", "confusion_matrices.png", "score_distributions.png", "summary_report.html"]:
        assert (root / name).exists()
    html = (root / "summary_report.html").read_text(encoding="utf-8")
    assert "data:image/png;base64" in html
