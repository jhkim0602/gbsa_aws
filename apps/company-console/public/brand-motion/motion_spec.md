# WhyYou logo motion brief

## Brand personality

- **Precise** — the wordmark resolves on a stable baseline without elastic deformation.
- **Inquisitive** — the question-mark symbol is the focal beat and the dot completes the idea.
- **Confident** — one consistent professional easing family, restrained scale, and a clean final lockup.

Energy is medium and tone is serious/professional. The primary usage is a first-visit landing-page hero reveal, so the total duration is 1,400 ms. Reduced-motion visitors receive the final static mark immediately.

## Part inventory

| SVG id | Role | Motion |
| --- | --- | --- |
| `wordmark-dark` | “Wh” foundation | left-to-right mask assembly |
| `question-mark` | brand idea / focal mark | soft vertical arrival and settle |
| `question-dot` | answer / completion accent | delayed drop-in follow-through |
| `letter-y`, `letter-o`, `letter-u` | product promise | short staggered baseline arrival |

The source is a 1364×533 RGB raster on solid white. Foreground colors resolve to deep navy (`#020c29`) and cobalt (`#305afd`). The final SVG keeps five simple filled silhouettes split into seven semantic actors. Anti-alias color islands from the source trace were deliberately rejected instead of becoming thousands of 1 px paths.

## Timeline

| Beat | Window | Principle |
| --- | --- | --- |
| Staging hold | 0–168 ms | Staging, anticipation |
| “Wh” establishes context | 168–672 ms | Solid drawing, slow in/out |
| Question mark becomes focal | 280–910 ms | Staging, timing |
| “you” overlaps in sequence | 588–1,169 ms | Overlapping action |
| Dot and all parts settle | 756–1,400 ms | Follow-through, appeal |

The overall choreography follows an approximately 20:50:30 anticipation/action/follow-through shape. There is no squash and no visible bounce because this is enterprise recruiting software.

## Geometry QA

- The starter trace measured IoU 0.951417 after preserving only the two dominant foreground colors.
- The accepted smooth SVG measures IoU **0.944** with `src_only_px=6,524` and `render_only_px=1,123`.
- The accepted fit is intentionally lower than the jagged starter trace because 2,091 anti-alias-only micro contours and pixel-grid turns were replaced with smooth quadratic contours. Structural landmarks, negative spaces, baseline, and proportions remain aligned.
- Seven semantic paths were audited independently: join-angle warnings **0**, short-segment warnings **0**.
- The final render and overlay progress strip show no visible stair-stepping or structural mismatch at landing-page display size.

## Motion QA contract

- Main clock: 1,400 ms.
- Keyframe timing functions use literal cubic Bézier values.
- `animation-fill-mode: both` is used for deterministic seeking.
- Computed transform, opacity, and clip-path values were sampled at 300 ms, 620 ms, and 900 ms; progression follows the intended literal cubic Bézier easing rather than a linear fallback.
- The deterministic `?t=1400` and `?static=1` captures have an exact same-pipeline pixel difference of **0**.
- Significant frames at 0, 280, 620, 900, 1,180, and 1,400 ms show the intended staged cascade without clipping.
- The landing implementation reuses the same SVG paths and supports `prefers-reduced-motion`.
