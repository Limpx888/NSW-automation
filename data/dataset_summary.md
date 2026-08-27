# Dataset summary

Synthetic top-down dispense images. Labels are ground truth from the generator, not hand-annotated photos.

- Total images: **3456**
- Split: train 2418 / val 516 / test 522 (70/15/15, stratified by defect class)
- Image size: 224×224

## By defect class
- under_dispense: 576
- over_dispense: 576
- missing: 576
- inconsistent_volume: 576
- spreading: 576
- air_bubble_irregular: 576

## By material
- solder_paste: 864
- silver_epoxy: 864
- uv_glue: 864
- silicone_gel: 864

## By pattern
- dot: 1152
- line: 1152
- dam_fill: 1152

## How it was made
OpenCV procedural shapes (dot, line, dam-and-fill) on PCB green / ceramic / metal backgrounds.
Material textures: grainy solder paste, metallic silver epoxy, translucent UV glue, soft-edge silicone.
Defects: shrink/enlarge, skip, multi-deposit variance, bleed, punched voids + satellites.
Augmentation baked in: brightness, blur, noise, rotation, slight perspective warp.

Real photos belong in `data/real/` and are a validation set, not the training set.
