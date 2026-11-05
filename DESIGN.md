---
version: alpha
colors:
  ink: "#193640"
  muted: "#586f7b"
  surface: "#f5f8f8"
  line: "#dce5e7"
  forecast: "#e1eef1"
  navy: "#102937"
  accent: "#176482"
  routine: "#3d7867"
  caution: "#8a651a"
  elevated: "#a04c16"
  high: "#a02f2d"
  unknown: "#61717b"
typography:
  sans:
    fontFamily: "Source Sans 3, sans-serif"
rounded:
  panel: "10px"
  control: "6px"
spacing:
  unit: "4px"
components:
  watchRail:
    width: "280px"
  evidencePanel:
    width: "390px"
---

## Overview
Terra Shift Watch extends the existing observatory into a monitoring desk. The Earth remains the primary spatial surface. A compact watchlist occupies the left; a readable, scrollable evidence briefing occupies the right. This is a decision-review product for environmental analysts, not an emergency dispatch console.

## Colors
Runtime owner: `apps/web/src/watch.css`. Each frontmatter color maps to the same-named `--watch-*` variable, except `line`, `surface`, and `accent`, which use explicit watch-prefixed names. The inherited historical page retains its existing tokens. Forecast shading is an encoding of forecast dates. Priority colors always accompany text labels; unknown stays separate from routine.

## Typography
Reuse the historical application's Source Sans 3 family, with tabular numbers. Area titles are 24px; finding titles 16px; readable findings 13px; metadata 11–12px. Only the empty-state introduction uses display-sized type.

## Layout
Desktop: full-height Earth, 280px watchlist, 390px evidence panel, and a restrained top navigation. At 800px and below, the map takes the top region and watchlist/detail panels move into normal document flow. Avoid clipped metrics and horizontal page scrolling. Native select ownership is intentional for check frequency. Existing AreaSelector owns exact geometry controls.

## Elevation & Depth
Panels are flat, with light borders. Shadows distinguish temporary search results, status messages, and drawing controls only. The globe supplies visual depth.

## Shapes
Panels have a 10px radius; controls use 6px. A map marker is circular. Markers communicate actual selected watch areas, not an invented global heat map.

## Components
WatchApp owns navigation, watch selection, search, form state, the shared status message, and the native accessible delete dialog. WatchDetails owns feature findings, forecast charts, sources, and satellite actions. Globe owns pins and scoped imagery overlays. AreaSelector remains the canonical location/geometry control. The shared API helper owns HTTP error decoding.

## Do's and Don'ts
Keep observed dates, forecast dates, missingness, and coverage visible. Do not invent safety probabilities or imply absence of alerts means safety. Use the same labels for creation, pause, resume, checking, and deletion. Honor reduced motion. Do not expose secrets or retain raw satellite archives.
