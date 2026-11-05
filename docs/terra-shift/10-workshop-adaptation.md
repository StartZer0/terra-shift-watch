# Adaptation of Meta's multimodal agent workshop

Reviewed November 4, 2026: [meta-models/legal-agent-workshop](https://github.com/meta-models/legal-agent-workshop). Inspected README, handbook, API client, settings, verification guide, signature tool and completed Session 2 loop. This is a design review; no workshop code was run or copied into the application.

## Findings

- The [handbook](https://github.com/meta-models/legal-agent-workshop/blob/main/HANDBOOK.md) distinguishes Muse Code as the development assistant from Muse Spark as the model used by the finished application.
- The [client](https://github.com/meta-models/legal-agent-workshop/blob/main/agent/agent_kit/client.py) uses the OpenAI Python SDK with `https://api.meta.ai/v1`. The SDK name does not mean requests are sent to an OpenAI model. The configured endpoint and model determine the provider/model.
- The [completed loop](https://github.com/meta-models/legal-agent-workshop/blob/main/solutions/02_session2/agent/legal_agent/loop.py) passes tools to the model, executes a selected call, returns its result, records progress and imposes a turn limit. It uses `store=False`; that setting is not a blanket promise of no provider retention.
- The [verification guide](https://github.com/meta-models/legal-agent-workshop/blob/main/agent/VERIFICATION.md) places checks at fixed tool boundaries so the agent cannot simply skip them. Some checks involve Muse judgments; these are not independent mathematical guarantees.
- The [signature tool](https://github.com/meta-models/legal-agent-workshop/blob/main/agent/agent_kit/tools/check_signatures.py) explicitly implements a placeholder returning consistent. Its SAM helper is unused by that placeholder. Do not describe the workshop's signature path as a complete SAM implementation or proof of accuracy.
- The workshop is instruction for a particular exercise, not additional hackathon rules. It does not establish an automatic 25-point award, exclusive coding-model requirement or organizer verification procedure.

## Terra Shift adaptation

Adopt a bounded investigative controller where useful, while keeping mandatory preprocessing and measurement deterministic. The legal workshop's pedagogical instruction that the model chooses every tool does not require the model to choose whether our raster QA/scaling/area rules run.

Proposed domain tools:

| Agent tool | Purpose | Boundary |
|---|---|---|
| `inspect_available_observations` | Inspect actual scenes/dates and quality metadata | Cannot silently change confirmed area/period/source |
| `inspect_change_region` | Read stored measurements and source previews for a region | No fabricated measurement or arbitrary file access |
| `segment_region` | Request SAM on an authorized current-run crop | Enforce tile, budget, concurrency and generation limits |
| `get_weather_context` | Retrieve computed history/context | Preserve reanalysis resolution and missing-data flags |
| `record_supported_finding` | Associate a finding with metric/evidence IDs | Reject invalid references, numbers and unsupported labels |
| `request_better_evidence` | Explain what observation is missing | Applying new analytical settings goes through user confirmation/deletion |
| `submit_explanation` | Produce final structured findings and limitations | Mandatory non-bypassable output validator |

The controller can choose which ambiguous region to inspect or whether another permitted crop would help. It cannot alter formulas, override QA, write code at runtime, change processing thresholds to obtain a desired result, or award its own scientific confidence. Keep an explicit small turn/call budget; terminate repeated identical failures and report unresolved evidence. Do not add an open-ended agent to every tile/year merely to increase model usage.

Keep evidence metadata separate from model prose. Each reported area must reference a computed metric; each observation references a source scene and valid support. Unsupported interpretations remain unresolved even if a model repeatedly requests approval. Human corrections stay explicitly labeled. Held-out evaluation references are not exposed to the runtime reasoning agent or used to tune prompts after results are seen.

## Visibility and retention

A compact Analysis details panel can display actual model/tool activity: requested task, model ID, tool name, completion status, duration and evidence references. This demonstrates observed activity; it is not a claim about the model's private reasoning and does not by itself prove accuracy.

Retain traces only within the current analysis, with explicit evidence export if the user chooses. Do not copy the workshop's long-term run/document storage into Terra Shift: its lifecycle conflicts with the user's delete-on-settings-change requirement. Existing cancellation and generation checks also apply to agent tools and delayed model responses.

## Muse development instructions

Use the workshop's bounded task-and-review style: specify a small package, changed-file ownership and acceptance checks; inspect what ran before moving on. Its legal case, signature logic, sample documents and human attorney workflow are domain-specific and are not needed here. Implement the geospatial equivalents independently using the current Meta API documentation and official SAM parser.

For the hackathon, accurately describe Muse Code's development contribution, Muse Spark's runtime reasoning and SAM's actual segmentation work as separate roles. The workshop supports this distinction; the supplied official rules remain the source for judging weights.
