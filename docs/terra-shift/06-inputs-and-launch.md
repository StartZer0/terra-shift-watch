# Inputs, access and ten-hour delivery plan

## Confirmed user requirements

- Indie Developer track; published deadline November 4, 2026 at 9 PM US Eastern, equivalent to November 5 at 6 AM in Baku.
- Develop within ten hours or less, without silently simplifying the requested product.
- Interactive 3D Earth, global search/click, user-defined square and period.
- First demonstration: a documented flood or shrinking lake; not a fixed-location-only application.
- Broad environmental themes, real SAM 3.1 use, weather history, meaningful measurements and explanations.
- Codex architects, designs, implements and reviews the application; Meta Muse Wonder handles runtime reasoning.
- **Temporary analyses only:** delete raw satellite imagery after processing; changing applied settings warns of result loss, deletes the old analysis and triggers fresh retrieval. No historical image archive or automatic saved studies.

The complete feature target is in the Muse handoff. Ten hours is the implementation budget, not a verified estimate that every classifier and historical sensor policy can be validated within it.

## Required access

| Service | Needed now? | Purpose and setup |
|---|---|---|
| Meta Model API | Yes | Local key with `sam-3.1` and a suitable Muse Wonder model enabled; confirm actual entitlements and credit balance |
| Muse Code | Optional; Codex implements the application | Install official CLI and authenticate locally; it was not found on PATH during drafting |
| Cesium ion | Recommended for the requested globe | Dedicated public token with only required read/geocode scopes and appropriate URL/asset restrictions; keep management tokens private |
| Satellite catalog | No new user credential initially expected | Public metadata checked; test signed asset reads before assuming the whole pipeline works |
| Open-Meteo | No key for eligible free use | Pin dataset, respect quota and attribution; commercial hosting may need another plan |
| Modal | Confirm provider first | Potential Python hosting; user said Model.com and reported $30. Supply account access locally only if deploying there |
| Baseten | Optional | $100 reported credit; only use if a specific hosted Meta model materially helps |
| NASA Earthdata/CDSE | Not initially required | May be needed for a different archive/product path; request only if that path is selected |

Use `local.env.example` as a field list, then configure a root `.env` locally. Do not paste secrets into chat, screenshots, prompts or source control. Meta runtime uses MODEL_API_KEY; Muse CLI can use local sign-in or META_API_KEY according to the installed version. An API account is not the same as a configured coding agent.

No key is required to review this design package. Standard API mode is the default. Do not assume a provider will erase its request logs when our local files are deleted; verify its actual retention settings before making that claim.

## Proposed first cases

**Primary: Lake Mead.** [NASA documents its changing extent](https://svs.gsfc.nasa.gov/15010/), and [USGS provides an Earthshots history](https://eros.usgs.gov/earthshots/lake-mead). Select a square over a clearly observable part of the reservoir, with same-season acquisitions after catalog checks. Label the result as within the selected square unless the whole lake is included. A published image story provides context, not automatically an independent pixel-level reference mask.

**Second: Pakistan 2022 flood.** [Copernicus EMS activation EMSR631](https://mapping.emergency.copernicus.eu/activations/EMSR631/) provides event mapping context. Inspect exact reference acquisition times and the availability of usable optical scenes. Do not compare an instantaneous optical map against a cumulative maximum flood map as though they were identical targets. Persistent cloud cover means the optical workflow may be inconclusive; SAR is a separate processing path, not a drop-in RGB replacement.

Also require a stable control, cloud/shadow case and a different user-picked AOI. Demo scenes must not determine the rules used to claim held-out performance.

## Ten-hour execution budget

| Elapsed target | Work and evidence |
|---|---|
| 0:00–0:45 | Configure access; verify actual API and satellite reads; lock contracts, benchmark framing and temporary-storage lifecycle |
| 0:45–2:15 | Muse builds ingestion/worker and scientific kernel; architect reviews scale, QA, coordinates and area tests |
| 2:15–3:30 | SAM integration, mask alignment and a real end-to-end case |
| 3:30–5:00 | Globe, search, square selection, dates and before/after evidence interactions |
| 5:00–7:00 | Remaining environmental evidence modules and seasonal history, including source policies and completeness |
| 7:00–8:00 | Weather context, constrained Muse explanation, export and destructive-setting-change confirmation |
| 8:00–9:00 | Real-case/control evaluation, cleanup/race-condition tests, responsive design and provider-failure review |
| 9:00–10:00 | Fix blocking defects, capture demo, document actual capability status and prepare submission with buffer |

These are target allocations, not guarantees. Track actual status at each checkpoint. If a dependency fails, identify the consequence immediately. Do not consume the submission buffer adding unvalidated functionality, and do not silently describe incomplete features as delivered. The user has not authorized reducing the requested scope.

## Competition presentation

Suggested narrative: select a place on Earth → draw a square → select periods → display actual observations → show measured change → click a region to inspect SAM and spectral evidence → show weather context and limitations → move the square and demonstrate the temporary-analysis warning.

The second location demonstrates generality. A no-data or disputed-evidence result demonstrates honesty. Use only real outputs for claims; clearly label replay if used for network resilience. Confirm the portal's actual video length and deliverables before recording. The supplied rules' 25% category is meaningful use of Meta tooling, not an automatic code-generation bonus.

## Remaining practical inputs

1. Local Meta access; Muse CLI authentication only if using that optional development tool.
2. A restricted Cesium public token or a separately verified alternative basemap/geocoder.
3. Confirmation of Modal versus another provider, if cloud deployment is wanted within this window.
4. Participant portal requirements that are not publicly visible, including demo length and submission artifacts.

All other routine architecture choices have proposed defaults in this package. Exact scene selection, method performance and resource costs still require real integration/evaluation, not additional brainstorming.
