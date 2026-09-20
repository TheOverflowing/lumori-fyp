# Interpretation of this run

This is a post-hoc **common output-contract v2 smoke check**, using only the original `transactions_zh_medium` development case across all six strategies. It is not a replication of the six-case D1 pilot or an efficacy ranking. The generic runner's `RESULTS.md` title does not distinguish run purpose; consult this note and the selected-case snapshot.

Five complete assets passed validation and the unchanged external AI judge. One DeepSeek response raised `ProviderOutputError` after HTTP 200; its usage/error record survives, but its unparsed response body was not exposed by the provider and is not archived. No retry was made.

All results and limitations are discussed in [the D1 record](../../D1_RECORD_20260919.md).
