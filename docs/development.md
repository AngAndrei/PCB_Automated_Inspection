# Build record

Plan: docs/superpowers/plans/2026-11-12-pcb-defect-segmentation.md

Implementation begins 12 November 2026 on `feat/inspection-app`.

The user requested implementation in this folder and GitHub integration. Work takes place here on a feature branch. The plan is the specification; the latest user clarification makes approximate translucent regions sufficient.

## Pre-flight

| Producer → consumer | Contract |
|---|---|
| Data preparation → training | Six zero-based classes, source-held-out test, reproducible group split, YOLO data.yaml. |
| Model bundle → worker | Immutable ID, weights SHA-256, class map, inference profile. |
| Worker → API → viewer | Original image coordinates, bbox_region, no learned mask claim. |
| Viewer → export | Same ellipse center and radii; opacity is display state. |

Decisions: use an in-place feature branch as requested; use CPU if CUDA is unavailable. Downloaded data, weights, environments, and user inspection files stay out of Git. A small demo workflow may use explicitly labeled fixture detections, while production inspection requires an installed PCB model. Training status and measured quality must be reported honestly.

## Progress

- [x] Data audit/conversion and real development-model training; full baseline pending.
- [x] Image normalization, coordinates and inference contracts.
- [x] SQLite queue, separate worker, API, history, reviews and exports.
- [x] React viewer, desktop/mobile workflow and stale-history regression.
- [x] Packaging, GitHub CI and local repository; remote creation/push blocked by missing Git sign-in and unavailable repository-creation connector.
- [x] Independent review, important fixes, verification and honest development-model status.

Implementation decisions: build in the requested folder on a feature branch; use a bounded CPU development run instead of the full100epoch experiment; expose measured poor accuracy and force manual review. Full-data quality, final test metrics and optional upgrades remain pending.

## Independent review and fixes

Three Important findings were reproduced before fixes: cross-board responses/reviews, unrelated evaluation attachment, and promotion missing an unvalidated default. Two deferred-response frontend regressions and six promotion/status tests went RED->GREEN. Async updates now use selection generations and inspection IDs; promotion checks provenance, preserves measured settings and defaults to manual review. Final Python suite:61 passed; frontend:9 passed; production build and desktop/mobile browser workflow passed. One upstream Starlette/httpx deprecation warning remains.

An automatic approval check rejected local app startup because Ultralytics attempted Google Analytics telemetry. Runtime configuration now disables online mode and sync before model imports; a fresh-process test verifies sync=false, online=false and analytics=false.

Deferred minor M1: auto-refresh can reset loaded history pages, and repeated Load more clicks can duplicate pagination.

Review boundaries: full-data quality, thresholds, camera generalization, production-good false alarms and final test performance remain unmeasured. Source groups cannot prove physical independence. Fresh-machine/GPU behavior and all terminal variants remain unverified; this host startup/live inference was exercised. The app assumes a trusted single local user. Desktop/mobile inspection does not constitute full accessibility certification. Git staging/push remains blocked by read-only metadata and missing repository/authentication capabilities.

GitHub integration: destination AngAndrei/PCB_Automated_Inspection exists and is public. The first source write was rejected with403 Resource not accessible by integration; no source upload or pull request was created. The connected account reports no accessible GitHub App installations. Local Git metadata remains protected here. The connect helper can configure a remote outside this sandbox; local history must be aligned with the published branch before future pushes.

GitHub retry diagnosis: a second write attempt returned403. OpenAI documentation confirms the standard ChatGPT GitHub app is read-only, so the prior advice to reconnect for write permission was incorrect. README now gives normal local Git publication commands; no source was uploaded by the connector.
