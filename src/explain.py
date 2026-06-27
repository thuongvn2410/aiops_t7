from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def save_feature_contributions(feature_names: list[str], values, output: Path, top_k: int = 5) -> Path:
    scores = np.asarray(values, dtype=float)
    order = np.argsort(np.abs(scores))[-top_k:]
    output.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(6, 3))
    plt.barh([feature_names[i] for i in order], scores[order])
    plt.tight_layout()
    plt.savefig(output, dpi=140)
    plt.close()
    return output


def save_attention_heatmap(matrix, output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(5, 4))
    plt.imshow(matrix, aspect="auto", cmap="viridis")
    plt.colorbar()
    plt.tight_layout()
    plt.savefig(output, dpi=140)
    plt.close()
    return output
