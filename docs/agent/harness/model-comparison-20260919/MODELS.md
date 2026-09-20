# Model comparison: verified configuration, 2026-09-19

This record fixes model identifiers and comparison settings before the experiment. It contains **no inference results**. The metadata requests below did not use credentials and made **0 paid inference calls**.

## Verified models

| Provider | Request model ID | Current mapped model | Context / maximum completion |
| --- | --- | --- | --- |
| DeepSeek direct | `deepseek-flash` | DeepSeek V4.1 Flash | 1M context / 384K maximum output per current pricing page |
| OpenRouter | `google/gemini-3.8-flash` | Catalog canonical slug `google/gemini-3.8-flash-20260902` | 1,048,576 context / 65,536 maximum completion |

DeepSeek's September 10 release and current API documentation explicitly map `deepseek-flash` to V4.1 Flash. There is no need to replace the working ID with the previously anticipated `deepseek-v4.1flash`. API response aliases alone do not identify an immutable weights revision; preserve the request ID, returned model, date, and provider metadata. Sources: [DeepSeek current API entry point](https://api-docs.deepseek.com/), [release/change log](https://api-docs.deepseek.com/updates/).

Gemini 3.8 Flash is present in the live public OpenRouter catalog. It supports text output, tool calling, JSON-schema structured outputs, and text/image/video/file/audio input. This comparison uses text only. Sources: [OpenRouter model page](https://openrouter.ai/google/gemini-3.8-flash), [Google model card](https://deepmind.google/models/model-cards/gemini-3-8-flash/).

## Why three arms

The earlier H1–H3 project experiments explicitly used DeepSeek with thinking disabled and a 4096-token output cap. These experiments do not establish performance with thinking enabled and do not identify the cause of an individual error.

| Arm | Chat Completions request fields | Purpose |
| --- | --- | --- |
| DeepSeek off | `model: deepseek-flash`; `thinking: {type: disabled}` | Re-measure the earlier non-thinking choice on the new fixed tasks. |
| DeepSeek high | `model: deepseek-flash`; `thinking: {type: enabled}`; `reasoning_effort: high` | Isolate the effect of enabling the same model's supported high thinking setting. |
| Gemini high | `model: google/gemini-3.8-flash`; `reasoning: {effort: high}` | Compare an alternative provider/model with explicit thinking enabled. Do not send DeepSeek's `thinking` field. |

DeepSeek currently defaults to thinking enabled/high and supports low/high/max. Its thinking mode ignores temperature, presence penalty, and frequency penalty; setting the same temperature in both requests therefore does not establish equal sampling behavior. [DeepSeek thinking documentation](https://api-docs.deepseek.com/guides/thinking_mode/)

Gemini 3.8 Flash's live catalog has `reasoning.mandatory=true`, supports **high/medium/low**, and defaults to medium. Do not send `none`, disable thinking, or label low as equivalent to off. Google's current documentation independently lists the same levels. [Google thinking documentation](https://ai.google.dev/gemini-api/docs/thinking)

The label high does not imply equal reasoning compute or equal token counts across vendors. Record actual reasoning tokens where reported, visible completion tokens, latency, finish reason, format failures, and costs. Reasoning shares the completion limit and can exhaust it before a usable answer appears. Hitting the token limit is an incomplete response, not a factual answer. Hiding reasoning with `exclude` does not disable it or remove its cost. [OpenRouter reasoning documentation](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens)

Use the same fixed task text, reference evidence, output contract, executable answer key, and grading rules for all arms. Keep the first comparison in the existing native caller to isolate model/configuration behavior from the Harness adapter. A subsequent Harness comparison must separately verify Gemini tool-call continuation and preservation of reasoning/signatures. Existing DeepSeek-adapter compatibility is not evidence that Gemini continuation is compatible.

All three arms can request `response_format: {type: json_object}` and apply the same local schema validator. For OpenRouter, `provider: {require_parameters: true}` restricts routing to endpoints that support the request parameters. The selected model and endpoint catalogs list `response_format`; the documented JSON mode is not a substitute for schema or semantic validation. A first-call transport failure must be retained rather than silently changing only one arm's settings. [OpenRouter parameters](https://openrouter.ai/docs/api/reference/parameters), [provider selection](https://openrouter.ai/docs/guides/routing/provider-selection)

## Price snapshot

USD per million tokens, checked September 19, 2026. Prices are public list prices, **not observed experiment charges**.

| Provider / tier | Uncached input | Cached input read | Output |
| --- | ---: | ---: | ---: |
| DeepSeek Flash off-peak | $0.15 | $0.003 | $0.60 |
| DeepSeek Flash peak | $0.30 | $0.006 | $1.20 |
| Gemini 3.8 Flash OpenRouter standard | $0.75 | $0.075 | $3.75 |

DeepSeek's current peak windows are Monday–Friday 01:00–04:00 and 06:00–10:00 UTC, excluding Chinese public holidays; other times, including weekends, are off-peak. Archive the start time and token/cache counters before estimating a charge. [DeepSeek prices](https://api-docs.deepseek.com/quick_start/pricing/)

The OpenRouter endpoint catalog also exposes distinct flex and priority tiers. The table above uses standard. Reasoning output has the same per-token rate as other output in the catalog. Actual provider routing/tier and usage-reported charges take precedence over this estimate; do not assume a missing cost field means free. [OpenRouter endpoints](https://openrouter.ai/api/v1/models/google/gemini-3.8-flash/endpoints)

## Public evidence snapshots

- [Selected OpenRouter model record](model-catalog-openrouter.json): UTC retrieval timestamp, full-catalog SHA-256, exact selected record, reasoning options, capabilities, and price.
- [OpenRouter endpoint records](model-catalog-openrouter-endpoints.json): UTC retrieval timestamp, available endpoint tiers and prices.
- [DeepSeek pricing page HTML](model-catalog-deepseek-pricing.html): public source page retrieved during this check.
- [DeepSeek price summary](model-catalog-deepseek.json): parsed prices, source link, and archived HTML SHA-256.

Local code evidence: `scripts/harness_correctness_experiment.py` records and applies `shared_thinking: {type: disabled}`; `app/harness_profile.py` sets thinking disabled/off; `app/harness_relay.py` currently rejects thinking-enabled requests. Any new thinking-enabled Harness experiment requires an explicit adapter change and tests. The model-comparison run itself should use its own settings and must not silently replace the production provider.
