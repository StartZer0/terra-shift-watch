# Temporary storage, disposal and settings changes

This is a binding user requirement, added November 4, 2026. It overrides any earlier suggestion of saved studies, durable result archives or reusable satellite-image caches.

## Lifecycle

1. One active analysis per browser session. A run has a random ID and monotonically increasing generation/revision; do not use a shared global current-job variable across users.
2. Download only required satellite windows into a run-specific temporary directory, or process them through bounded memory buffers. Avoid entire-scene downloads when range reads suffice.
3. Once scaling, masks, indices and required RGB previews have been produced, close dataset handles and delete raw downloaded source files immediately. If SAM needs an RGB crop, retain only that crop until the call completes. No raw satellite image is archived after processing.
4. Keep derived previews, masks, per-pixel inspection layers, metrics, weather context and the provenance manifest only for the current analysis. They are temporary outputs needed to display the result, not a historical archive.
5. Applying any changed analytical setting requires a loss warning. On confirmation, invalidate the old run, cancel its work, clear its browser state and delete its remaining server artifacts. Start the new run only after deletion is acknowledged. Fresh satellite retrieval is required even if the user later returns to the previous settings.
6. Explicit user export downloads a report/evidence bundle to the user's device. This is optional and does not create a saved server study. Delete any temporary archive file after streaming. No automatic source imagery export or backup.
7. Clean abandoned runs automatically: proposed 60-minute inactivity TTL and four-hour hard lifetime, with a visible expiry warning while connected. Active-run polling alone must not extend inactivity indefinitely. Configuration can be adjusted, but automatic cleanup must exist.

## Confirmation UX

Maintain **draft settings** separately from **applied settings**. Typing a place or dragging an unconfirmed square does not silently destroy results. When applying a change, show:

> Replace this analysis?
> Changing the area, dates or analysis settings will delete the current results. Satellite imagery will be downloaded again for the new analysis. Download your report first if you want to keep it.

Actions: **Keep current results** / **Delete results and analyze**. An optional **Download report** action must finish without accidentally submitting the replacement.

Analytical changes include AOI, dates, seasonal range, source policy, resolution, selected analysis modules and measurement thresholds. Camera orbit, zoom, overlay visibility, swipe position and display opacity do not change the analysis and should not trigger deletion. Region annotations/corrections remain versioned within the active run; changing the underlying scientific inputs requires a new run.

There is no Saved studies menu. A short page refresh may recover the current unexpired session, but does not create a permanent study. Expired or deleted runs show a clear rerun action. Do not store results in localStorage or IndexedDB.

## Worker race protection

- Invalidate the generation before starting cancellation/cleanup. Every worker stage checks its cancellation token, including immediately before artifact publication and status updates.
- Long remote calls may complete after local cancellation. Their results must be discarded; they must not recreate deleted files or overwrite a newer analysis. Already-incurred provider usage cannot be undone.
- Wait for local writer/reader shutdown before deleting the directory. Use a tombstone/cancellation state and ownership checks so cleanup cannot remove a different run.
- New analysis cannot start against the previous run's directory. Repeated DELETE requests are idempotent. Failed deletion is visible as cleaning/cleanup_failed and retried; do not silently claim files were removed.
- An abandoned/failed run goes through the same disposal path. On process restart, sweep orphan temporary directories. This application does not need to resume a previous historical study after restart.

## API and access

Add `DELETE /api/analyses/{id}` to cancel and purge the session-owned run. Return cleanup status; artifact access becomes invalid immediately even while physical deletion is finishing. Add `expires_at`, `generation`, `raw_sources_deleted` and `cleanup_status` to the job contract.

Artifact routes check session ownership and generation. Use `Cache-Control: no-store` for analysis images/results; exclude them from service-worker caches. Revoke browser object URLs, remove Cesium layers, destroy textures where supported and release chart/raster references. Do not put model keys or signed source URLs into browser history.

Avoid CDN caches, object versioning, bucket backups and replicated archives for temporary analysis data. If object storage is used, delete both objects and any generated versions; a lifecycle rule is a backstop, not the primary deletion mechanism. Keep SDK/GDAL disk caches inside the run directory; release in-memory raster caches when the run ends.

Retain only non-content operational usage totals if needed for budget enforcement; omit geographic coordinates, imagery and model output from ordinary logs. An expiry/deletion tombstone may contain a random ID and timestamps for a short time, not result content.

## Model-provider boundary

Prefer documented transient/inline image inputs when supported to avoid additional uploaded files. If a provider upload is required, track its ID and use the documented deletion mechanism where available. Verify API support before promising deletion.

Our deletion policy covers application-controlled files, derived results and browser cache directives. It does not erase the public satellite archive or automatically override Meta/hosting provider retention policies. Disclose that distinction accurately. Do not claim absolute browser/device forensic erasure or zero provider retention without verification.

## Acceptance tests

1. Successful processing leaves no raw input file in the run directory.
2. Cancelling the settings dialog leaves the original result and configuration unchanged.
3. Confirming a date/AOI change deletes old outputs and causes a fresh provider read.
4. A late SAM/worker response cannot repopulate the deleted run or overwrite new results.
5. Browser disconnect, worker exception and process restart all lead to cleanup by the stated policy.
6. Old artifact URLs are denied immediately after invalidation; other sessions cannot read/delete the run.
7. TTL cleanup removes previews, rasters, masks, archive files and derived tables; normal display changes do not trigger new downloads.
8. Export is user-triggered and leaves no durable server archive.
9. Disk growth stays bounded after repeated runs; monitor actual files rather than only marking a database record deleted.
