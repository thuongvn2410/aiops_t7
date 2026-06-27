from __future__ import annotations

import numpy as np
from joblib import dump, load

try:
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset
except Exception:
    torch = None
    nn = None
    DataLoader = None
    TensorDataset = None


if torch is not None:

    class AutoencoderNet(nn.Module):
        def __init__(self, input_dim: int) -> None:
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(input_dim, 128),
                nn.ReLU(),
                nn.Linear(128, 64),
                nn.ReLU(),
                nn.Linear(64, 32),
                nn.ReLU(),
                nn.Linear(32, 64),
                nn.ReLU(),
                nn.Linear(64, 128),
                nn.ReLU(),
                nn.Linear(128, input_dim),
            )

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            return self.net(x)

else:
    AutoencoderNet = None


class AutoencoderAnomaly:
    def __init__(self, input_dim: int, device: str | None = None) -> None:
        self.input_dim = input_dim
        self.backend = "torch" if torch is not None else "numpy_svd"
        self.device = device or ("cuda" if torch is not None and torch.cuda.is_available() else "cpu")
        self.model = AutoencoderNet(input_dim).to(self.device) if torch is not None else None
        self.mean_: np.ndarray | None = None
        self.components_: np.ndarray | None = None

    def fit(self, x_train: np.ndarray, x_val: np.ndarray | None = None, epochs: int = 4, batch_size: int = 64) -> "AutoencoderAnomaly":
        if torch is None:
            self.mean_ = x_train.mean(axis=0)
            centered = x_train - self.mean_
            _, _, vt = np.linalg.svd(centered, full_matrices=False)
            keep = max(1, min(32, vt.shape[0] // 2 or 1))
            self.components_ = vt[:keep]
            return self

        data = TensorDataset(torch.tensor(x_train, dtype=torch.float32))
        loader = DataLoader(data, batch_size=batch_size, shuffle=False)
        opt = torch.optim.Adam(self.model.parameters(), lr=1e-3)
        loss_fn = nn.MSELoss()
        scaler = torch.cuda.amp.GradScaler(enabled=self.device == "cuda")
        best = float("inf")
        patience = 10
        bad = 0
        for _ in range(epochs):
            self.model.train()
            for (batch,) in loader:
                batch = batch.to(self.device)
                opt.zero_grad(set_to_none=True)
                with torch.cuda.amp.autocast(enabled=self.device == "cuda"):
                    recon = self.model(batch)
                    loss = loss_fn(recon, batch)
                scaler.scale(loss).backward()
                scaler.step(opt)
                scaler.update()
            val_loss = float(np.mean(self.score_samples(x_val if x_val is not None and len(x_val) else x_train[: min(128, len(x_train))])))
            if val_loss < best:
                best = val_loss
                bad = 0
            else:
                bad += 1
            if bad >= patience:
                break
        return self

    def score_samples(self, x: np.ndarray) -> np.ndarray:
        if self.backend == "numpy_svd":
            centered = x - self.mean_
            recon = centered @ self.components_.T @ self.components_ + self.mean_
            return np.mean((recon - x) ** 2, axis=1)
        self.model.eval()
        with torch.no_grad():
            tensor = torch.tensor(x, dtype=torch.float32, device=self.device)
            recon = self.model(tensor)
            return torch.mean((recon - tensor) ** 2, dim=1).detach().cpu().numpy()

    def save(self, path) -> None:
        if self.backend == "numpy_svd":
            dump(
                {
                    "backend": self.backend,
                    "input_dim": self.input_dim,
                    "mean": self.mean_,
                    "components": self.components_,
                },
                path,
            )
            return
        torch.save({"backend": self.backend, "state_dict": self.model.state_dict(), "input_dim": self.input_dim}, path)

    @classmethod
    def load(cls, path, device: str | None = None) -> "AutoencoderAnomaly":
        try:
            payload = load(path)
            if isinstance(payload, dict) and payload.get("backend") == "numpy_svd":
                instance = cls(int(payload["input_dim"]), device=device)
                instance.backend = "numpy_svd"
                instance.mean_ = payload["mean"]
                instance.components_ = payload["components"]
                return instance
        except Exception:
            payload = None
        if torch is None:
            raise RuntimeError("Torch checkpoint cannot be loaded because torch is not installed")
        payload = torch.load(path, map_location=device or "cpu")
        instance = cls(int(payload["input_dim"]), device=device)
        instance.model.load_state_dict(payload["state_dict"])
        return instance
