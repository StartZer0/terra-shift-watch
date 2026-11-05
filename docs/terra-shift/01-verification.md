# Verification and corrections

Checked November 4, 2026. Source support and design recommendations are distinguished below.

| Supplied claim | Finding | Implementation consequence |
|---|---|---|
| Sentinel/Landsat data are free | Open imagery is available; hosting, processing, egress and service quotas can still cost money | Use bounded Cloud Optimized GeoTIFF reads and temporary processing; do not promise free unlimited analysis |
| Choose any two dates and fetch cloud-free images | Acquisition schedules, clouds and local archive gaps prevent this guarantee | Request windows; disclose actual acquisitions and permit no usable observations |
| SAM 3.1 can segment prompted objects | Supported in official documentation; geospatial accuracy on our scenes is untested | Send consistent RGB crops, preserve geographic transforms, evaluate independently |
| NDVI/NDWI rules identify disasters | They indicate spectral/cover changes; labels require additional evidence | Separate observation from interpretation |
| Vegetation decrease plus bare ground means desertification | Unsupported from two scenes | Use vegetation decline/exposed ground; reserve desertification for a broader dryland degradation assessment |
| Vegetation loss means deforestation | Incorrect | Need tree-cover baseline, persistent loss and land-use context |
| Coastal land becomes water, therefore erosion | Incorrect | Call it waterline/land-water change unless water-level and morphology evidence support erosion |
| Median composites always help | Useful for seasonal summaries; may erase brief floods and create synthetic spectra | Use selected acquisitions for events and transparent seasonal composites for trends |
| Same sensor solves temporal comparability | Helpful but insufficient | Address season, illumination, processing baseline, atmospheric effects, registration and quality masks |
| SAM is the visual layer only | Scientifically cautious but weak model integration | Use it for object delineation, selection and explicit comparison with spectral evidence, without fabricating accuracy |
| Muse can assign a confidence percentage | An LLM's self-rating is not calibrated | Compute quality flags and sensitivity; narrative may not invent probabilities |

## Data history and availability

[USGS Landsat Collection 2](https://pubs.usgs.gov/publication/fs20213002) distinguishes Level-1 history from 1972 and global Level-2 surface products from 1982. A 20-year surface-reflectance study is possible, but crosses sensors and may encounter missing observations; Landsat 7 scan-line gaps also require explicit handling.

[NASA HLS](https://hls.gsfc.nasa.gov/hls-data/) has product lineage starting in 2013 for Landsat and 2015 for Sentinel. HLS harmonizes inputs at 30 m; it does not provide a 20-year record back from 2026. The [NASA vegetation-index description](https://science.nasa.gov/mission/landsat/hls-vegetation-indices/) explains the index family. Particular hosted catalogs can contain less history than the full mission product.

**Live metadata check:** both Earth Search and Planetary Computer catalog endpoints responded successfully. Planetary Computer currently advertises HLS L30/S30 starting in 2020, despite the longer NASA product history. Its Sentinel-2 L2A and Landsat C2 L2 collections advertise starts in 2015 and 1982. These are collection extents, not guarantees for each location. Record: `../../research/terra-shift/catalog-check-2026-11-04.json`.

[Earth Search's maintained documentation](https://github.com/Element84/earth-search/blob/main/README.md) lists collection versions and a changing v2 beta. Pin the endpoint and collection; discover available asset names instead of relying on stale tutorials. The current architecture selects Planetary Computer as the first adapter to share an access path across Sentinel and Landsat, with Earth Search as a separately tested alternative. Follow [Planetary Computer's STAC signing example](https://planetarycomputer.microsoft.com/docs/quickstarts/reading-stac-r/); an expiring signed asset URL is not a durable dataset identifier.

## Weather

[Open-Meteo historical documentation](https://open-meteo.com/en/docs/historical-weather-api) supports ERA5 from 1940 at 0.25° and ERA5-Land from 1950 at 0.1°. Kilometer equivalents are approximate and latitude-dependent. Reanalysis is a gridded reconstruction, not a weather station at every selected pixel. Pin a dataset for long histories rather than allowing automatic source changes. Recent data has a lag.

[Open-Meteo pricing](https://open-meteo.com/en/pricing) lists non-commercial free access, 10,000 daily calls and other limits. Large time/variable requests can consume more quota than one simple call; check current accounting. Preserve attribution and check commercial-use terms before a commercial deployment. Weather association cannot establish the cause of a mapped change.

## Interpretation limits supported by specialist sources

- [UNCCD guidance](https://www.unccd.int/resources/unccd-library/good-practice-guidance-sdg-indicator-1531-proportion-land-degraded-over) evaluates land degradation using land cover, productivity and soil organic carbon together. A low NDVI pair is not that assessment.
- [WRI forest methodology](https://gfr.wri.org/annual-tree-cover-loss-data-explained) distinguishes tree-cover loss from permanent deforestation.
- [ESA waterline guidance](https://knowledge-hub-gda.esa.int/eo_capability/waterlines-and-shorelines/) explains that tide and weather affect the observed waterline. [USGS DSAS](https://www.usgs.gov/software/digital-shoreline-analysis-system-version-62) measures shoreline change using transects and uncertainty.
- [JRC Global Surface Water](https://global-surface-water.appspot.com/download) provides water-history products useful for context and comparison, but an occurrence map is not ground truth for a particular flood acquisition.

## Implementation-critical details

[USGS scaling guidance](https://www.usgs.gov/faqs/how-do-i-use-a-scale-factor-landsat-level-2-science-products) gives Landsat C2 surface-reflectance scaling as DN × 0.0000275 − 0.2. Apply dataset-specific metadata exactly once. Additive offsets do not cancel in normalized differences.

[Copernicus Sentinel-2 documentation](https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Data/S2L2A.html) distinguishes band and quality-mask resolutions and warns that tile cloud percentages need not represent the selected area. Do not confuse Sentinel Hub's harmonized API values with raw values from a different catalog.

[Meta SAM prompting](https://dev.meta.ai/docs/sam/segmenting) documents concept and geometric prompts. [Client libraries](https://dev.meta.ai/docs/sam/client-libraries) handle its segmentation response format. These establish the interface, not its performance on satellite data.

[CesiumJS](https://cesium.com/learn/cesiumjs-learn/cesiumjs-quickstart/) supports geospatial globe rendering. Basemap imagery is navigation context and must never be silently treated as dated analytical imagery. [Ion tokens](https://cesium.com/learn/ion/cesium-ion-access-tokens/) have distinct public and private scopes.

## Verification status

Verified: official documentation, public catalog reachability, listed collection extents, local Node/Python availability. `muse` was not found on the current shell PATH.

Not yet verified: user model entitlements, usable imagery at the chosen site/dates, signed asset reads, SAM accuracy, end-to-end latency, deployment capacity, quantitative change results. No empirical result is claimed by this draft.
