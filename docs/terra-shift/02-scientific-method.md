# Scientific method and evaluation contract

Status: proposed exploratory methods, not a completed study. The user requests a full product within ten hours. The following safeguards are requirements for meaningful results, not optional polish. Research validation is not guaranteed to fit the implementation window.

## Observable change versus environmental interpretation

Store three separate fields: measured observation, interpretation, and evidence status. Multiple observations can coexist in one region; do not force every pixel into exactly one disaster label.

| Requested phenomenon | Directly measurable output | What is additionally required for the stronger label |
|---|---|---|
| Flooding | Newly observed surface water; gain/loss hectares | Pre-event water/seasonality baseline, event timing, independent corroboration; optical result excludes unseen flooded areas |
| Lake shrinkage | Water-to-land transition and water-area change | Same-season observations, full lake inclusion or explicit within-selection label; no inference about water volume |
| Greening | Same-season NDVI increase and persistent positive trajectory | Land-cover/use context to distinguish recovery, irrigation, crop rotation and invasive vegetation |
| Deforestation | Vegetation decrease within a corroborated tree-cover baseline; tree-cover-loss reference layer where available | Persistent loss and land-use conversion evidence before labeling deforestation |
| Desertification | Persistent vegetation decline, exposed-ground increase and climate/aridity context | Dryland context, productivity and soil/land-use evidence; do not declare desertification from two scenes |
| Soil/mountain erosion | Exposed-ground change or candidate disturbance | Terrain, event/land-use context and validated erosion method; no soil-volume/tonnage estimate from RGB differences |
| Coastal erosion | Observed waterline displacement or land-water transition | Tide/water-level normalization, stable datum, morphology and positional uncertainty |
| Other cataclysms | Only outputs supported by an implemented, versioned detector | Additional modules for snow/glaciers, burned area, landslides or ocean processes require their own validation |

All requested themes belong in the architecture. A theme can legitimately return insufficient evidence. It cannot receive a confident label just because the user selected it.

## Two temporal modes

**Event mode:** compare actual quality-screened pre/post acquisitions within explicit user windows. Default search windows are a proposal, not a physical assumption: ±14 days, with no overlap across the event boundary. Show the selected acquisition date and local valid coverage. Do not median away a brief flood. An optical acquisition after flood recession cannot establish maximum flood extent.

**History mode:** construct repeated observations in the same user-selected seasonal window each year. Start with per-date indices, then robust seasonal summaries. Use a medoid-like real observation for display/SAM when feasible; record its date and distinguish it from an index composite. A median RGB or per-band composite may never have existed on one acquisition. Do not run SAM on a synthetic composite and present its boundary as a dated observation.

For events, fixed acquisition pairs support an average interval rate, not continuous dynamics. For histories, provide annual values and a robust slope only after temporal completeness checks. A proposed minimum of five valid annual summaries is a product gate, not proof of trend significance. No significance or calibrated probability is claimed without a separate statistical design.

## Preprocessing—required before change detection

1. Validate geometry, requested dates, collection coverage and estimated processing budget. Search STAC. Preserve source item IDs, collection version, timestamps, sensor, asset band metadata and license/attribution.
2. Read only necessary COG windows: RGB, red, green, NIR, SWIR1 and optionally SWIR2 plus QA. Decode nodata/QA before scaling. Apply each asset's scale/offset exactly once; record where the values came from. Abort on ambiguous scaling instead of guessing.
3. Build pixel-level invalid masks for clouds, cirrus, cloud shadows, snow/ice, missing/saturated samples and unreliable values. Sensor QA policies are distinct. For the initial conservative Sentinel SCL policy, consider classes 4/5/6 eligible and others invalid; disclose resulting coverage loss. Do not use SCL water as independent validation of another Sentinel-derived water map. Future snow analysis requires a different QA policy.
4. Reproject both dates to the same local equal-area grid and affine transform. For a small AOI, a local Lambert azimuthal equal-area CRS is suitable. Use approximately 20 m analysis cells for Sentinel methods requiring 20 m SWIR; Landsat/HLS remain 30 m. Resample reflectance with an appropriate continuous method and QA/class masks with nearest neighbor. A 10 m RGB display does not make a 20 m water calculation a 10 m measurement.
5. Use a common valid footprint V = AOI ∩ valid_before ∩ valid_after. Report its area and percentage. Proposed pair-comparison gate: at least 80% valid AOI; below that show partial evidence without extrapolating to the entire AOI. Validate this policy on the chosen cases. Treat retained cloud/shadow uncertainty explicitly.
6. Inspect registration on stable features. A shared CRS does not prove subpixel alignment. Suppress tiny boundary changes near the positional uncertainty; do not report confident displacement below the effective resolution/registration error.
7. Keep scientific rasters separate from display stretching, only in the active run’s temporary storage; purge raw source files as soon as derivatives are ready. Use the same RGB band order, stretch and gamma across periods for SAM/display. Never compute indices from PNG previews, globe screenshots, JPEG basemaps or colorized maps.

## Indices and rules

Compute ratios only where the denominator is safely nonzero. Preserve invalid values as nodata, not zero. Store formulas, bands and units in result provenance.

- NDVI = (NIR − red) / (NIR + red).
- NDWI_McFeeters = (green − NIR) / (green + NIR), for open-water evidence.
- MNDWI = (green − SWIR1) / (green + SWIR1), another water indicator.
- NDMI = (NIR − SWIR1) / (NIR + SWIR1), primarily vegetation moisture evidence; not direct soil moisture.
- BSI = ((SWIR1 + red) − (NIR + blue)) / ((SWIR1 + red) + (NIR + blue)), exposed-ground evidence, with urban/rock confounds.
- SAVI = 1.5 × (NIR − red) / (NIR + red + 0.5), using surface reflectance and a fixed L=0.5 as an explicitly chosen heuristic.

Avoid the ambiguous label NDWI without a formula. Soil-adjusted indices can help sparse vegetation but do not establish desertification. Additional indices should be added only when their interpretation and validation are defined.

**Initial configurable water baseline:** MNDWI > 0 on valid pixels is a development heuristic, not a universally calibrated classifier. Test local alternatives on development scenes and freeze the policy before held-out evaluation. Evaluate sensitivity at threshold ±0.05 as an exploratory diagnostic, not a confidence interval. Built surfaces, snow, terrain shadow, turbid/shallow water and emergent vegetation need special scrutiny.

**Vegetation:** publish continuous ΔNDVI before categorical labels. A configurable exploratory |ΔNDVI| ≥ 0.1 can flag candidate regions but must be described as a chosen threshold and tested against seasonality/stable controls. Use the same support for each date. Water-to-land transitions must not be mistaken for ordinary vegetation browning. Forest-specific claims require the forest baseline; NDVI alone cannot distinguish forest from crops.

**Multi-year indicators:** use same-season yearly summaries on a fixed cohort of adequately observed pixels; never trend annual means over changing cloud footprints without disclosing/controlling the support. Record usable year count and missing years. Theil–Sen slope is descriptive; do not manufacture p-values from spatially dependent pixels. Show sensitivity to season/threshold choices and mask persistence separately from a two-date comparison.

## SAM 3.1 has a substantive, testable role

SAM receives true-color renderings of actual, georeferenced optical observations. It is not assumed to ingest arbitrary multispectral tensors or understand georeferencing.

1. Spectral evidence proposes candidate objects/regions. A user may also click an object.
2. Use a short concept prompt such as water, or geometric prompts derived from a candidate interior point/box. Follow the current API's supported prompt forms; do not send conflicting forms in one call.
3. Tile large AOIs at bounded image dimensions, preserving tile offsets, overlap and the exact raster-to-image mapping. Validate model limits before fixing defaults. Discard/merge duplicate overlap results consistently.
4. Parse output with the official client. Invert any image resizing and map masks onto the analysis grid. Clip to valid support. Keep original SAM geometry, spectral masks, transformed geometry and user edits distinct.
5. For water, store spectral/SAM agreement, disagreement and each method's area. Agreement is not ground-truth correctness. Conservative corroborated pixels are their intersection; disputed pixels are explicit, not silently discarded or filled.
6. The selected SAM object scopes an object-level measurement and before/after inspection. If SAM fails, return an explicit spectral-only result and explain that object delineation is unavailable. Do not depict a threshold mask as SAM output.
7. Compare against independent reference annotations and the spectral-only baseline. Claim improved accuracy only if held-out results support it. SAM can still provide useful interactive object selection without beating the baseline globally.

Never advertise sharp SAM edges as finer satellite resolution. Index/SAM disagreement is not a statistically valid uncertainty interval.

## Quantities, rates and geographic correctness

For common valid area V and classified water masks W0/W1:

- A0 = area(W0 ∩ V); A1 = area(W1 ∩ V).
- Gross gain = area((W1 minus W0) ∩ V).
- Gross loss = area((W0 minus W1) ∩ V).
- Net = gain − loss = A1 − A0.
- Relative change = net / A0 × 100, only if A0 is nonzero and sufficient; otherwise null with reason.
- Pair rate = net / actual elapsed days; an annualized equivalent may be shown only as a labeled arithmetic conversion, not a forecast.

Use equal-area raster cell areas, or geodesic polygon areas for exported geometry; never square degrees or screen pixels. Report area units and appropriate rounding. Label area as within selected square unless the entire object is observed. A partial coast/lake square cannot establish total lake shrinkage or global sea-level change.

For seasonal windows report interval boundaries and representative timing; avoid precise daily rate claims on broad composites. Rate units differ: hectares/year for area, NDVI units/year for greenness, and meters/year for independently supported shoreline transects.

## Weather context

Use a pinned ERA5 dataset initially, with precipitation and temperature summaries for matching periods and a fixed same-season climatology, proposed 1991–2020. Check completeness, grid-cell coordinates, unit conversions and the provider's recent-data lag. Large selections need multiple cells or an explicitly labeled representative cell. Weather resolution is separate from satellite resolution.

Compute anomalies in code. Define seasonal totals/means and baseline years explicitly. Do not turn a precipitation anomaly into a standardized drought index without implementing that index properly. Present temporal coincidence as context; do not let Muse infer causation from two dates or self-assign confidence.

## Evaluation proposal before model execution

Recommended first case: a well-documented shrinking reservoir such as Lake Mead, or a documented flood with an independent reference and adequate optical coverage. Final scene dates/bounds remain to be selected from catalog metadata. Add a stable nearby control and a difficult cloud/shadow example. No presumed numerical result is specified.

Primary benchmark question: on fixed held-out water scenes, does the proposed SAM-assisted workflow produce useful object delineation without worsening water-change measurements beyond a pre-agreed tolerance relative to spectral-only output?

Null: no practical improvement or degradation. Alternative: improved delineation/interaction with acceptable area error. Define the tolerance from reference quality and intended use before looking at outputs; do not select it after observing failures.

Separate development and held-out sites/dates. Use independently traced masks or temporally matched authoritative event maps. JRC annual/occurrence layers are contextual references and may share source imagery; record that dependence. Do not tune on the final evaluation masks.

Report water precision/recall/IoU, signed/absolute area error, changed-region error, valid support, manual edits, runtime and cost. Include unchanged and unusable scenes. A few scenes support a demonstration, not global accuracy claims.

Core software tests use synthetic geometry and known arrays: scale/offset, nodata masking, band alignment, transform inversion, pixel areas, gain/loss accounting, zero-baseline handling, date arithmetic, common support, antimeridian geometry, invalid AI statements and missing-data states. These tests are implementation checks, not scientific validation.
