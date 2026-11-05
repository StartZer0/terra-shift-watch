# Time-lapse and Meta tooling assessment

## Time-lapse feature

Include an in-app Play/Pause timeline and explicit MP4/GIF export for the active analysis. For an inclusive 2000–2020 selection, use one representative same-season image per available year, with the actual observation date shown. Annual scientific composites may be an alternative view, clearly identified as composites rather than single-date photographs.

Controls: play/pause, scrub, speed, loop, RGB versus selected change overlay, and export. Use the existing selected AOI and source policy. Keep geographic extent, output grid, north orientation and display stretch consistent across frames. Freeze the camera for comparison; a cinematic globe fly-in can be separate from the evidence sequence.

Do not interpolate invented satellite observations or use generative frame morphing. Missing years appear as explicitly marked gaps/placeholder cards. Default playback can allocate equal time per selected year, including gaps; if unusable years are skipped, display dates and disclose that spacing is not uniform. A crossfade, if offered, is a presentation transition and never an observed intermediate condition. Prefer direct transitions for the evidence view.

Include the selected area, date/season, source, spatial resolution, attribution and meaningful missing-data indication. Overlay metrics must match the displayed observation/support; do not place an annual composite's measurement onto a single-scene frame without labeling the distinction. Preserve cloud masks. Do not animate mixed sensors as though changes in color balance were physical changes.

## Bounded implementation

- Reuse only the current run's derived display frames; no additional Meta calls are necessary just to animate already-produced results.
- Generate bounded previews while processing each year. Store compressed frames temporarily with the run, not all decoded frames in browser memory.
- Browser preloads the current and next frame and optionally one previous frame within its budget. Evict old decoded frames/textures. Pause in hidden tabs and cancel fetches on replacement.
- Preferred export: a separate bounded FFmpeg subprocess on the configured processing host, reading temporary frames sequentially. Use approximately 720p initially; offer higher export resolution explicitly subject to resource limits. One export at a time, bounded codec/filter threads, timeout and cancellation. Do not read the full raw video sequence into RAM.
- MP4 is the recommended default for photographic imagery; GIF is an optional smaller-dimension export with limited palette fidelity. Detect available FFmpeg encoders and produce compatible pixel formats/container output rather than assuming every installation has the same codecs. A short sequence of annual frames can hold each observation for a readable duration; export fps does not imply additional satellite measurements.
- Do not ship a large browser FFmpeg/WASM dependency merely to encode. If client encoding is later desired, feature-detect WebCodecs, supported codecs and muxing support, and bound its queue. Browser support is not uniform.
- Temporary export files are covered by the job disk quota. Delete an export after download or a short explicit expiry if abandoned. Only a user-requested downloaded copy persists on the user's device.
- Settings confirmation cancels playback and any encoding subprocess, invalidates that run's generation, and deletes derived frames plus exports. Late encoder callbacks must not recreate deleted outputs. Export captures an immutable run version so its frames, dates and metrics cannot mix with a new analysis.

Acceptance: every frame aligns spatially; year/date labels are correct; gaps remain evident; export plays in tested target browsers; animation stays responsive during processing; cancellation and repeated exports do not grow retained memory/disk; no raw imagery remains archived. Record actual export duration/file size on the test hardware rather than promise fixed performance.

Primary implementation references: [FFmpeg CLI](https://ffmpeg.org/ffmpeg.html), [FFmpeg filters](https://ffmpeg.org/ffmpeg-filters.html), [WebCodecs](https://www.w3.org/TR/webcodecs/). These describe mechanisms; performance remains to be measured.

## Judging clarification

Rechecked the supplied `Hackathon Terms & Conditions (“Official Rules”) and Event Waiver.pdf`, page 2, on November 4, 2026. The rubric assigns Impact 30%, Use of Meta AI Tooling 25%, Technical Depth & Execution 20%, and Demo 25%.

The Meta tooling category considers creativity, depth beyond basic integration and unexpected capabilities. This is a weighted part of judging, not an automatic extra 25 points for calling Muse or using a specific host. The supplied rules do not state that all code must be written by Muse, or specify a penalty for using a different coding assistant. The supplied kickoff file contains only closing remarks and does not substantiate a separate bonus. Later participant-only instructions could add detail; none has been provided or verified here.

The [official event page](https://cerebralvalley.ai/e/meta-ai-developer-hackathon) lists Meta models, open weights and Muse Code. It does not establish an exclusive Muse coding requirement. Do not promise a judge's exact score or claim that a single API integration earns the full category.

Recommended project evidence:

1. SAM 3.1 performs genuine region delineation/interactive selection linked to geographic measurements, with limitations and disagreements visible.
2. Muse Wonder explains stored measurements and context through a validated evidence contract.
3. Muse Code contributes to implementation, with honest task/change records; Codex designs, reviews and may write critical parts.
4. The demo shows what these components actually do, not merely their logos.

Using another assistant for code is not a stated violation in the materials reviewed. It cannot be guaranteed to have zero influence on subjective judging; the defensible strategy is substantive, demonstrated Meta use rather than unsupported claims about bonus points. Hosted Meta APIs are the straightforward implementation choice here, but meaningful use of permitted Meta open-weight models is also described by the event.
