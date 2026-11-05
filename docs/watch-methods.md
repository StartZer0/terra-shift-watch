# Watch evidence and review rules

The executable source of truth is `services/api/watch_assessment.py`, rule version `watch-evidence-v1`. These thresholds are application heuristics for review, not calibrated environmental hazard classes.

## Temporal and spatial support

Forecast feeds are separate from observed satellite evidence. The collection requests seven forecast days, recent weather context, and up to ninety past modeled river days. The recent river percentile excludes forecast dates. Inputs retrieved more than eighteen hours ago are withheld when reassessing. The interface also flags stored checks older than eighteen hours.

Satellite freshness for the review rules is at most fourteen days. Actual acquisition dates are retained. NASA products are classified rasters; SAM consumes separate RGB optical acquisitions, which can be older. They are never represented as the same observation. Partial NASA tile coverage is disclosed; one sampled tile is not a complete mosaic of a large selection.

The equal-area grid measures clipped raster pixels in hectares. Watch inspection uses at least 60 m cells and an approximately 512-pixel maximum edge, with an overall subprocess time limit. The drawn polygon is the analytical boundary. Forecasts sample representative model grid points; they are not spatially resolved predictions within the polygon.

## Current thresholds

| Finding | Conditions |
| --- | --- |
| River support | At least thirty past modeled daily values, three forecast values, and a representative cell within 30 km |
| Elevated river review | Forecast peak exceeds recent modeled p95 by more than the larger of 1 m³/s or five percent of p95 |
| High river review | Forecast peak exceeds the larger of 1.5 × recent p95 or p95 + 2 m³/s |
| Heavy-rain Watch | Forecast daily rainfall at least 50 mm; may support a review signal when river evidence is unavailable |
| Atmospheric drying pressure | Complete seven-day precipitation minus reference ET₀: Watch at −15 mm, Elevated at −30 mm |
| Vegetation disturbance | Any ongoing confirmed OPERA vegetation disturbance supports Watch; five percent of valid sampled pixels supports Elevated |
| Forest support | Fresh OPERA, at least twenty percent observation and reference coverage, and a positive comparable dated tree-cover baseline |
| Forest disturbance | Positive mapped disturbance within the supported baseline gives Watch; more than one hectare gives Elevated |
| Ground | Heavy rain or drying pressure gives Watch; generic disturbance above five percent plus daily rain at least 30 mm gives Elevated |
| Coast support | At least three wave forecast days and a representative sea grid point within 50 km |
| Coast review | Significant-wave-height peak of at least 2 / 3 / 5 m maps to Watch / Elevated / High review priority |

Routine means no configured trigger in usable evidence. Unknown means insufficient support. The overall level is the highest supported theme level, alongside an explicit count of assessable themes. A routine water result cannot establish that every selected theme is safe.

OPERA disturbance classes 3 and 6 represent ongoing confirmed disturbance. Water classes 0, 1, and 2 supply classified support; classes 1 and 2 contribute mapped water. Cloud, shadow, and no-data are excluded. A bounded search tries up to three recent candidates before declaring insufficient classified coverage. A water-area rate requires distinct dated rasters and at least twenty percent common valid support; it is an interval measurement, not extrapolation.

The forest reference uses the Hansen 2000 tree-cover baseline with mapped losses through 2024 excluded. Later regrowth and losses are not reconstructed. Disturbance does not establish permanent deforestation or its cause.

## SAM integration

Each available dated optical image is segmented by text concept. Shared water/coast concepts avoid duplicate requests. Empty responses can receive bounded geometric guidance based on valid spectral candidate regions. Those results are labeled guided and are not independent spectral validation.

The native mask decoder validates bounds and mask encoding before geospatial area calculation. A failed or empty mask is not a measured zero. Change requires masks at two distinct dated acquisitions on common support. Model confidence and spectral overlap are not ground-truth accuracy.

## Muse interpretation

The model receives compact measured evidence, rule-based findings, limitations, and allowed evidence IDs. It cannot assign the numerical priority or calculate the displayed values. The server validates the structured response and evidence references, rejects numerical literals in the brief, and allows one correction. Failure retains numerical findings without an AI brief.

## Scheduling, storage, and failure

Only registered enabled areas are scheduled. Forecast checks are serialized; independent provider calls within a check are bounded. Daily satellite inspections share a single worker with manual inspection and avoid an active historical raster job. Failed forecast checks back off for thirty minutes. Failed satellite attempts retain a checked timestamp to prevent immediate retry loops.

SQLite retains up to ninety compact snapshots per area. Source arrays and raw optical RGB files are removed after inspection; active PNG previews expire after twenty-four hours. The local model usage ledger persists across restart and reserves estimated costs before requests. Failed requests may conservatively retain their reservation. It is not the provider account balance.

EWDS direct retrieval has queue and file-size limits. A queued or missing river-cell result remains separate from fast-feed evidence. EWDS is not a time-critical warning delivery channel. Direct Marine values are also preserved separately for inspection and export.

## Required work before operational warning use

Independent event backtesting, local gauge and coastal validation, region-specific thresholds, terrain and exposure modeling, forecast skill/false-alert assessment, alert delivery and acknowledgement, operational availability, and expert review are not supplied by the current heuristic pipeline. Use official warnings for safety decisions.

## Source documentation

- [Open-Meteo flood API](https://open-meteo.com/en/docs/flood-api)
- [Open-Meteo marine API](https://open-meteo.com/en/docs/marine-weather-api)
- [NASA OPERA product documentation](https://nasa-opera.github.io/docs/products/)
- [OPERA DSWx-HLS](https://podaac.jpl.nasa.gov/dataset/OPERA_L3_DSWX-HLS_V1)
- [Copernicus GloFAS forecast](https://ewds.climate.copernicus.eu/datasets/cems-glofas-forecast)
