# Experience and visual design

## Direction: a working Earth observatory

The Earth itself is the main interface. Open directly into a cinematic but usable globe, not a marketing landing page. The memorable element is the transition from planetary context to evidence at a selected site. Surround it with restrained controls that remain legible over imagery.

Audience: a person investigating environmental change who needs to choose a location, compare periods, understand results and inspect their support.

## Visual tokens

| Token | Value | Purpose |
|---|---|---|
| Space | `#07131E` | Globe canvas surroundings |
| Panel | `#F5F7F8` | Light control/evidence surfaces, readable over imagery |
| Ink | `#172B3A` | Panel text |
| Water gain | `#087EAD` | Blue change overlay |
| Water loss | `#B65A22` | Orange change overlay |
| Vegetation gain | `#27764C` | Green change overlay |

Vegetation decline can reuse orange in its own legend; unknown uses neutral hatching. Text/icon labels and patterns supplement colors. Never rely on red/green alone. Reserve high saturation for mapped changes, not decorative neon.

Typography: Source Sans 3 for interface and narrative; tabular numerals for measurements; system fallback bundled/local where possible. Use 14–16 px body text and 24–30 px result titles. No tiny all-caps telemetry or ornamental dashboard gauges. Panels use modest 8–12 px corner radii; avoid wrapping every sentence in a card.

## Desktop composition

```text
┌ Terra Shift ───────── [Search a place or coordinates…] ─── [New analysis] ┐
│                                                                        │
│ ┌ Analysis setup ───┐                         ┌ Evidence ────────────┐ │
│ │ Selected square   │                         │ Selected region     │ │
│ │ Center / side km  │      Interactive        │ Observed change     │ │
│ │ Event / History   │        Earth            │ Measurement + units │ │
│ │ Dates / season    │                         │ Actual observations │ │
│ │ Evidence layers   │    Draw / move AOI      │ Data quality        │ │
│ │ [Find imagery]    │                         │ Why this label?     │ │
│ └───────────────────┘                         └──────────────────────┘ │
│                    [Before | Swipe | After | Change]                   │
│ ───────────── Observation timeline + availability bands ────────────── │
│ Source attribution                                 [Export evidence]   │
└────────────────────────────────────────────────────────────────────────┘
```

Keep setup about 300 px wide, evidence about 340 px, and the map central. Evidence opens when a region is selected; it need not obscure the globe at entry. No invented statistics appear before analysis.

## Interaction requirements

1. **Explore:** tactile orbit, zoom and pan; subdued atmospheric rim; realistic navigation imagery. No endless automatic spinning while the user works. Render on demand when stationary where practical.
2. **Locate:** search returns disambiguated places with country/region. A selected result flies to location. Clicking the globe or entering coordinates sets the same center. A missed click on space does not create coordinates.
3. **Select area:** choose a metric square with draggable center/corners and numeric side length, or draw a custom polygon, drag its corners and edit exact vertex coordinates. Measurements exclude pixels outside the selected boundary. Show km² and estimated resolution. Search or camera motion must not silently replace a confirmed AOI.
4. **Choose time:** event windows and annual seasonal range are distinct controls. History exposes inclusive From year / To year controls and a seasonal window; 2000–2020 requests 21 yearly summaries using the default Landsat policy. Optional Sentinel detail mode is available only for supported periods from 2015 onward. Display coverage availability before expensive processing. Show requested and actual dates; date substitutions require visibility, not hidden nearest-scene selection.
5. **Run:** clear stage labels with true elapsed time and cancellation. The globe stays responsive while the worker runs. Show a cost/work estimate where calculable, not a false guarantee.
6. **Inspect:** fly toward the selected square and transition to a near-nadir analysis view. Before/after split uses the same camera and footprint; scientific imagery overlays are separate from the undated basemap. The user can return to 3D without changing the calculation.
7. **Explain:** clicking a change polygon opens the evidence drawer, highlights its source pixels, and shows SAM vs spectral layers. Display data coverage, effective resolution and source dates near the result.
8. **Compare history:** timeline shows real observation years and gaps. No interpolated fabricated images or animated intermediate disasters. Weather context occupies an expandable strip, not the main visual stage.
9. **Export:** offer an explicit download containing scene IDs, configuration, derived map, measurements and limitations. Do not create persistent share links or saved studies.
10. **Replace:** applying changed analytical settings opens the loss warning in `07-temporary-storage.md`. Keep draft edits separate so cancellation preserves the active result. Confirmed replacement purges the old run before fresh downloads.

## Environmental theme controls

The controls allow several themes at once, with a pressed state and checkmark for each selection. The evidence panel switches between selected layers without downloading imagery again. Include the user's requested themes in the product information architecture: water/flood context; vegetation/greening; forest-change evidence; exposed ground/degradation indicators; coast/terrain change. Controls must describe the measured outputs and required supporting data. A theme lacking evidence produces an explanatory state, not a generic confident summary.

The UI must not hide scientific uncertainty in a footnote. “Vegetation declined” and “desertification confirmed” are different claims. The former can be a measured result; the latter requires the additional evidence in the scientific contract.

## Failure, partial and empty states

- No imagery: “No usable observations in this window. Widen the dates or choose another period.”
- Cloud obstruction: mark unavailable pixels; show how much can be compared.
- SAM failure: preserve a labeled spectral result; disable claims of SAM-refined boundaries.
- Disagreement: striped disputed region; allow inspection and recorded correction.
- Unsupported historical comparison: state missing sensor policy/coverage; never fake a long timeline.
- Water baseline zero: area difference can exist but percentage change is unavailable.
- Weather unavailable: satellite analysis remains viewable; no invented context.
- Oversized selection: show tiled-job estimate or user-controlled coarser analysis.

## Mobile, accessibility and performance

Mobile: full-width map, search at top, collapsible bottom sheet for setup/results; timeline remains reachable. Controls ≥44 px, visible focus, keyboard alternatives for coordinate/AOI entry, screen-reader summaries, reduced-motion preference, 2D fallback if WebGL fails. Pinch/drag on the globe must not fight page scrolling inside sheets.

Use a single Cesium Viewer, destroy it on unmount, and avoid rerendering it on every React input change. Lazy-load visualization bundles; limit raster resolution sent to the browser; tile larger outputs. Keep attributions visible. Target a smooth 30+ fps during interaction on the actual demo machine, then measure rather than assume it. The photographic Earth supplies visual richness; avoid extra particle effects and glowing UI.

Design review: this layout is specific to geographic investigation. It opens on the object of study, keeps measurement controls tied to the AOI, and turns result inspection into a geographic interaction. The dark canvas is justified by the globe; light panels prevent the whole application becoming a generic dark dashboard.
