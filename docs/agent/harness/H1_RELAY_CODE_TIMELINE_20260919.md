# H1 relay code timeline and evidence limits

Recorded on 2026-09-19 after the first H1 live run. This is an audit note, not a change to its frozen artifacts or a claim of model quality.

All timestamps below use UTC; local time is UTC+08:00.

| Event | Timestamp | Relay SHA-256 |
| --- | --- | --- |
| Frozen relay source file modification time | 2026-09-19T10:26:39.269489+00:00 | `02638f99f40ae22b30465dbfbf19b19782ab189c11320051e3e5dbcc80a18cae` |
| H1 manifest creation | 2026-09-19T10:31:55.320059+00:00 | Manifest records the same frozen hash above |
| Working-tree relay update | 2026-09-19T10:33:15.542099+00:00 | `479803f582d77302d2af1cad23b3c8a67851361dc5657624b0823c976b53be7d` |

The working-tree update changed only two areas:

1. Reject configured provider extras that override `tools`, `tool_choice`, or `parallel_tool_calls` after tool validation.
2. Include the effective merged `Endpoint.extra` options in the sanitized request audit, rather than recording only the pre-merge payload.

It did **not** change `_completion`, its finish-reason validation, tool-call field validation, model/tool generation prompts, or the SSE encoder. It therefore cannot explain H1's HTTP 200 responses being rejected by `_completion`.

The five Harness call creation times from saved call ledgers were:

| Case | Call created at | Saved status |
| --- | --- | --- |
| `canary_bad` | 2026-09-19T10:32:01.977790+00:00 | failed |
| `canary_corrected` | 2026-09-19T10:32:06.752333+00:00 | failed |
| `cpu_en_hard` | 2026-09-19T10:32:31.424883+00:00 | failed |
| `cpu_zh_hard` | 2026-09-19T10:33:04.522469+00:00 | failed |
| `transactions_zh_medium` | 2026-09-19T10:33:19.605114+00:00 | failed |

Every saved Harness request audit, including the last case after the source-file update, contains exactly `max_tokens`, `messages`, `model`, `n`, `stream`, `thinking`, and `tools`; it does not contain the configured extra `temperature`. This is consistent with the H1 process retaining the pre-update relay module in Python's module cache across phases. The first Harness phase began before the working-tree update. There is no import-time source hash in H1 evidence, so these observations are **supporting evidence, not proof of an exact loaded source revision**.

Consequently H1 must not be described as a strictly controlled comparison against the final working-tree revision. Preserve the original manifest/code snapshot and failed calls, and use a new run ID and source snapshot for any compatibility repair. All integration checks in `tests/test_harness_runner.py` use the real installed local runtime with a mocked model transport; they establish transport/tool/budget behavior, not live-provider compatibility or educational answer quality.

Evidence inspected: `docs/agent/harness-experiments/H1_20260919/manifest.json`, its `code/app/harness_relay.py`, all five `deepseek_harness__*.json` artifacts, and current `app/harness_relay.py` file metadata and diff.
