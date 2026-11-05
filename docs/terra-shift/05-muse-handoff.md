# Muse implementation handoff

## Collaboration contract

Updated implementation ownership: Codex writes the complete application. The work packages below remain the implementation contract. Muse Code is optional; if used, select Muse Wonder or Wonder Full when an eligible subscription is available. Runtime LLM calls use Muse Wonder (`muse-wonder-1.0`), with no automatic downgrade.

Codex owns requirements, architecture, UI, API, adapters, geospatial calculations, tests and integration. Muse Wonder provides runtime evidence interpretation; SAM provides runtime segmentation. Record actual authorship and model usage. This build was written by Codex, not Muse Code.

`muse` is not currently on the shell PATH. Install from official documentation, inspect `muse --help` and the installed version before assuming CLI flags. Official docs describe `muse exec` for headless work. Model API requests do not themselves edit local files without a coding-agent tool loop.

[Official Muse Code documentation](https://dev.meta.ai/docs/muse-code) distinguishes CLI authentication (`META_API_KEY` for headless use) from API examples (`MODEL_API_KEY`). Configure them locally without printing values. Do not switch to a data-contribution mode merely to reduce cost.

## Full requested target and ten-hour constraint

The user requests completion in ten hours or less without simplifying the product, and confirms the published deadline. The full requested scope is the target, not a promise already demonstrated feasible. Do not silently substitute a static globe, prerecorded-only analysis, fixed-location demo, cosmetic SAM overlay or invented disaster labels.

Required target capabilities:

- Real interactive 3D globe, global search/click and editable square AOI.
- User-chosen observation windows and multi-year range/season.
- Real satellite retrieval and quality-controlled quantitative change.
- Water change/flood context, greening/browning, forest-loss evidence, exposed-ground/degradation indicators, and coast/terrain-change evidence with scientifically appropriate labels.
- SAM region delineation/inspection and clear comparison with spectral evidence.
- Weather history/context, measured area/rate outputs, evidence-aware Muse explanation.
- Before/after view, playable history timeline, MP4/GIF export, source provenance, temporary-session lifecycle and explicit report export. Follow document 09 for aligned frames, missing years, bounded encoding and cleanup.

Not every place/date/theme has adequate observations or can support a diagnosis. Correctly returning insufficient evidence is required behavior; falsely marking an unimplemented feature as an evaluated insufficient-evidence result is prohibited. Keep implementation status distinct from data sufficiency.

If the ten-hour window cannot accommodate the full target, report the exact incomplete capabilities and remaining work. Do not silently call a reduced build the completed product. A validated universal catastrophe classifier is not a credible promise in this window.

## Proposed repository structure

```text
apps/web/src/
  globe/          # Cesium lifecycle, AOI interaction, scientific overlays
  analysis/       # setup, job state, evidence drawer, timeline
  api/            # typed API client
services/api/
  app.py
  contracts.py
  jobs.py
  providers/      # satellite, Meta, weather
  science/        # QA, scaling, grid, indices, changes, rates
  evidence/       # manifests, narrative validation, export
  tests/
artifacts/        # ignored, run-scoped TEMPORARY data; mandatory purge
scripts/          # smoke checks and reproducibility commands
docs/terra-shift/   # this specification
.env.example
.gitignore
```

## Ordered work packages with acceptance criteria

### A. Provider and contract readiness

Create environment validation that reports presence/absence only. Verify a catalog search, signed COG window read, one real SAM response and a structured Muse response. Log billable usage. Pin source collection/version and library versions. Agree on one documented lake/flood case and independent reference before running the evaluation.

Accept when source IDs, band transforms, QA meanings, SAM output parsing and local geographic transforms are demonstrably understood. Failed provider access is surfaced immediately, not concealed with fixtures.

### B. Geospatial measurement kernel

Implement scales, QA, common grid/support, indices, water gain/loss, continuous vegetation change, area and interval-rate functions. Keep them independent of LLMs and UI. Architect reviews this package first.

Required tests: known reflectance values after offsets; QA invalidation; affine pixel area; mask resize/crop inversion; same-image no-change; gain-loss accounting; zero denominators; no overlap; cloudy support; sensor band mapping; actual-date rates. Use synthetic arrays for unit tests, not a mirror of implementation logic.

### C. SAM integration

Render georeferenced real observations, prompt concept/geometry, parse masks, invert transforms and preserve disagreement. Support click-selected object refinement and versioned human correction. Handle no detections separately from no water.

Accept when a mask aligns with its raster and globe geometry, and the result distinguishes original SAM, spectral and edited masks. Displaying a fabricated overlay fails acceptance.

### D. Globe and selection interface

Build the design spec with a single Cesium lifecycle. Implement search plus lat/lon fallback, square creation/edit, date/mode controls, attribution and responsive panels. Use public-scoped Cesium token only. Connect to actual capability/search endpoints.

Accept when search and clicking set the same state, square dimensions are metric, an antimeridian case is handled, and an unexpired current session can refresh without creating a permanent archive; confirmed settings changes purge it. UI fixtures must be visibly marked during development and excluded from claimed real results.

### E. Environmental and historical modules

Implement separate detector modules over the shared measurement engine. Water, vegetation and exposed-ground observations are quantitative; stronger interpretations require the specified baselines/context. Integrate a documented tree-cover reference with date/version/licensing; do not label general NDVI loss deforestation. Implement coastal waterline evidence with explicit water-level limitations; do not claim sediment erosion rates without the extra method.

Implement same-season annual summaries and documented Landsat sensor policies. Add an availability registry that distinguishes implemented, awaiting-validation and unavailable capabilities. A menu label is not a working detector.

Accept when every returned label has a versioned rule, required evidence and limitations, annual gaps remain visible, and changing support does not create a false trend.

### F. Weather, explanation and exports

Fetch pinned reanalysis, compute aggregates/anomalies in Python, attach spatial/temporal resolution. Send evidence JSON to Muse; validate returned claims/numbers. Build explicit map/CSV/GeoJSON/manifest download and the mandatory temporary-analysis lifecycle in document 07. No saved studies or cross-analysis image caching.

Accept when a model-invented number or causal assertion is rejected, incomplete weather stays missing, and export reproduces the displayed measurements.

### G. Integration, resource limits and evidence review

Implement the bounded worker, browser tile/texture budgets and optional source registry in document 08. Run block-size numerical-equivalence checks, long-history memory/disk monitoring, cancellation and repeated-run cleanup tests. Run the agreed real case plus a stable control and unusable input. Measure latency/cost, test phone/desktop, inspect attribution and error states, record an actual demo, and validate submission fields. Keep an honest limitations/capability report.

## Initial Muse prompt

> You are implementing Terra Shift in this workspace. Read docs/terra-shift/README.md, then the ten numbered documents. The user requires a real global globe-based environmental change application, with editable square AOIs, selected periods, satellite measurements, SAM 3.1, weather context and evidence-based explanations. Codex owns architecture, scientific contracts and review. Begin with work package A and the shared typed contracts; then package B. Do not generate the entire product in one unchecked pass. Before editing, list the files you will own and the acceptance criteria. Use official provider documentation and inspect current response metadata. Never compute scientific metrics from RGB previews, ignore scale offsets, count clouds as change, measure square degrees, invent dates/results, or label an index change as a confirmed environmental cause. Preserve the full target scope and report any unimplemented capability honestly. Do not create fake success paths, silent source switches or cosmetic SAM masks. Keep secrets server-side and do not print their values. Raw satellite inputs must be deleted after processing, and confirmed analytical-settings changes must cancel and purge the current run before fresh downloads; implement the race-safe lifecycle in document 07. After each package, report files changed, checks run, real provider outcomes, known failures, usage and the next dependency. Pause package advancement if a scientific contract is violated; fix it before adding presentation layers.

## Follow-up prompt format

For each package: goal; allowed files; API inputs/outputs; scientific invariants; completion tests; budget/time allowance; forbidden scope substitutions. Architect reviews the diff and executed checks, then issues the next package. Avoid two agents editing the same files simultaneously. Do not rely on Muse's optional parallel-workflow features without verifying availability.

The docs are instructions for implementation, not authorization to auto-submit competition forms, publish externally, contact others, or purchase additional services.
