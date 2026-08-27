"""Train a frozen-backbone MobileNetV2 defect classifier on synthetic images."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import cv2
import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset
from torchvision import models, transforms

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from model.classes import DEFECT_CLASSES

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]


class CsvImageDataset(Dataset):
    def __init__(self, root: Path, split: str, augment: bool = False):
        self.root = Path(root)
        self.rows = []
        with (self.root / "labels.csv").open(encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                if row["split"] == split:
                    self.rows.append(row)
        ops = [transforms.ToPILImage(), transforms.Resize((224, 224))]
        if augment:
            ops += [
                transforms.ColorJitter(0.15, 0.15, 0.1, 0.05),
                transforms.RandomHorizontalFlip(),
            ]
        ops += [transforms.ToTensor(), transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD)]
        self.tf = transforms.Compose(ops)

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, idx: int):
        row = self.rows[idx]
        img = cv2.imread(str(self.root / row["filename"]))
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        y = DEFECT_CLASSES.index(row["defect_class"])
        return self.tf(img), y


def build_model(
    num_classes: int = 6,
    freeze_backbone: bool = True,
    unfreeze_last: int = 0,
) -> nn.Module:
    try:
        weights = models.MobileNet_V2_Weights.IMAGENET1K_V1
        model = models.mobilenet_v2(weights=weights)
    except Exception:
        model = models.mobilenet_v2(weights=None)
    if freeze_backbone:
        for param in model.features.parameters():
            param.requires_grad = False
        if unfreeze_last > 0:
            children = list(model.features.children())
            for block in children[-unfreeze_last:]:
                for param in block.parameters():
                    param.requires_grad = True
    in_features = model.classifier[1].in_features
    model.classifier[1] = nn.Linear(in_features, num_classes)
    return model


def accuracy(model: nn.Module, loader: DataLoader, device: torch.device) -> float:
    model.eval()
    correct = total = 0
    with torch.no_grad():
        for xb, yb in loader:
            xb, yb = xb.to(device), yb.to(device)
            pred = model(xb).argmax(1)
            correct += int((pred == yb).sum().item())
            total += int(yb.numel())
    return correct / max(total, 1)


def train(
    data_dir: Path,
    out_dir: Path,
    epochs: int = 6,
    batch_size: int = 32,
    lr: float = 1e-3,
    unfreeze_last: int = 0,
    resume: Path | None = None,
) -> dict:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    train_ds = CsvImageDataset(data_dir, "train", augment=True)
    val_ds = CsvImageDataset(data_dir, "val", augment=False)
    test_ds = CsvImageDataset(data_dir, "test", augment=False)
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False, num_workers=0)
    test_loader = DataLoader(test_ds, batch_size=batch_size, shuffle=False, num_workers=0)

    model = build_model(unfreeze_last=unfreeze_last).to(device)
    if resume and Path(resume).exists():
        ckpt = torch.load(resume, map_location=device, weights_only=False)
        model.load_state_dict(ckpt["state_dict"])
        # Re-apply unfreeze after load
        if unfreeze_last > 0:
            for param in model.features.parameters():
                param.requires_grad = False
            for block in list(model.features.children())[-unfreeze_last:]:
                for param in block.parameters():
                    param.requires_grad = True
            for param in model.classifier.parameters():
                param.requires_grad = True

    opt = torch.optim.Adam(filter(lambda p: p.requires_grad, model.parameters()), lr=lr)
    loss_fn = nn.CrossEntropyLoss()
    history = []
    best_val = -1.0
    out_dir.mkdir(parents=True, exist_ok=True)
    best_path = out_dir / "best.pt"

    for epoch in range(1, epochs + 1):
        model.train()
        running = 0.0
        n = 0
        for xb, yb in train_loader:
            xb, yb = xb.to(device), yb.to(device)
            opt.zero_grad()
            logits = model(xb)
            loss = loss_fn(logits, yb)
            loss.backward()
            opt.step()
            running += float(loss.item()) * int(yb.size(0))
            n += int(yb.size(0))
        val_acc = accuracy(model, val_loader, device)
        row = {
            "epoch": epoch,
            "train_loss": running / max(n, 1),
            "val_acc": val_acc,
        }
        history.append(row)
        print(row, flush=True)
        if val_acc > best_val:
            best_val = val_acc
            torch.save(
                {
                    "state_dict": model.state_dict(),
                    "classes": DEFECT_CLASSES,
                    "val_acc": val_acc,
                },
                best_path,
            )

    ckpt = torch.load(best_path, map_location=device, weights_only=False)
    model.load_state_dict(ckpt["state_dict"])
    test_acc = accuracy(model, test_loader, device)
    metrics = {
        "best_val_acc": best_val,
        "test_acc": test_acc,
        "epochs": epochs,
        "train_size": len(train_ds),
        "val_size": len(val_ds),
        "test_size": len(test_ds),
        "device": str(device),
        "unfreeze_last": unfreeze_last,
        "history": history,
        "checkpoint": str(best_path),
        "classes": DEFECT_CLASSES,
    }
    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print({"test_acc": test_acc, "best_val_acc": best_val}, flush=True)
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default=str(ROOT / "data" / "synthetic"))
    parser.add_argument("--out", default=str(ROOT / "model" / "checkpoints"))
    parser.add_argument("--epochs", type=int, default=6)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--unfreeze-last", type=int, default=0)
    parser.add_argument("--resume", default="")
    args = parser.parse_args()
    train(
        Path(args.data),
        Path(args.out),
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        unfreeze_last=args.unfreeze_last,
        resume=Path(args.resume) if args.resume else None,
    )


if __name__ == "__main__":
    main()
