# Vision model metrics

Honest numbers for the presentation slide.

## Dataset

- **3,456** synthetic 224×224 images (`scripts/generate_dataset.py --per-combo 48`)
- Balanced across 6 defect classes × 4 materials × 3 patterns
- Split 70/15/15: train 2418 / val 516 / test 522
- Details: `data/dataset_summary.md`

## MobileNetV2 transfer learning (CPU)

| Stage | Setup | Best val | Test |
| --- | --- | --- | --- |
| Baseline | Frozen backbone, 6 epochs | 60.9% | 60.5% |
| Fine-tune | Unfreeze last 4 feature blocks, 5 epochs @ 3e-4 | **89.3%** | **86.4%** |

Checkpoint: `model/checkpoints/best.pt` (gitignored — regenerate with `python model/train.py`).

## What to tell judges

1. Training data is **synthetic**. Labels are exact because the generator wrote them.
2. **86% on held-out synthetic test** is a strong starting point, not a claim about factory cameras.
3. Expect a drop on phone photos / real NSW AOI. That gap is the next experiment (`data/real/`), not a failure of the reasoning engine.
4. Vision is **Bonus 1**. The product differentiator is material-aware cause ranking (NSW 5× nozzle rule). If vision is wrong, the operator’s answers still drive a useful ranked checklist.

## Reproduce

```powershell
python scripts/generate_dataset.py --per-combo 48
python model/train.py --epochs 6
python model/train.py --epochs 5 --lr 0.0003 --unfreeze-last 4 --resume model/checkpoints/best.pt
```
