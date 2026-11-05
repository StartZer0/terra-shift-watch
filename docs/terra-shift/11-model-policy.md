# Model policy and implementation ownership

Updated November 4, 2026 following the owner's explicit instructions.

- **Codex implements the complete application.** Muse Code authentication is optional, not a development prerequisite. Earlier work-package documents remain useful engineering contracts, but their original Muse-first authorship allocation is superseded here.
- **Runtime reasoning:** `muse-wonder-1.0`, Standard API mode, reasoning effort `max`. No automatic substitution with Spark or another provider. The default is configurable server-side; clients cannot choose arbitrary model IDs or provider URLs.
- **Runtime segmentation:** `sam-3.1`. SAM is distinct from Muse. Segmentation remains a genuine provider request with the official output parser.
- **Wonder Full:** available only in Muse Code on Power Usage / Maximum Usage subscriptions. It is not accessible through the Model API, and `max` reasoning does not turn Wonder into Wonder Full. Do not invent a `muse-wonder-full` API model identifier.
- **Hosting:** start locally. Confirm whether the owner's “Model.com” account is Modal before any cloud deployment. Neither Modal nor Baseten credentials are needed for the local implementation.
- **Budget:** Wonder API prices checked at $4 input, $0.20 cached input and $20 output per million tokens. Log actual usage; account-wide spending outside this app is not observable from its ledger. A higher-capability model does not justify unlimited prompts, contexts, retries or tool loops.
- **Evidence:** session/task records honestly identify Codex's code contribution and Meta's runtime contribution. Never imply that using the Meta SDK means Muse wrote the application.

Sources: [Meta models](https://dev.meta.ai/docs/models), [pricing](https://dev.meta.ai/docs/pricing-rate-limits). Provider access checks verified that the configured account's model catalog lists both `muse-wonder-1.0` and `sam-3.1`; successful inference is a separate integration check.
