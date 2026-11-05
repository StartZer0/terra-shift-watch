# Terra Shift — implementation blueprint

Specification + implementation record · November 5, 2026 · Meta Global AI Developer Hackathon, Indie Developer track.

**Explore Earth. Measure what changed. Inspect the evidence.**

Terra Shift is a globe-based environmental change observatory. A user searches for a place or selects an area on Earth, chooses periods, and receives mapped changes, quantitative measurements, weather context, and traceable evidence. The first intended users are environmental analysts, local conservation teams, and journalists investigating a specific place.

The local application is implemented; real satellite, SAM and Muse integrations have been exercised. These documents retain the design requirements. Consult the project [README](../../README.md) and [verification record](12-implementation-verification.md) for delivered behavior and validation. Engineering integration checks do not establish scientific accuracy.

The runtime AI pipeline uses Meta SAM 3.1 for promptable segmentation and Muse Wonder for structured, evidence-linked interpretation through Meta Model API.

## Read order

Start with [START-HERE.md](START-HERE.md) for the owner access checklist and division of work. The workspace root `.env.example` contains the configuration template; keep real credentials in a local ignored `.env`.

1. [01-verification.md](01-verification.md): corrected claims, checked sources, remaining uncertainty.
2. [02-scientific-method.md](02-scientific-method.md): observable classes, processing, SAM role, metrics, evaluation.
3. [03-system-architecture.md](03-system-architecture.md): stack, contracts, services, security, deployment and budgets.
4. [04-experience-design.md](04-experience-design.md): globe experience, layouts, interaction and visual system.
5. [05-muse-handoff.md](05-muse-handoff.md): implementation tasks, boundaries, acceptance tests and starter prompt.
6. [06-inputs-and-launch.md](06-inputs-and-launch.md): credentials, user inputs, schedule and demo.
7. [07-temporary-storage.md](07-temporary-storage.md): user-required disposal, confirmation, expiry and race handling.
8. [08-performance-and-source-options.md](08-performance-and-source-options.md): optional adapters, bounded processing, laptop budgets and performance checks.
9. [09-timelapse-and-judging.md](09-timelapse-and-judging.md): playback, MP4/GIF export and verified Meta tooling rubric.
10. [10-workshop-adaptation.md](10-workshop-adaptation.md): reviewed workshop patterns, agent boundaries and verification.

## Product framing

Recommended question: **Within a user-selected area and comparable observation windows, what observable land/water/vegetation changes exceed our quality and sensitivity limits, how large are they, and what evidence supports each interpretation?**

Three possible levels:

- **Measurement — foundational layer:** observable water extent and vegetation-index change. Most defensible and quickest to validate.
- **Environmental interpretation — evidence-dependent layer:** contextual labels such as possible inundation or persistent vegetation decline, supported by baselines and multiple observations.
- **Causal attribution or forecasting — excluded:** proving drought caused land degradation, forecasting a flood, or assigning a disaster probability requires a separate validated model and study.

This is an exploratory observation product. Each empirical benchmark needs its scenes, reference labels, exclusions and acceptance criteria fixed before testing; it must be reported separately from illustrative case studies.

## Full target and delivery boundary

The user confirmed a ten-hour-or-less build, the November 4 at 9 PM Eastern deadline, global location search and user-defined square selection. Preserve the complete requested experience: globe, selectable periods, satellite analysis, water/flood context, vegetation/greening, forest-change evidence, degradation/exposed-ground indicators, coast/terrain evidence, SAM, weather, area/rate outputs and export. The first demonstration should use a documented flood or shrinking lake; other locations must be selectable through the same pipeline.

Global navigation does not guarantee that every place/date has usable observations or that every catastrophe can be diagnosed. Scientific evidence requirements are defined in the method document. If an implementation or validation is incomplete, report that explicitly. Do not silently reduce scope or claim a universal validated classifier can be guaranteed in ten hours.

Build in dependency order: provider access and measurement kernel, SAM, globe interaction, environmental/history modules, weather/explanations, integration and demo. The handoff gives concrete acceptance conditions for the full target.

## Satellite decision

Use Landsat Collection 2 Level-2 as the default for selectable year ranges, including 2000–2020. Analyze all usable years within the inclusive interval using season-matched observations; retain gaps explicitly. Sentinel-2 is an optional higher-detail source for periods from 2015 onward. Do not splice Sentinel into the later years of a Landsat history. Sensor differences within Landsat still require checks.

## Temporary analysis lifecycle

The user explicitly does not want a satellite-image archive. Delete raw downloaded imagery when its processing stage no longer needs it. Retain previews and derived outputs only for the active analysis. Applying changed settings requires confirmation, cancellation and deletion of the previous run before fresh retrieval. No automatic saved studies or cross-analysis image cache. Explicit user exports are downloads, not server archives. See [07-temporary-storage.md](07-temporary-storage.md) for races, TTLs and failure cleanup.

## What makes the project substantial

- Every result connects to its acquisition dates, pixels, model outputs and processing version.
- The user can click a changed region, inspect spectral/SAM agreement, and correct object selection.
- Unknown and cloud-obscured areas remain visible and are excluded from claims.
- Measurements are reproducible from downloadable evidence.
- A global globe serves the analysis workflow, while the detail view reveals the real spatial resolution.

These are design commitments. They are not measured advantages over competing products or a promise of a prize.

## Responsiveness requirement

Include Landsat, Sentinel-2 and Sentinel-1 source options, with HLS/MODIS as additional declared adapters. Process imagery outside the browser in a resource-bounded worker; limit both raster memory and globe tile/texture residency. Display quality changes must not alter measurement resolution. See document 08 for the proposed laptop profile and validation targets. These are implementation requirements, not measured performance claims.
