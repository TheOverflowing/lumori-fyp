"""Report R6 query-rewrite ablations without changing application configuration.

Input: dataset.json, rewrites.json, components.json, selection-lock.json,
calls.json and {dev,test}-per-query.json. All four arms must contain the same
(query_id, mode) pairs within each split. Failures remain in every denominator.
"""

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
import random
import statistics


ARMS = ("canonical", "original", "rewritten", "dual")
ELIGIBLE_ARMS = ("original", "rewritten", "dual")
QUALITY_METRICS = ("budget_hit", "top5_hit", "mrr5", "candidate_hit20")
MEAN_FIELDS = QUALITY_METRICS + (
    "context_tokens", "rewrite_ms", "query_embedding_ms", "rerank_ms",
    "ranking_ms", "stage_sum_estimate_ms",
)
BOOTSTRAP_SEED = 20260919
BOOTSTRAP_SAMPLES = 2000


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def numeric(value):
    return isinstance(value, (int, float)) and math.isfinite(value)


def percentile(values, percent):
    """Linear percentile, including small samples; absent observations are unknown."""
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * percent / 100
    low = math.floor(position)
    high = math.ceil(position)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def group_matches(row, group):
    if group in (None, "all"):
        return True
    if group.startswith("mode:"):
        return row["mode"] == group.split(":", 1)[1]
    if group.startswith("language:"):
        return row["language"] == group.split(":", 1)[1]
    return row["mode"] + ":" + row["language"] == group


def indexed_arm(rows, arm, group=None):
    result = {}
    for row in rows:
        if row["arm"] != arm or not group_matches(row, group):
            continue
        key = (row["query_id"], row["mode"])
        if key in result:
            raise ValueError(f"Duplicate paired scenario for {arm}: {key}")
        result[key] = row
    return result


def paired_rows(rows, arm, baseline="original", group=None):
    base = indexed_arm(rows, baseline, group)
    candidate = indexed_arm(rows, arm, group)
    if not base or set(base) != set(candidate):
        missing = sorted(set(base) - set(candidate))
        extra = sorted(set(candidate) - set(base))
        raise ValueError(f"Incomplete pairing {arm} vs {baseline} ({group}): missing={missing}, extra={extra}")
    pairs = []
    for key in sorted(base):
        before, after = base[key], candidate[key]
        for field in ("family_id", "language", "mode"):
            if before[field] != after[field]:
                raise ValueError(f"Paired metadata mismatch for {key}: {field}")
        pairs.append((before, after))
    return pairs


def interval(rows, component_map, arm, metric, group=None, baseline="original"):
    """Source-component paired bootstrap of a scenario-weighted mean difference.

    Draw components with replacement and retain *all* bilingual/mode scenarios
    in each drawn component. Repeated scenarios do not create independent units.
    """
    grouped = defaultdict(list)
    for before, after in paired_rows(rows, arm, baseline, group):
        family = after["family_id"]
        if family not in component_map:
            raise ValueError(f"Missing source component for family {family}")
        if not numeric(before.get(metric)) or not numeric(after.get(metric)):
            raise ValueError(f"Missing/non-finite paired metric {metric}: {after['query_id']}")
        grouped[str(component_map[family])].append(after[metric] - before[metric])
    values = [grouped[key] for key in sorted(grouped)]
    sums = [math.fsum(group) for group in values]
    counts = [len(group) for group in values]
    rng = random.Random(BOOTSTRAP_SEED)
    estimates = []
    for _ in range(BOOTSTRAP_SAMPLES):
        draws = [rng.randrange(len(values)) for _ in values]
        estimates.append(math.fsum(sums[i] for i in draws) / sum(counts[i] for i in draws))
    return {
        "baseline": baseline, "arm": arm, "metric": metric,
        "difference": math.fsum(sums) / sum(counts),
        "ci95": [percentile(estimates, 2.5), percentile(estimates, 97.5)],
        "clusters": len(values), "paired_scenarios": sum(counts),
        "sampling_unit": "source_connected_component",
        "estimand": "scenario_weighted_mean_paired_difference",
        "seed": BOOTSTRAP_SEED, "samples": BOOTSTRAP_SAMPLES,
    }


def all_groups(rows):
    return ["all"] + ["mode:" + v for v in sorted({r["mode"] for r in rows})] + [
        "language:" + v for v in sorted({r["language"] for r in rows})
    ] + sorted({r["mode"] + ":" + r["language"] for r in rows})


def validate_rows(rows, split):
    if {r["arm"] for r in rows} != set(ARMS):
        raise ValueError(f"{split} requires exactly four arms: {ARMS}")
    for arm in ARMS:
        paired_rows(rows, arm, "original")
    for row in rows:
        if row.get("split", split) != split:
            raise ValueError(f"Wrong split in {row['query_id']}")
        if row["status"] not in ("succeeded", "failed"):
            raise ValueError(f"Unknown status in {row['query_id']}: {row['status']}")
        if row["mode"] not in ("mixed", "cross") or row["language"] not in ("en", "zh"):
            raise ValueError(f"Unknown mode/language in {row['query_id']}")
        for metric in ("budget_hit", "mrr5", "candidate_hit20"):
            if not numeric(row.get(metric)) or not 0 <= row[metric] <= 1:
                raise ValueError(f"Invalid required metric {metric} in {row['query_id']}")
        if row["status"] == "failed" and (row["budget_hit"] != 0 or row["mrr5"] != 0):
            raise ValueError("Failed scenarios must explicitly score zero final hit and MRR; do not omit them")


def summarize(rows):
    result = []
    for group in all_groups(rows):
        for arm in ARMS:
            subset = [r for r in rows if r["arm"] == arm and group_matches(r, group)]
            summary = {"arm": arm, "group": group, "rows": len(subset),
                       "failed": sum(r["status"] != "succeeded" for r in subset),
                       "rewrite_fallbacks": sum(bool(r.get("rewrite_fallback")) for r in subset)}
            for field in MEAN_FIELDS:
                known = [float(r[field]) for r in subset if numeric(r.get(field))]
                summary[field] = statistics.mean(known) if known else None
                summary[field + "_missing"] = len(subset) - len(known)
            result.append(summary)
    return result


def select_on_dev(rows):
    """Only dev is accepted by the caller; ties retain original before rewritten."""
    summaries = {r["arm"]: r for r in summarize(rows) if r["group"] == "all"}
    return max(ELIGIBLE_ARMS, key=lambda arm: (
        summaries[arm]["budget_hit"], summaries[arm]["mrr5"], -ELIGIBLE_ARMS.index(arm),
    ))


def metering(calls):
    result = {}
    records = list(calls.values()) if isinstance(calls, dict) else list(calls)
    for capability in sorted({r.get("capability", "unreported") for r in records}):
        subset = [r for r in records if r.get("capability", "unreported") == capability]
        usages = [r.get("usage") if isinstance(r.get("usage"), dict) else {} for r in subset]
        costs = [u["cost"] for u in usages if numeric(u.get("cost")) and not isinstance(u["cost"], bool)]
        durations = [r["duration_ms"] for r in subset if numeric(r.get("duration_ms"))]
        result[capability] = {
            "attempts": len(subset), "failures": sum(r.get("status") != "succeeded" for r in subset),
            "known_cost": math.fsum(costs) if costs else None,
            "cost_reported_count": len(costs), "missing_cost_count": len(subset) - len(costs),
            "p50_ms": percentile(durations, 50), "p95_ms": percentile(durations, 95),
            "missing_duration_count": len(subset) - len(durations),
            "returned_models": dict(Counter(r.get("model") or "unreported" for r in subset)),
        }
        for label, names in (("prompt_tokens", ("prompt_tokens", "input_tokens")),
                             ("completion_tokens", ("completion_tokens", "output_tokens")),
                             ("total_tokens", ("total_tokens",))):
            values = [next((u[n] for n in names if numeric(u.get(n))), None) for u in usages]
            known = [v for v in values if v is not None]
            result[capability][label + "_known_sum"] = math.fsum(known) if known else None
            result[capability][label + "_missing_count"] = len(values) - len(known)
    return result


def csv_rows(path, rows):
    if not rows:
        raise ValueError(f"Refusing to emit an empty evidence table: {path}")
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with Path(path).open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def rewrite_text(record):
    result = record.get("result")
    return result.get("query", "") if isinstance(result, dict) else ""


def attribution(rows):
    groups = defaultdict(list)
    for arm in ("rewritten", "dual"):
        for before, after in paired_rows(rows, arm):
            succeeded_before = before["status"] == "succeeded"
            succeeded_after = after["status"] == "succeeded"
            state = ("both_succeeded" if succeeded_before and succeeded_after else
                     "original_failed" if succeeded_after else
                     "candidate_failed" if succeeded_before else "both_failed")
            for group in ("all", "mode:" + after["mode"], "language:" + after["language"],
                          after["mode"] + ":" + after["language"]):
                groups[arm, group, state].append(after["budget_hit"] - before["budget_hit"])
    return {"interpretation": "事后描述性分解；不替代保留失败的主分析，双方成功子集不构成新的随机对照或因果估计。",
            "rows": [{"arm": key[0], "group": key[1], "paired_status": key[2], "rows": len(deltas),
                      "net_hit_change": math.fsum(deltas), "gains": sum(v > 0 for v in deltas),
                      "losses": sum(v < 0 for v in deltas)} for key, deltas in sorted(groups.items())]}


def formatted(value, style="number"):
    if value is None:
        return "未报告"
    return f"{value:.2%}" if style == "percent" else f"{value:.4f}" if style == "metric" else f"{value:.1f}"


def report(run):
    run = Path(run)
    dataset = load(run / "dataset.json")
    queries = {q["id"]: q for q in dataset["queries"]}
    rewrites = load(run / "rewrites.json")
    components = load(run / "components.json")
    lock = load(run / "selection-lock.json")
    rows = {split: load(run / f"{split}-per-query.json") for split in ("dev", "test")}
    for split, split_rows in rows.items():
        validate_rows(split_rows, split)
        observed_ids = {r["query_id"] for r in split_rows}
        expected_ids = {q["id"] for q in dataset["queries"] if q["split"] == split}
        if observed_ids != expected_ids:
            raise ValueError(f"Dataset/scenario query mismatch in {split}")
        expected_scenarios = {(query_id, mode) for query_id in expected_ids for mode in ("mixed", "cross")}
        if set(indexed_arm(split_rows, "original")) != expected_scenarios:
            raise ValueError(f"Each dataset query requires both mixed and cross scenarios in {split}")
        for row in split_rows:
            query = queries[row["query_id"]]
            if row["family_id"] != query["family_id"] or row["language"] != query["language"]:
                raise ValueError(f"Dataset/scenario metadata mismatch in {row['query_id']}")
    winner = select_on_dev(rows["dev"])
    if lock.get("basis") != "dev_only" or lock.get("selected_arm") != winner:
        raise ValueError(f"Selection lock disagrees with dev-only selection: expected {winner}")
    summaries = {split: summarize(values) for split, values in rows.items()}
    comparisons = (("original", "canonical"), ("rewritten", "original"), ("dual", "original"))
    intervals = {}
    for arm, baseline in comparisons:
        key = arm + "_minus_" + baseline
        intervals[key] = {group: {metric: interval(rows["test"], components["test"], arm, metric, group, baseline)
                                 for metric in ("budget_hit", "mrr5", "candidate_hit20")}
                          for group in all_groups(rows["test"])}
    changes = []
    for arm, baseline in comparisons:
        for before, after in paired_rows(rows["test"], arm, baseline):
            query = queries[after["query_id"]]
            rewrite = rewrites.get(query["id"], {})
            result = rewrite.get("result") if isinstance(rewrite.get("result"), dict) else {}
            changes.append({
                "comparison": arm + "_minus_" + baseline, "arm": arm, "baseline": baseline,
                "query_id": query["id"], "family_id": query["family_id"],
                "source_component": components["test"][query["family_id"]],
                "canonical_query": query["text"], "colloquial_query": query["colloquial_text"],
                "rewritten_query": rewrite_text(rewrite), "language": query["language"], "mode": after["mode"],
                "baseline_hit": before["budget_hit"], "arm_hit": after["budget_hit"],
                "delta_hit": after["budget_hit"] - before["budget_hit"],
                "delta_mrr5": after["mrr5"] - before["mrr5"],
                "delta_candidate_hit20": after["candidate_hit20"] - before["candidate_hit20"],
                "baseline_status": before["status"], "arm_status": after["status"],
                "rewrite_status": rewrite.get("status", "unreported"),
                "needs_clarification": result.get("needs_clarification", "unreported"),
                "rewrite_fallback": after.get("rewrite_fallback", False),
            })
    calls = metering(load(run / "calls.json"))
    inputs = ["dataset.json", "rewrites.json", "components.json", "selection-lock.json", "calls.json",
              "dev-per-query.json", "test-per-query.json"]
    decision = {
        "dev_selected": winner, "selection_basis": "dev_only",
        "selection_rule": "max dev budget_hit, then dev mrr5, exact tie original > rewritten > dual; canonical excluded",
        "selection_lock_verified": True,
        "production_action": "retain_current_configuration_no_automatic_deployment",
        "interpretation": "旧 R5 来源上的合成口语扰动探索；不是全新保留来源、真实用户日志或本科课程人工金标。",
        "test_intervals": intervals, "metering": calls,
        "test_hit_changes": {arm + "_minus_" + baseline: dict(Counter(
            "better" if c["delta_hit"] > 0 else "worse" if c["delta_hit"] < 0 else "same"
            for c in changes if c["comparison"] == arm + "_minus_" + baseline)) for arm, baseline in comparisons},
        "input_sha256": {name: hashlib.sha256((run / name).read_bytes()).hexdigest() for name in inputs},
    }
    for split in rows:
        save(run / f"{split}-report-summary.json", summaries[split])
        csv_rows(run / f"{split}-metrics.csv", summaries[split])
    save(run / "decision.json", decision)
    csv_rows(run / "test-changes.csv", changes)
    save(run / "test-failure-attribution.json", attribution(rows["test"]))
    families = len({q["family_id"] for q in queries.values()})
    lines = ["# R6：口语输入与检索查询改写对照实验", "",
             f"开发集按预算 Hit、MRR@5、平局优先 original 的规则锁定 **{winner}**。canonical 只作参照，不参加选择。保留集完整展示四组，不据此重新选冠军；没有修改应用默认配置。", "",
             "## 研究问题与证据边界", "",
             "本轮分别检验：合成口语输入相对规范问题损失多少；同语种改写能否改善口语输入；保留原文与改写两路是否更稳健。", "",
             f"数据共 {families} 个双语 family、{len(queries)} 条查询，来源沿用旧 R5 的公开 QA 原文与相关性映射。口语表达为人工智能辅助构造的扰动，不是真实用户日志，也不是新增教师标注。本轮设计规模为 20 family / 40 query；结果规模以这里读取的归档数据为准。", "",
             "dev/test 在本轮按冻结分组分开，但旧来源此前已被使用；因此只能称本轮保留部分，不能称从未见过的课程测试集。原问题的相关性映射移用于口语变体依赖语义保持假设，需要另行核验歧义和概念增删。", "",
             "## 控制变量与指标", "",
             "canonical 使用规范问题完成检索及重排，是整体参照。original / rewritten / dual 三臂重排均固定使用口语原文，只改变首阶段候选召回查询；dual 合并去重后仍最多 20 个候选。共同采用相同文档向量、重排器、Top5 与 1024 个 Qwen source token 预算。rewrite 不应看到相关答案或 gold 文档。", "",
             "预算 Hit 表示最终预算内至少命中一段相关证据；它不是覆盖全部相关段落的 Recall。MRR@5 为前五个结果中首个相关结果排名的倒数；重排前 Hit@20 衡量候选覆盖。失败场景的最终 Hit / MRR 为零，保留在分母；候选覆盖仍可记录失败前已经取得的结果。", "",
             "改写失败或请求澄清时的回退另外记录。阶段耗时相加只用于估计本实验查询成本，不是含服务排队的在线端到端延迟。相同缓存调用可以被多场景复用，实际调用量不能用场景数代替。", ""]
    for split in ("dev", "test"):
        split_queries = [q for q in queries.values() if q["split"] == split]
        lines += ["## " + ("开发集（选择策略）" if split == "dev" else "保留部分（不重新选择）"), "",
                  f"{len({q['family_id'] for q in split_queries})} family / {len(split_queries)} query；每条查询包含 mixed 与 cross 场景。", "",
                  "| 策略 | 场景 | 失败 | 回退 | 预算 Hit | MRR@5 | 候选 Hit@20 | token | 阶段耗时估计 ms |",
                  "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for value in summaries[split]:
            if value["group"] == "all":
                lines.append(f"| {value['arm']} | {value['rows']} | {value['failed']} | {value['rewrite_fallbacks']} | {formatted(value['budget_hit'], 'percent')} | {formatted(value['mrr5'], 'metric')} | {formatted(value['candidate_hit20'], 'percent')} | {formatted(value['context_tokens'])} | {formatted(value['stage_sum_estimate_ms'])} |")
        lines += [""]
    labels = {"all": "全部", "mode:mixed": "混合语料", "mode:cross": "跨语言语料",
              "language:en": "全部英文查询", "language:zh": "全部中文查询",
              "cross:en": "英文查中文", "cross:zh": "中文查英文", "mixed:en": "英文查混合语料", "mixed:zh": "中文查混合语料"}
    lines += ["## 按语言和场景分解", "", "| 场景 | 策略 | n | 失败 | 预算 Hit | MRR@5 | 候选 Hit@20 |",
              "|---|---|---:|---:|---:|---:|---:|"]
    for value in summaries["test"]:
        if value["group"] != "all":
            lines.append(f"| {labels[value['group']]} | {value['arm']} | {value['rows']} | {value['failed']} | {formatted(value['budget_hit'], 'percent')} | {formatted(value['mrr5'], 'metric')} | {formatted(value['candidate_hit20'], 'percent')} |")
    lines += ["", "## 配对增损与不确定性", "",
              "负的 original − canonical 差值表示规范输入参照下的口语损失；正的 rewritten / dual − original 表示相对口语原文的改善。canonical 的重排问题也不同，不能把这一差值完全归因于首阶段召回。", "",
              "区间为来源关联组件配对 bootstrap：每次抽取整个组件，保留组件内的双语与两种语料场景，2,000 次，固定种子 20260919。点估计按场景数加权；没有把相关查询视作独立样本。小样本区间仅作探索，没有多重比较校正。", "",
              "| 对比 | 指标 | 差值 | 95% 区间 | 来源组件 |", "|---|---|---:|---|---:|"]
    for comparison, by_group in intervals.items():
        for metric, value in by_group["all"].items():
            lines.append(f"| {comparison} | {metric} | {value['difference']:+.4f} | [{value['ci95'][0]:+.4f}, {value['ci95'][1]:+.4f}] | {value['clusters']} |")
    lines.append("")
    lines += ["各语言/模式的相同配对区间保存在 decision.json。全部逐题改写与得失见 test-changes.csv。", "",
              "## 失败归因与改写检查", "",
              "test-failure-attribution.json 按双方成功、原文失败、候选策略失败及双方失败拆分净命中变化。接口状态差异造成的净收益不能全部解释为改写提升；成功子集的事后拆分不替代保留失败的主结果。", ""]
    for split in ("dev", "test"):
        selected = [rewrites.get(q["id"], {}) for q in queries.values() if q["split"] == split]
        failed = sum(r.get("status") != "succeeded" for r in selected)
        unclear = sum(isinstance(r.get("result"), dict) and bool(r["result"].get("needs_clarification")) for r in selected)
        lines.append(f"- {split}：改写记录未成功或缺失 {failed}/{len(selected)}，请求澄清 {unclear}/{len(selected)}。JSON 结构通过不等于含义保持，必须检查新增概念、删去限定词和歧义处理。")
    lines += ["", "## 调用量、费用和延迟", "", "| 能力 | 实际请求 | 失败 | 已报告费用之和 | 缺费用字段 | p50 ms | p95 ms |",
              "|---|---:|---:|---:|---:|---:|---:|"]
    for capability, value in calls.items():
        cost = "未报告" if value["known_cost"] is None else f"{value['known_cost']:.8f}"
        lines.append(f"| {capability} | {value['attempts']} | {value['failures']} | {cost} | {value['missing_cost_count']} | {formatted(value['p50_ms'])} | {formatted(value['p95_ms'])} |")
    lines += ["", "费用仅汇总供应商实际返回的 cost 字段；缺失不按零费用解释，也未核对账户总账单。返回的模型标识、token 已知合计和缺失数见 decision.json；没有假定未报告币种。", "",
              "## 结论使用范围与复现", "",
              f"开发集选择 {winner}，仅代表这组预设实验的选择结果。是否启用默认 rewrite 还需要新的真实口语/课程查询、语义保持审核、故障与延迟预算验证；本次脚本不修改运行时、数据库或默认检索策略。不能凭保留部分中另一个臂更高就反向重新调参。", "",
              "这是旧 R5 来源上的小规模受控扰动实验，不能证明所有口语输入都需要改写，也不能声称某个策略普遍最强。第一阶段候选改写与最终生成提示词是不同对象；本实验不把重写后文本作为用户最终意图的替代。", "",
              "运行 `python scripts/r6_report.py --run <归档目录>` 可从冻结逐题记录重建本报告，不发起 API 调用。decision.json 保存输入 SHA-256；dev/test-metrics.csv 保留完整分组指标与缺失统计，selection-lock.json 在报告中仅验证不改写。", ""]
    observations = []
    for comparison, label in (("original_minus_canonical", "口语原文相对规范问题"),
                              ("rewritten_minus_original", "改写相对口语原文"),
                              ("dual_minus_original", "两路合并相对口语原文")):
        value = intervals[comparison]["all"]["budget_hit"]
        contains_zero = value["ci95"][0] <= 0 <= value["ci95"][1]
        observations.append(f"- {label}：预算命中差 {100 * value['difference']:+.2f} 个百分点；95% 组件区间 "
                            f"[{100 * value['ci95'][0]:+.2f}, {100 * value['ci95'][1]:+.2f}] 个百分点，"
                            + ("包含零，不能据此确认稳定的总体提升或下降。" if contains_zero else
                               "未包含零，仍受小样本、旧来源和合成扰动范围限制。"))
    lines[4:4] = observations + [""]
    (run / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return decision


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    decision = report(parser.parse_args().run)
    print(json.dumps({"dev_selected": decision["dev_selected"], "production_action": decision["production_action"],
                      "test_hit_changes": decision["test_hit_changes"]}, ensure_ascii=False, indent=2))
