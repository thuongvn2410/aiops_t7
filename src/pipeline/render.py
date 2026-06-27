from __future__ import annotations

import argparse
import base64
import json
from io import BytesIO

import matplotlib.pyplot as plt
import numpy as np
from sklearn.metrics import PrecisionRecallDisplay, RocCurveDisplay, confusion_matrix

from src.pipeline.state import report_dir, resolve_run_id, run_dir, stage_complete


def _save_current(path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(path, dpi=140)
    plt.close()


def _image_b64(path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def _load_full(root):
    full_path = root / "parsed" / "metrics_full.json"
    if full_path.exists():
        return json.loads(full_path.read_text(encoding="utf-8"))
    public = json.loads((root / "parsed" / "metrics.json").read_text(encoding="utf-8"))
    for model in public["models"]:
        model["scores"] = []
        model["labels"] = []
    return public


def _plot_roc(models, output):
    plt.figure(figsize=(8, 5))
    plotted = False
    for model in models:
        if model.get("scores") and len(set(model.get("labels", []))) > 1:
            RocCurveDisplay.from_predictions(model["labels"], model["scores"], name=model["name"])
            plotted = True
    if not plotted:
        plt.plot([0, 1], [0, 1], label="no scored models")
    plt.title("ROC Curves")
    plt.legend()
    _save_current(output)


def _plot_pr(models, output):
    plt.figure(figsize=(8, 5))
    plotted = False
    for model in models:
        if model.get("scores") and len(set(model.get("labels", []))) > 1:
            PrecisionRecallDisplay.from_predictions(model["labels"], model["scores"], name=model["name"])
            plotted = True
    if not plotted:
        plt.plot([0, 1], [1, 0], label="no scored models")
    plt.title("Precision-Recall Curves")
    plt.legend()
    _save_current(output)


def _plot_confusion(models, output):
    count = max(1, len(models))
    cols = min(3, count)
    rows = int(np.ceil(count / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(4 * cols, 3.5 * rows))
    axes = np.array(axes).reshape(-1)
    for ax, model in zip(axes, models):
        labels = np.array(model.get("labels", []))
        scores = np.array(model.get("scores", []))
        if len(labels) and len(scores):
            pred = (scores >= model["optimal_threshold"]).astype(int)
            cm = confusion_matrix(labels, pred, labels=[0, 1])
        else:
            cm = np.zeros((2, 2), dtype=int)
        ax.imshow(cm, cmap="Blues")
        ax.set_title(model["name"])
        for (i, j), value in np.ndenumerate(cm):
            ax.text(j, i, str(value), ha="center", va="center")
        ax.set_xticks([0, 1])
        ax.set_yticks([0, 1])
    for ax in axes[len(models) :]:
        ax.axis("off")
    fig.suptitle("Confusion Matrices")
    _save_current(output)


def _plot_scores(models, output):
    plt.figure(figsize=(8, 5))
    for model in models:
        scores = model.get("scores", [])
        if scores:
            plt.hist(scores, bins=30, alpha=0.35, label=model["name"])
    if not any(model.get("scores") for model in models):
        plt.hist([0], bins=1, label="no scores")
    plt.title("Score Distributions")
    plt.legend()
    _save_current(output)


def _write_html(data, out_dir):
    images = {
        "ROC Curves": out_dir / "roc_curves.png",
        "Precision-Recall Curves": out_dir / "pr_curves.png",
        "Confusion Matrices": out_dir / "confusion_matrices.png",
        "Score Distributions": out_dir / "score_distributions.png",
    }
    rows = "\n".join(
        f"<tr><td>{m['name']}</td><td>{m['precision']:.3f}</td><td>{m['recall']:.3f}</td><td>{m['f1']:.3f}</td><td>{m['auc_roc']:.3f}</td><td>{m['auc_pr']:.3f}</td></tr>"
        for m in data["models"]
    )
    img_html = "\n".join(f"<h2>{title}</h2><img src='data:image/png;base64,{_image_b64(path)}' />" for title, path in images.items())
    html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>AIOps Summary {data['run_id']}</title>
<style>body{{font-family:Arial,sans-serif;margin:32px}}table{{border-collapse:collapse}}td,th{{border:1px solid #ddd;padding:8px}}img{{max-width:100%;height:auto}}</style>
</head><body>
<h1>AIOps Anomaly Detection Summary</h1>
<p>Run: {data['run_id']} | Evaluated: {data['evaluated_at']}</p>
<table><thead><tr><th>Model</th><th>Precision</th><th>Recall</th><th>F1</th><th>AUC-ROC</th><th>AUC-PR</th></tr></thead><tbody>{rows}</tbody></table>
{img_html}
</body></html>"""
    (out_dir / "summary_report.html").write_text(html, encoding="utf-8")


def run(run_id: str | None = None) -> str:
    selected = resolve_run_id(run_id)
    if stage_complete(selected, "render"):
        print(f"render skip run_id={selected}: report files already exist")
        return selected
    root = run_dir(selected)
    out_dir = report_dir(selected)
    out_dir.mkdir(parents=True, exist_ok=True)
    data = _load_full(root)
    models = data.get("models", [])
    _plot_roc(models, out_dir / "roc_curves.png")
    _plot_pr(models, out_dir / "pr_curves.png")
    _plot_confusion(models, out_dir / "confusion_matrices.png")
    _plot_scores(models, out_dir / "score_distributions.png")
    _write_html(data, out_dir)
    print("leaderboard")
    for model in sorted(models, key=lambda item: item.get("f1", 0), reverse=True):
        print(f"{model['name']:18s} precision={model['precision']:.3f} recall={model['recall']:.3f} f1={model['f1']:.3f} auc_pr={model['auc_pr']:.3f}")
    return selected


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args()
    run(args.run_id)


if __name__ == "__main__":
    main()
