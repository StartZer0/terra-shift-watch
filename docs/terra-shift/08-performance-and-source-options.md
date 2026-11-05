# Performance, resource budgets and optional sources

Required by the user: include optional satellite sources and make both the web page and a laptop-hosted service responsive. This document specifies implementation requirements and initial tuning targets; it does not claim measured performance on laptops yet.

## Source options are real adapters

| Option | Role | Processing distinction |
|---|---|---|
| Landsat C2 L2 — default | Long year ranges, including 2000–2020 | 30 m surface-reflectance processing with sensor-specific policies |
| Sentinel-2 L2A — optional | More detailed optical observations from 2015 onward | 10 m RGB/selected bands; use the appropriate 20 m grid when SWIR is required |
| Sentinel-1 — optional radar | Flood/water evidence under clouds | Separate calibrated, terrain-aware SAR pipeline; not an RGB/index substitute |
| HLS — optional harmonized optical | Combined recent Landsat/Sentinel history | 30 m; actual selected catalog coverage controls available years |
| MODIS — optional regional history | Broad regional vegetation/environment indicators | Product-specific resolution, QA and composite periods; not small-site boundary detail |

All options are in the requested scope. They must have implemented/validated/coverage states in capabilities; a non-working menu option is not a delivered integration. No silent fallback between sources. User switching source is an analytical-settings change and follows the deletion confirmation.

For Sentinel-1, select a declared GRD/RTC product and discover its actual provider extent. Prefer suitable analysis-ready RTC data if available for the chosen period; otherwise implement and validate preprocessing. Match acquisition geometry/orbit/polarization, distinguish linear backscatter from dB, handle terrain shadow/layover, noise, speckle and permanent water. Show radar-derived flood evidence separately from optical evidence. SAM's role remains on appropriately dated optical images where available; do not claim SAM reliably identifies water on radar without a separate evaluation. Optical/SAR observations on different dates are not simultaneous ground truth.

HLS and MODIS need their own scale factors, QA, temporal definitions and spatial support. Native MODIS composite dates must not be presented as single-day snapshots. Source adapters expose `discover`, `read_window`, `decode_quality`, `to_physical_units`, `grid_policy` and `provenance`; they do not reuse Sentinel assumptions indiscriminately.

## Two deployment modes, one processing contract

**Hosted service, recommended:** the browser handles navigation/display; a remote Python worker handles imagery. User laptops do not download multispectral archives or execute SAM locally. Server concurrency is globally bounded, not just bounded per visitor; additional analyses queue.

**Laptop-hosted:** browser and API run locally, but raster processing executes in a separate subprocess. Keep the API responsive to cancellation. SAM and Muse still use remote APIs. Cloud processing is an optional escape for workloads exceeding the machine budget, never an undisclosed upload destination or paid automatic fallback.

A separate process prevents Python/NumPy/GDAL work from occupying the browser's event loop; it does not alone prevent system memory pressure. CPU, memory, I/O and disk budgets must also be enforced.

## Bounded pipeline

1. Search catalog metadata before downloading. Estimate candidate observations, pixel count, compressed transfer where known, uncompressed working memory, temporary storage and inference calls. Mark estimates as estimates.
2. Read required bands and AOI windows from COGs using HTTP ranges. Align reads with storage blocks. A tiny requested window can still cause full underlying blocks to be read; reject/handle servers that ignore range requests rather than silently fetching giant assets.
3. Process one spatial block and one bounded temporal batch at a time. Start at 512×512 pixels; shrink blocks to fit the temporal reducer, rather than reducing scientific resolution.
4. Apply QA and scaling, calculate indices and write temporary tiled derivatives. Close dataset handles and release source buffers promptly. Do not load every image/year into a single NumPy/xarray cube.
5. Seasonal median needs special handling: a median of batch medians is not the true median. Size a per-block temporal stack against the memory budget, shrink the block or use a correct disk-backed algorithm. Do not quietly substitute a different statistic or drop observations to meet the budget.
6. For annual history, finish and release each year's source inputs. Keep only active-run seasonal derivatives, support masks and small metrics; process multi-year slopes blockwise as well. Spatial support must remain scientifically consistent.
7. SAM receives bounded tiles of real RGB observations with preserved transforms. Bound inference concurrency. Generate SAM work when required by the declared analysis/object-inspection policy; do not claim unsegmented years were SAM-verified. Extra years/objects requested later may require fresh source reads if their previews were already released.
8. Send only viewport tiles, small region vectors and compact result JSON to the browser. Never embed a multi-year raster cube or full-resolution masks as enormous base64 strings in application state.

Example of why this matters: a 100 km square at approximately 30 m has about 11.1 million cells. Six float32 bands use roughly 267 MB for just one observation. One observation for each of 21 years is about 5.6 GB before QA, copies, multiple scenes or the globe. A 512×512 block of six float32 bands is about 6 MiB. Actual peak memory includes temporal stacks and native-library allocations, so block size alone is not a resource guarantee.

## Initial laptop-friendly profile

Assume an 8 GB RAM laptop with integrated graphics as a test target, not a guaranteed supported minimum. Tune from measured results.

| Control | Initial proposal |
|---|---|
| Active raster jobs on local host | 1 globally |
| Raster threads | 1 by default, up to 2 after checking CPU headroom; never ALL_CPUS |
| Concurrent asset reads | 2 |
| Concurrent SAM requests | 2, with backpressure |
| Spatial block | 512×512 initially, smaller when needed for exact temporal processing |
| GDAL block cache | 128 MiB |
| Warp scratch budget | 64 MiB per active warp |
| Worker RSS planning ceiling | Up to 1 GiB, lowered based on available host memory |
| Browser-owned decoded overlay/tile target | 128 MiB, managed through tile counts and known allocations |
| Analysis preview longest edge | Up to 2,048 pixels, with smaller mobile previews |
| Visible full-screen comparison dates | 2; history loads on demand |
| Temporary storage | 2 GiB initial job quota plus required host free-space reserve |
| Globe render target | 30 fps laptop-friendly; 60 fps only when measured headroom permits |

Compute a worker ceiling from the smaller of 1 GiB, 20% of physical RAM and 40% of available RAM at job start. If that leaves insufficient workspace, queue or explain the resource constraint. These are proposed admission policies, not portable operating-system hard limits. Use process RSS and host available-memory monitoring, admission estimates and a watchdog; stop/cancel the worker before prolonged swap pressure. Native allocations can overshoot a sampled limit, so leave reserve and avoid large allocations by construction.

Use `GDAL_CACHEMAX=128` in environment configuration (MB interpretation verified for the selected GDAL version). Programmatic rasterio/GDAL cache APIs can use bytes: convert explicitly. Limit warp memory separately. Disable unnecessary per-file VSI caches or set small bounded values after profiling; many open files multiply per-file caches. Bound open dataset handles. Also set supported BLAS/OpenMP thread caps to avoid nested oversubscription. Confirm settings actually take effect in the pinned runtime.

Disk quota covers raw windows, derived rasters, tile caches, masks, temporary median scratch and export archives. Stop admission before exceeding it or the host's free-space reserve. Large results may require a larger explicitly chosen quota/remote host. Do not silently lower spatial resolution, omit years or alter the estimator.

## Browser rendering requirements

- Single Cesium Viewer; load the globe bundle lazily and show usable shell controls first.
- Enable request-render mode for this non-simulation app; request frames when layers/camera/UI interactions require them. Avoid clock-driven continuous rendering when the view is unchanged.
- Cap render resolution/device pixel ratio appropriately; offer laptop-friendly/balanced/high display profiles. Lower display resolution only, without changing scientific raster resolution.
- Keep expensive shadows, building tiles, animated water and post-processing off in the laptop profile. Retain globe navigation, analytical layers and evidence interactions.
- Load only visible map tiles plus a small bounded margin. Cancel stale tile/network requests on camera/analysis changes. Limit concurrent image decoding and evict invisible textures using a bounded active-run LRU.
- Only two active comparison imagery layers plus the selected change layer. Timeline scrubbing switches/evicts frames; it does not instantiate 21 full-resolution layers.
- Rasterize dense masks for display. Simplify/vector-tile outlines by zoom for interaction; retain unsimplified measurement geometry on the worker. Display simplification must not affect reported areas.
- Keep large arrays outside React state. Use Web Workers for any necessary client-side mask/vector decoding or geometry preparation and transferable buffers when possible. Workers are not permission to download full source archives into the browser.
- Debounce metadata searches and draft-setting changes; start analysis only on explicit apply. Poll job status modestly or use event updates without flooding the main thread.
- Pause rendering and speculative loads in hidden tabs. Cancel stale work, remove imagery layers, revoke object URLs and release resources on replacement/unmount.
- Support WebGL context-loss recovery and a lighter 2D view when 3D is unavailable. The user can continue inspecting results.

Active-run memory reuse/LRU is compatible with the user's deletion requirement: it ends when the analysis is replaced/expired. No service-worker, localStorage, IndexedDB or cross-analysis imagery archive. Raw imagery is still deleted after processing; derived current-view tiles expire with the run.

## User-facing settings

Expose a small number of understandable controls:

- Source: Landsat / Sentinel-2 / Sentinel-1 / HLS / MODIS, with coverage and method details.
- Display quality: Laptop-friendly / Balanced / High. This affects rendering only and does not delete results.
- Analysis location: Local service or configured remote service, selected before a run.
- Advanced analysis resolution and resource allowance: explicit choices with consequences, never hidden automatic reductions.

Show stage, elapsed time, processed years/blocks and cancellation. A long analysis should remain usable even when it cannot be fast. Display processing estimates only after discovery; do not promise a fixed number of seconds for arbitrary areas and 20-year ranges.

## Performance verification—required before claims

Test on an actual 8 GB/integrated-graphics device if available; otherwise report tested hardware and lack of low-end validation. Browser throttling is supplementary, not proof of behavior on another GPU or memory configuration.

Scenarios: short Landsat pair; 2000–2020 annual history; larger square; Sentinel-2 detail; radar mode; rapid globe navigation; timeline scrub; 10 consecutive replacements; slow/offline provider; cancellation during native processing; simultaneous visitors on a hosted worker.

Record browser long tasks/frame-time distribution, interaction latency, worker peak RSS, host available memory/swap growth, active texture/tile estimates, disk peak, source bytes, inference calls and per-stage duration. Distinguish cached active-view navigation from first-run retrieval.

Initial acceptance targets (not achieved results): usable pan/cancel controls throughout processing; approximately 30 fps during ordinary globe navigation on the test device; no sustained application-induced swapping; bounded memory/disk within enforced policies; no monotonic retained-memory growth across repeated runs after cleanup settles. A typical cancel click should acknowledge promptly (target under 500 ms); remote provider requests may finish later, with outputs discarded. Watchdog termination and cleanup must handle stuck native workers.

Compare numerical outputs between different block sizes, concurrency settings and display profiles. Performance tuning must not change measurements beyond documented floating-point tolerances or the declared method. Record incomplete optimization rather than claim the app cannot freeze on every laptop.

## Primary references checked

- [Rasterio windowed I/O](https://rasterio.readthedocs.io/en/latest/topics/windowed-rw.html): supports processing larger-than-memory rasters; reads still follow source block layout.
- [GDAL configuration](https://gdal.org/en/stable/user/configoptions.html): cache units, thread controls and per-file cache considerations.
- [Cesium scene controls](https://cesium.com/learn/cesiumjs/ref-doc/Scene.html) and [viewer resolution](https://cesium.com/learn/cesiumjs/ref-doc/Viewer.html): explicit rendering and adjustable rendering resolution.
