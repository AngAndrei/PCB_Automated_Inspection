# DeepPCB dataset audit

The checked-out upstream DeepPCB dataset contains 1,500 aligned tested/template pairs with six defect classes. `PCBData/trainval.txt` lists 1,000 tested images and `PCBData/test.txt` lists 500. Each line supplies a nominal image path and an annotation path. Actual image names append `_test.jpg` and `_temp.jpg`; annotation directories are siblings ending in `_not`. The pipeline uses the explicit annotation path from each membership line.

Dataset use is research-only according to the upstream README notification. The repository's MIT LICENSE applies to its software; it does not remove that dataset restriction. Raw data, prepared images, and downloaded weights must remain outside Git.

## Class mapping

| Source ID | Source label | App/YOLO ID | App label |
|---|---|---|---|
| 1 | open | 0 | open_circuit |
| 2 | short | 1 | short_circuit |
| 3 | mousebite | 2 | mouse_bite |
| 4 | spur | 3 | spur |
| 5 | copper | 4 | spurious_copper |
| 6 | pin-hole | 5 | pin_hole |

Source annotations give top-left and bottom-right pixel corners. The annotation tool bounds coordinates at `width-1`/`height-1`; its documentation does not define inclusive-area arithmetic. This conversion explicitly interprets corner coordinates continuously, with width `x2-x1` and height `y2-y1`, without adding one pixel. This matches standard YOLO corner conversion. Normalized centers are `(x1+x2)/(2W)` and `(y1+y2)/(2H)`. For a 100x80 fixture, `10 20 30 60 1` becomes `0 0.20 0.50 0.20 0.50`.

Preparation rejects invalid/nonfinite coordinates, nonpositive box areas, out-of-range coordinates, IDs outside 1..6, missing paired images, missing annotations, and empty annotations. Missing or empty annotations are unknown, never inferred to mean defect-free.

## Split audit

Seed 42 and validation group fraction 0.2 yield **802 train / 198 validation / 500 test** tested images. Whole source board directories are selected for validation from trainval only. All original trainval and test memberships are retained. There are no tested-image SHA256 duplicates and no train/validation group overlap in this source checkout.

All seven source board directories used by published trainval also occur in published test:

- group00041/00041
- group13000/13000
- group20085/20085
- group44000/44000
- group50600/50600
- group77000/77000
- group92000/92000

The test protocol is therefore **not board-disjoint**. Results must be described as the published image split, with a group-held-out validation subset. Preparation reports this overlap in `audit.json`; it never claims the published test is an independent-board test. Cross-split identical tested-image bytes are rejected. SHA256 duplicate checks do not establish independence of visually similar neighboring crops.

The source checkout has 1,501 template files (including one unlisted template) and 1,499 unique template hashes. Only the 1,500 published pairs participate in the manifest. Templates are excluded from YOLO images and headline metrics. Their paths, SHA256 values, and known-negative provenance are retained for traceability: upstream describes them as manually checked and cleaned defect-free templates. Such cleaned templates are not a representative production-good set. No false-alarm rate is estimated from missing annotations or from the defective test images. The evaluator returns null good-set rates when no explicit verified-negative images are present.

The manifest records every tested-image hash, annotation hash, group, original membership, assigned split, dimensions, converted class/boxes, and paired-template provenance. `audit.json` contains class counts, split counts, overlap warnings, and duplicate checks. All 1,500 listed tested images in the audited checkout passed strict annotation validation.

## Reproduction

```powershell
$env:PYTHONPATH='src'
.venv/Scripts/python.exe -m pcb_inspection.ml.prepare --source data/raw/DeepPCB --output data/processed/deeppcb --seed 42
```

The output must be empty. Re-running with the same source bytes, seed, and validation fraction produces the same manifest. `data.yaml` additionally contains the resolved local output path for Ultralytics.
