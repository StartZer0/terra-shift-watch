# Watch interaction contract

| Capability | Canonical owner | Source of truth | Allowed variants | Verification |
| --- | --- | --- | --- | --- |
| Select/Listbox | Native HTML select | UX contract | Frequency, season, source, speed | Keyboard and option selection |
| Date | Native HTML date input in historical App | UX contract | Event endpoints | Labeled date inputs and existing contracts |
| Form | WatchApp and shared API schema | WatchArea / AnalysisRequest | Create and geometry | Validation tests and browser creation |
| Scrollbar | Global watch.css baseline | DESIGN.md | Panel gutter and narrow document flow | Desktop/mobile overflow check |
| Toast | WatchApp shared status region | UX contract | Status and error | Live region and dismissal |
| CRUD | WatchApp with Watch API/store | Watch API lifecycle | Create, pause, resume, delete | API tests, persistence, dialog cancellation |

- Create: validate name, coordinates, boundary, and at least one theme; preserve input on failure. Success returns to the selected watch and queues a real check.
- Check: queued → checking → ready/failed. Disable duplicate actions, retain the last successful evidence with its timestamp, and never manufacture a low-priority result after a provider failure.
- Forecast: separate future model values from dated observations. Missing inputs produce unknown or explicitly partial assessments. Priority is heuristic review triage, not a disaster probability.
- Pause/resume: persist enabled state. Pausing prevents later scheduled checks; an already running read may complete. Overdue enabled watches resume after backend restart.
- Satellite: one bounded subprocess, actual dated OPERA rasters and optional optical SAM comparison. Current previews expire after 24 hours; measurements remain in bounded snapshot history. Failed/empty model masks remain unknown.
- Delete: accessible native HTML dialog with initial focus on Keep, Escape cancellation, and focus restoration. Delete removes the selected watch, history, and temporary previews. Any running satellite read is terminated.
- Search: explicit Enter submission, clear control, and visible progress. Only one search may be active; clear invalidates pending results. Never use a browser-native confirm/alert/prompt.
- Canonical controls: existing AreaSelector owns geometry. Native select owns frequency options. WatchApp owns status feedback, selection, create/delete routes, and errors. WatchDetails owns feature selection. Global scrollbar styling lives in watch.css.
- Select/Listbox: native. The existing HTML select is the canonical owner for frequency, historical source, season, and playback speed; operating-system popup appearance is intentional.
- Date: native. The historical analysis page owns event dates through labeled HTML date inputs; platform calendar localization is intentional. Watch forecast dates come from provider responses and are not editable dates.
- Locale: English interface, device-locale number/time formatting; provider dates and calculations use UTC. Units are explicit.
- Accessibility: semantic buttons, labels, focus rings, text severity labels, live feedback, keyboard-operable native dialog, and reduced-motion support.
- Retention: at most 90 numeric/context snapshots per area and 12 areas by default; no credentials in browser storage or public responses. This is a local single-user application, not public authenticated hosting.
