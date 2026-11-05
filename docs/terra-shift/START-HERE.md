# Terra Shift — run and review

The local application is implemented. Meta and Cesium credentials are configured and have passed real access checks. Start with the workspace [README](../../README.md), launch `sh scripts/start-local.sh`, and open http://127.0.0.1:5173. See the [verification record](12-implementation-verification.md) for completed checks and remaining limits. No additional model credentials are needed for local use.

## Access checklist for a new installation

1. **Meta access configured locally.** Copy the workspace `.env.example` to `.env` only if `.env` does not already exist, then set `MODEL_API_KEY`. The account must have access to the requested SAM and Muse Wonder models. Confirm the available credit; the reported $150 is a ceiling, not a target to spend. Model identifiers in the template must be checked against actual account access.
2. **Optional Muse Code authentication.** Codex can handle installation and setup from official documentation; the owner completes interactive sign-in locally when required. Headless authentication may use `META_API_KEY`. Runtime API access and coding-agent authentication are separate configuration steps, not necessarily separate keys or purchases. A `.env` file is not automatically exported into the CLI process.
3. **A dedicated Cesium ion public token.** Set `VITE_CESIUM_ION_TOKEN` for the chosen globe assets and geocoding, with minimal scopes and appropriate URL restrictions. This token is intentionally visible in the browser; do not use an account-management token.
4. **Participant-only submission requirements.** Provide the submission-page instructions, especially demo duration, required links/files, public repository requirements and any tooling-use declaration. Existing official rules are already included in the specification.

Never paste secret values into chat, Muse prompts, source files, screenshots or commits. Configure secrets locally. Codex checks presence and makes bounded authentication checks without printing values.

## Optional access, requested only when needed

- Confirm whether “Model.com” means **Modal**. If using it for the public Python backend, authenticate its CLI locally and confirm the reported $30 credit. Local development can begin without it.
- **Baseten:** the reported $100 credit is optional. Configure a key only if a concrete deployment or hosted model requires it; it is not a prerequisite for the primary Meta integration.
- **Public hosting and repository:** provide the preferred account/project when preparing deployment. Default workflow is local development followed by a public demo. Repository creation and publishing should follow the owner's requested visibility and deployment target.
- Additional Earthdata/Copernicus credentials are requested only if the selected source adapter requires an authenticated data path. Initial public catalog access does not establish that every optional source is anonymous.

No manually downloaded satellite archive, local GPU or further design brief is needed to begin. Codex can inspect local hardware and dependencies. Tutorials are useful if they document account-specific endpoints or required hackathon behavior.

## Division of work

- **Codex:** architecture, interaction design, contracts, scientific rules, critical geospatial calculations, review, integration and validation.
- **Codex implementation:** all application code, with bounded tasks and verification. Muse Code is optional and is not required to start.
- **Muse Wonder at runtime:** evidence-based explanations and bounded investigation through approved tools.
- **SAM:** actual image segmentation with georeferenced masks, compared with independently calculated spectral evidence.

Provider checks and application integration have been performed. The original work packages remain in [05-muse-handoff.md](05-muse-handoff.md); they describe target acceptance conditions, not a claim of independent scientific validation.

## Implemented pipeline

Place search or globe click → metric square AOI → inclusive year range and season → source availability checks → bounded satellite-window retrieval → cloud/quality filtering, scaling and aligned grids → annual measurements and change candidates → SAM segmentation and agreement checks → area/rate calculations and evidence classification → historical weather context → constrained Muse explanation → globe overlays, before/after view, timeline and explicit exports.

Process data in a separate worker with enforced limits. Delete raw imagery after processing. Keep derived outputs only during the active session. Confirmed analytical-setting changes cancel and purge the old run before fresh retrieval. Display-only controls do not discard results.

Read [README.md](README.md) for the complete specification index and [06-inputs-and-launch.md](06-inputs-and-launch.md) for the ten-hour work budget. These are implementation requirements; completion and scientific reliability must be demonstrated through real runs.
