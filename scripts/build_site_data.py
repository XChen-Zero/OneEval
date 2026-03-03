#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from extract_results import (
    PUBLIC_RESULTS_PREFIX,
    build_public_bundle,
    collect_results_bundle,
    materialize_public_results,
    relative_posix,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SITE_DATA_ROOT = REPO_ROOT / "site" / "data"
CATEGORY_ORDER = ["knowledge", "agentic", "instruction_following", "reasoning"]
CATEGORY_META = {
    "knowledge": {
        "display_name": "Knowledge",
        "description": (
            "Knowledge benchmarks emphasize factual recall, domain expertise, and "
            "subset-level coverage."
        ),
        "href": "./knowledge.html",
        "featured_note": "Best for MMLU-Pro, Chinese SimpleQA, and GPQA-style reading.",
    },
    "agentic": {
        "display_name": "Agentic",
        "description": (
            "Agentic evaluation focuses on tool use, workflow handling, and "
            "multi-scenario behavior."
        ),
        "href": "./agentic.html",
        "featured_note": "BFCL v3 is the sole agentic benchmark in the current release.",
    },
    "reasoning": {
        "display_name": "Reasoning",
        "description": (
            "Reasoning benchmarks include pass@k math evaluation and logic-heavy tasks."
        ),
        "href": "./reasoning.html",
        "featured_note": "Best for AIME pass@k curves and logic-style benchmarks.",
    },
    "instruction_following": {
        "display_name": "IF",
        "description": (
            "Instruction-following evaluation isolates compliance with explicit "
            "formatting and behavioral constraints."
        ),
        "href": "./if.html",
        "featured_note": "IFEval is split out as its own reading path.",
    },
}

BENCHMARK_CATEGORY = {
    "chinese_simpleqa": "knowledge",
    "gpqa_diamond": "knowledge",
    "mmlu_pro": "knowledge",
    "simple_qa": "knowledge",
    "super_gpqa": "knowledge",
    "bfcl_v3": "agentic",
    "aime24": "reasoning",
    "aime25": "reasoning",
    "hmmt25": "reasoning",
    "ifeval": "instruction_following",
    "zebralogicbench": "reasoning",
}

PROTOCOL_TOP_LEVEL_LABELS = {
    "evalscope_version": "EvalScope",
    "eval_backend": "Backend",
    "eval_batch_size": "Eval batch size",
    "eval_type": "Eval type",
    "judge_strategy": "Judge strategy",
    "limit": "Limit",
    "debug": "Debug",
    "max_model_len": "Max model len",
    "max-model-len": "Max model len",
}
PROTOCOL_GENERATION_LABELS = {
    "temperature": "Temperature",
    "top_p": "Top-p",
    "top_k": "Top-k",
    "min_p": "Min-p",
    "presence_penalty": "Presence penalty",
    "repetition_penalty": "Repetition penalty",
    "max_tokens": "Max tokens",
    "max_new_tokens": "Max new tokens",
    "batch_size": "Batch size",
    "do_sample": "Do sample",
    "n": "Num generations",
    "num_generations": "Num generations",
    "pass_k": "Pass@k",
}
PROTOCOL_TOP_LEVEL_ORDER = [
    "evalscope_version",
    "eval_backend",
    "eval_batch_size",
    "eval_type",
    "judge_strategy",
    "limit",
    "debug",
    "max_model_len",
    "max-model-len",
]
PROTOCOL_GENERATION_ORDER = [
    "temperature",
    "top_p",
    "top_k",
    "min_p",
    "presence_penalty",
    "repetition_penalty",
    "max_tokens",
    "max_new_tokens",
    "batch_size",
    "do_sample",
    "n",
    "num_generations",
    "pass_k",
]
MANUAL_PROTOCOL_OVERRIDES = {
    ("Qwen3.5", "CoT"): {
        "title": "Qwen3.5 CoT default",
        "lines": [
            {"label": "Temperature", "value": "0.6"},
            {"label": "Top-p", "value": "0.95"},
            {"label": "Top-k", "value": "20"},
            {"label": "Min-p", "value": "0.0"},
            {"label": "Presence penalty", "value": "0.0"},
            {"label": "Repetition penalty", "value": "1.0"},
            {"label": "Max model len", "value": "262144"},
        ],
        "notes": ["Qwen3.5 max-model-len is fixed at 262144."],
    },
    ("Qwen3.5", "NoCoT"): {
        "title": "Qwen3.5 NoCoT default",
        "lines": [
            {"label": "Temperature", "value": "0.7"},
            {"label": "Top-p", "value": "0.8"},
            {"label": "Top-k", "value": "20"},
            {"label": "Min-p", "value": "0.0"},
            {"label": "Presence penalty", "value": "1.5"},
            {"label": "Repetition penalty", "value": "1.0"},
            {"label": "Max model len", "value": "262144"},
        ],
        "notes": ["Qwen3.5 max-model-len is fixed at 262144."],
    },
}
QWEN_STYLE_FAMILIES = {"Qwen3", "Qwen3.5", "Qwen3-Next", "DeepSeek"}
QWEN_STYLE_BENCHMARK_REPEAT_OVERRIDES = {
    "gpqa_diamond": 10,
    "chinese_simpleqa": 1,
    "simple_qa": 1,
    "mmlu_pro": 1,
    "ifeval": 1,
    "aime24": 64,
    "aime25": 64,
    "zebralogicbench": 1,
}


def sorted_unique(values: list[str]) -> list[str]:
    return sorted({value for value in values if value}, key=str.lower)


def model_family(model_name: str) -> str:
    lowered = model_name.lower()
    if lowered.startswith("qwen3.5"):
        return "Qwen3.5"
    if lowered.startswith("qwen3-next"):
        return "Qwen3-Next"
    if lowered.startswith("qwen3"):
        return "Qwen3"
    if lowered.startswith("meta-llama") or "llama" in lowered:
        return "Llama"
    if lowered.startswith("deepseek"):
        return "DeepSeek"
    return model_name.split("-")[0]


def benchmark_category(benchmark: str) -> str:
    return BENCHMARK_CATEGORY.get(benchmark, "knowledge")


def benchmark_display_name(records: list[dict[str, Any]], benchmark: str) -> str:
    for record in records:
        if record["benchmark"] == benchmark:
            return record["benchmark_display"] or benchmark
    return benchmark


def metric_priority(metric: str) -> int:
    lowered = metric.lower()
    if lowered == "mean_acc":
        return 0
    if lowered == "mean_is_correct":
        return 1
    if lowered == "mean_is_incorrect":
        return 2
    if lowered == "mean_is_not_attempted":
        return 3
    if "summary" in lowered:
        return 4
    if "correct" in lowered:
        return 5
    if "pass" in lowered:
        return 8
    return 6


def metric_label(metric: str) -> str:
    labels = {
        "mean_acc": "Accuracy",
        "mean_is_correct": "Correct",
        "mean_is_incorrect": "Incorrect",
        "mean_is_not_attempted": "Abstain",
    }
    if metric in labels:
        return labels[metric]
    return metric.replace("_", " ")


def format_score_value(score: float | None, score_unit: str) -> str:
    if score is None:
        return "n/a"
    if score_unit == "percent":
        return f"{score:.2f}%"
    return f"{score:.4f}"


def format_protocol_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return f"{value:g}"
    return str(value)


def protocol_line_signature(lines: list[dict[str, str]]) -> str:
    return json.dumps(lines, ensure_ascii=False, sort_keys=True)


def protocol_summary_from_lines(lines: list[dict[str, str]]) -> str:
    if not lines:
        return "No published config"
    return " · ".join(f"{line['label']} {line['value']}" for line in lines)


def protocol_param_values_from_lines(lines: list[dict[str, str]]) -> dict[str, str]:
    values = {"temperature": "—", "top_p": "—", "top_k": "—"}
    for line in lines:
        label = line["label"]
        if label == "Temperature":
            values["temperature"] = line["value"]
        elif label == "Top-p":
            values["top_p"] = line["value"]
        elif label == "Top-k":
            values["top_k"] = line["value"]
    return values


def manual_protocol_variant(family: str, mode: str) -> dict[str, Any] | None:
    override = MANUAL_PROTOCOL_OVERRIDES.get((family, mode))
    if not override:
        return None
    lines = [dict(line) for line in override["lines"]]
    return {
        "title": override["title"],
        "lines": lines,
        "summary": protocol_summary_from_lines(lines),
        "manual_override": True,
        "notes": list(override.get("notes", [])),
    }


def config_excerpt_to_protocol_lines(config_excerpt: dict[str, Any]) -> list[dict[str, str]]:
    lines: list[dict[str, str]] = []
    for key in PROTOCOL_TOP_LEVEL_ORDER:
        value = config_excerpt.get(key)
        if value is None:
            continue
        lines.append(
            {
                "label": PROTOCOL_TOP_LEVEL_LABELS[key],
                "value": format_protocol_value(value),
            }
        )

    generation = config_excerpt.get("generation_config", {})
    for key in PROTOCOL_GENERATION_ORDER:
        value = generation.get(key)
        if value is None:
            continue
        lines.append(
            {
                "label": PROTOCOL_GENERATION_LABELS[key],
                "value": format_protocol_value(value),
            }
        )
    return lines


def build_protocol_variants(
    family: str,
    mode: str,
    config_excerpts: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    override_variant = manual_protocol_variant(family, mode)
    if override_variant:
        return [override_variant], list(override_variant.get("notes", []))

    variants: list[dict[str, Any]] = []
    seen_signatures: set[str] = set()

    for config_excerpt in config_excerpts:
        lines = config_excerpt_to_protocol_lines(config_excerpt)
        signature = protocol_line_signature(lines)
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        variants.append(
            {
                "title": "",
                "lines": lines,
                "summary": protocol_summary_from_lines(lines),
                "manual_override": False,
            }
        )

    if not variants:
        variants.append(
            {
                "title": "Published setup unavailable",
                "lines": [],
                "summary": "No published config",
                "manual_override": False,
            }
        )

    if len(variants) == 1 and variants[0]["lines"]:
        variants[0]["title"] = "Published sampling"
    elif len(variants) > 1:
        for index, variant in enumerate(variants, start=1):
            variant["title"] = f"Variant {index}"

    return variants, []


def unique_protocol_param_values(
    config_excerpts: list[dict[str, Any]],
) -> dict[str, str]:
    collected = {
        "temperature": set(),
        "top_p": set(),
        "top_k": set(),
    }
    for config_excerpt in config_excerpts:
        generation = config_excerpt.get("generation_config", {})
        for key in collected:
            value = generation.get(key)
            if value is not None:
                collected[key].add(format_protocol_value(value))
    summary: dict[str, str] = {}
    for key, values in collected.items():
        if not values:
            summary[key] = "—"
        elif len(values) == 1:
            summary[key] = next(iter(values))
        else:
            summary[key] = ", ".join(sorted(values, key=str))
    return summary


def protocol_repeat_count(
    family: str,
    benchmark: str,
    *,
    distinct_run_count: int,
    pass_k_count: int,
) -> int:
    if benchmark == "bfcl_v3":
        return 8 if distinct_run_count >= 8 else 1
    if family in QWEN_STYLE_FAMILIES:
        manual = QWEN_STYLE_BENCHMARK_REPEAT_OVERRIDES.get(benchmark)
        if manual is not None:
            return manual
    if family == "Llama":
        return 1
    return max(distinct_run_count, pass_k_count)


def summarize_config_excerpt(config_excerpt: dict[str, Any]) -> str:
    generation = config_excerpt.get("generation_config", {})
    parts: list[str] = []

    if config_excerpt.get("evalscope_version"):
        parts.append(f"EvalScope {config_excerpt['evalscope_version']}")
    if config_excerpt.get("eval_backend"):
        parts.append(str(config_excerpt["eval_backend"]))
    if generation.get("temperature") is not None:
        parts.append(f"temp {generation['temperature']}")
    if generation.get("top_p") is not None:
        parts.append(f"top-p {generation['top_p']}")
    if generation.get("top_k") is not None:
        parts.append(f"top-k {generation['top_k']}")
    if generation.get("max_tokens") is not None:
        parts.append(f"max {generation['max_tokens']}")
    elif generation.get("max_new_tokens") is not None:
        parts.append(f"max {generation['max_new_tokens']}")
    if generation.get("do_sample") is not None:
        parts.append(f"sample {generation['do_sample']}")
    if generation.get("pass_k") is not None:
        parts.append(f"pass@{generation['pass_k']}")
    if generation.get("n") is not None:
        parts.append(f"n {generation['n']}")
    elif generation.get("num_generations") is not None:
        parts.append(f"n {generation['num_generations']}")

    return " · ".join(parts) if parts else "No published config"


def parse_pass_metric(metric: str) -> tuple[str, int] | None:
    lowered = metric.lower()
    marker = "pass@"
    alt_marker = "pass^"
    if marker in lowered:
        index = lowered.rfind(marker)
        base = metric[:index].rstrip("_-")
        suffix = metric[index + len(marker) :]
    elif alt_marker in lowered:
        index = lowered.rfind(alt_marker)
        base = metric[:index].rstrip("_-")
        suffix = metric[index + len(alt_marker) :]
    else:
        return None

    if not suffix.isdigit():
        return None
    return (base or "metric", int(suffix))


def pass_milestones(
    points: list[dict[str, Any]], score_unit: str
) -> list[dict[str, Any]]:
    if not points:
        return []

    by_k = {point["k"]: point for point in points}
    selected: list[dict[str, Any]] = []
    target_ks = [1, 8, 32, 64]

    for k in target_ks:
        if k in by_k:
            selected.append(by_k[k])

    first = points[0]
    last = points[-1]
    if not any(point["k"] == first["k"] for point in selected):
        selected.insert(0, first)
    if not any(point["k"] == last["k"] for point in selected):
        selected.append(last)

    selected.sort(key=lambda item: item["k"])

    milestones = [
        {
            "k": point["k"],
            "score": point["score"],
            "score_label": format_score_value(point["score"], score_unit),
        }
        for point in selected
    ]

    gain = None
    if first["score"] is not None and last["score"] is not None:
        delta = last["score"] - first["score"]
        gain = {
            "label": "Gain",
            "score": delta,
            "score_label": (
                f"{delta:.2f}%"
                if score_unit == "percent"
                else f"{delta:+.4f}"
            ),
        }

    if gain:
        milestones.append(gain)
    return milestones


def clean_output_dirs(output_root: Path) -> None:
    for subdir in ("categories", "benchmarks"):
        directory = output_root / subdir
        if not directory.exists():
            continue
        for file_path in directory.glob("*.json"):
            file_path.unlink()


def build_protocol_payload(public_bundle: dict[str, Any]) -> dict[str, Any]:
    records = public_bundle["records"]
    benchmark_display = {
        record["benchmark"]: record["benchmark_display"] or record["benchmark"]
        for record in records
    }
    models_by_scope: dict[tuple[str, str, str], set[str]] = {}
    for record in records:
        key = (model_family(record["model"]), record["mode"], record["benchmark"])
        models_by_scope.setdefault(key, set()).add(record["model"])
    pass_k_by_scope: dict[tuple[str, str, str], int] = {}
    for record in records:
        if not record["is_overall"]:
            continue
        if benchmark_category(record["benchmark"]) != "reasoning":
            continue
        parsed = parse_pass_metric(record["metric"])
        if not parsed:
            continue
        key = (model_family(record["model"]), record["mode"], record["benchmark"])
        pass_k_by_scope[key] = max(pass_k_by_scope.get(key, 0), parsed[1])

    grouped: dict[tuple[str, str], dict[str, Any]] = {}

    for run_setting in public_bundle["run_settings"].values():
        family = model_family(run_setting["model"])
        mode = run_setting["mode"]
        key = (family, mode)
        entry = grouped.setdefault(
            key,
            {
                "family": family,
                "mode": mode,
                "config_excerpts": [],
                "benchmarks": set(),
                "coverage_count": 0,
                "notes": set(),
            },
        )
        entry["coverage_count"] += 1
        entry["config_excerpts"].append(dict(run_setting["config_excerpt"]))
        entry["benchmarks"].update(run_setting["benchmarks"])
        if "bfcl_v3" in run_setting["benchmarks"]:
            entry["notes"].add("BFCL v3 uses YaRN context extension to 131072.")

    families: dict[str, dict[str, Any]] = {}
    for (family, _mode), entry in grouped.items():
        settings_variants, override_notes = build_protocol_variants(
            family,
            entry["mode"],
            entry["config_excerpts"],
        )
        if settings_variants and settings_variants[0].get("manual_override"):
            protocol_params = protocol_param_values_from_lines(
                settings_variants[0]["lines"]
            )
        else:
            protocol_params = unique_protocol_param_values(entry["config_excerpts"])
        benchmark_run_counts = [
            {
                "benchmark": benchmark,
                "display_name": benchmark_display.get(benchmark, benchmark),
                "distinct_run_count": distinct_run_count,
                "run_count": protocol_repeat_count(
                    family,
                    benchmark,
                    distinct_run_count=distinct_run_count,
                    pass_k_count=pass_k_by_scope.get(
                        (family, entry["mode"], benchmark), 0
                    ),
                ),
            }
            for benchmark in sorted(
                entry["benchmarks"],
                key=lambda item: benchmark_display.get(item, item).lower(),
            )
            for distinct_run_count in [
                len(models_by_scope.get((family, entry["mode"], benchmark), set()))
            ]
        ]
        repeated_benchmarks = [
            benchmark_entry
            for benchmark_entry in benchmark_run_counts
            if benchmark_entry["run_count"] > 1
        ]
        notes = sorted(set(entry["notes"]).union(override_notes), key=str.lower)
        if repeated_benchmarks:
            repeated_summary = ", ".join(
                f"{item['display_name']} x{item['run_count']}"
                for item in repeated_benchmarks
            )
            notes.append(f"Repeated runs: {repeated_summary}.")

        family_entry = families.setdefault(
            family,
            {
                "family": family,
                "modes": [],
                "benchmarks": set(),
                "family_run_count": 0,
            },
        )
        family_entry["family_run_count"] += entry["coverage_count"]
        family_entry["benchmarks"].update(entry["benchmarks"])
        family_entry["modes"].append(
            {
                "mode": entry["mode"],
                "temperature": protocol_params["temperature"],
                "top_p": protocol_params["top_p"],
                "top_k": protocol_params["top_k"],
                "settings_variants": settings_variants,
                "settings_summary": " / ".join(
                    variant["summary"] for variant in settings_variants
                ),
                "coverage_count": entry["coverage_count"],
                "benchmark_count": len(entry["benchmarks"]),
                "benchmarks": sorted(entry["benchmarks"], key=str.lower),
                "benchmark_run_counts": benchmark_run_counts,
                "repeated_benchmarks": repeated_benchmarks,
                "notes": notes,
            }
        )

    family_rows = []
    for family in sorted(families, key=str.lower):
        family_entry = families[family]
        modes = sorted(
            family_entry["modes"],
            key=lambda item: (0 if item["mode"] == "CoT" else 1, item["mode"].lower()),
        )
        family_rows.append(
            {
                "family": family,
                "modes": modes,
                "family_run_count": family_entry["family_run_count"],
                "benchmark_count": len(family_entry["benchmarks"]),
            }
        )

    return {
        "generated_at": public_bundle["generated_at"],
        "families": family_rows,
        "global_notes": ["BFCL v3 uses YaRN context extension to 131072."],
    }


def build_benchmark_detail(
    benchmark: str,
    records: list[dict[str, Any]],
    generated_at: str,
) -> dict[str, Any]:
    display_name = benchmark_display_name(records, benchmark)
    benchmark_records = [record for record in records if record["benchmark"] == benchmark]
    subset_records = [
        record
        for record in benchmark_records
        if not record["is_overall"] and parse_pass_metric(record["metric"]) is None
    ]
    pass_records = [
        record
        for record in benchmark_records
        if record["is_overall"] and parse_pass_metric(record["metric"]) is not None
    ]
    overall_scalar_records = [
        record
        for record in benchmark_records
        if record["is_overall"] and parse_pass_metric(record["metric"]) is None
    ]

    grouped_overall: dict[tuple[str, str], dict[str, Any]] = {}
    subset_count_by_subject: dict[tuple[str, str], set[str]] = {}

    for record in subset_records:
        subject_key = (record["model"], record["mode"])
        subset_count_by_subject.setdefault(subject_key, set())
        subset_count_by_subject[subject_key].add(record["subset"])

    for record in overall_scalar_records:
        subject_key = (record["model"], record["mode"])
        entry = grouped_overall.setdefault(
            subject_key,
            {
                "model": record["model"],
                "mode": record["mode"],
                "subject_label": f"{record['model']} · {record['mode']}",
                "metrics": {},
                "num_samples": record["num_samples"],
                "subset_count": len(subset_count_by_subject.get(subject_key, set())),
            },
        )
        entry["metrics"][record["metric"]] = record
        if entry["num_samples"] is None and record["num_samples"] is not None:
            entry["num_samples"] = record["num_samples"]

    overall_rows = []
    for (_model, _mode), entry in sorted(grouped_overall.items(), key=lambda item: (item[0][0].lower(), item[0][1].lower())):
        ordered_metrics = sorted(
            entry["metrics"],
            key=lambda metric: (metric_priority(metric), metric.lower()),
        )
        primary_metric = ordered_metrics[0]
        primary_record = entry["metrics"][primary_metric]
        supporting_metrics = [
            {
                "name": metric,
                "label": metric_label(metric),
                "score": entry["metrics"][metric]["score"],
                "score_label": format_score_value(
                    entry["metrics"][metric]["score"],
                    entry["metrics"][metric]["score_unit"],
                ),
            }
            for metric in ordered_metrics[1:]
        ]
        overall_rows.append(
            {
                "benchmark": benchmark,
                "benchmark_display": display_name,
                "model": entry["model"],
                "mode": entry["mode"],
                "subject_label": entry["subject_label"],
                "primary_metric_name": primary_metric,
                "primary_metric_label": metric_label(primary_metric),
                "primary_score": primary_record["score"],
                "primary_score_label": format_score_value(
                    primary_record["score"], primary_record["score_unit"]
                ),
                "supporting_metrics": supporting_metrics,
                "num_samples": entry["num_samples"],
                "subset_count": entry["subset_count"],
                "detail_ref": f"./data/benchmarks/{benchmark}.json",
            }
        )

    flat_subset_rows = [
        {
            "model": record["model"],
            "mode": record["mode"],
            "metric": record["metric"],
            "metric_label": metric_label(record["metric"]),
            "subset": record["subset"],
            "score": record["score"],
            "score_label": format_score_value(record["score"], record["score_unit"]),
            "num_samples": record["num_samples"],
        }
        for record in sorted(
            subset_records,
            key=lambda item: (
                item["model"].lower(),
                item["mode"].lower(),
                metric_priority(item["metric"]),
                item["metric"].lower(),
                item["subset"].lower(),
            ),
        )
    ]

    pass_groups_map: dict[tuple[str, str, str], dict[str, Any]] = {}
    for record in pass_records:
        parsed = parse_pass_metric(record["metric"])
        if not parsed:
            continue
        metric_base, k = parsed
        key = (record["model"], record["mode"], metric_base)
        entry = pass_groups_map.setdefault(
            key,
            {
                "benchmark": benchmark,
                "benchmark_display": display_name,
                "model": record["model"],
                "mode": record["mode"],
                "metric_base": metric_base,
                "score_unit": record["score_unit"],
                "points": [],
            },
        )
        entry["points"].append({"k": k, "score": record["score"]})

    passk_rows = []
    for (_model, _mode, _metric_base), entry in sorted(
        pass_groups_map.items(), key=lambda item: (item[0][0].lower(), item[0][1].lower(), item[0][2].lower())
    ):
        points = sorted(entry["points"], key=lambda point: point["k"])
        passk_rows.append(
            {
                "benchmark": benchmark,
                "benchmark_display": display_name,
                "model": entry["model"],
                "mode": entry["mode"],
                "metric_base": entry["metric_base"],
                "score_unit": entry["score_unit"],
                "points": [
                    {
                        "k": point["k"],
                        "score": point["score"],
                        "score_label": format_score_value(
                            point["score"], entry["score_unit"]
                        ),
                    }
                    for point in points
                ],
                "milestones": pass_milestones(points, entry["score_unit"]),
                "detail_ref": f"./data/benchmarks/{benchmark}.json",
            }
        )

    artifact_paths = sorted_unique(
        [record["public_artifact_path"] for record in benchmark_records]
    )
    detail_payload = {
        "benchmark": benchmark,
        "category": benchmark_category(benchmark),
        "display_name": display_name,
        "generated_at": generated_at,
        "models": sorted_unique([record["model"] for record in benchmark_records]),
        "overall_rows": overall_rows,
        "subset_rows": flat_subset_rows,
        "passk_rows": passk_rows,
        "downloads": {
            "json_path": f"./data/benchmarks/{benchmark}.json",
            "artifact_paths": artifact_paths,
            "notes": "Detailed public-safe artifacts are copied under published_results/.",
        },
    }
    return detail_payload


def category_display_type(benchmark_payload: dict[str, Any]) -> str:
    has_pass = bool(benchmark_payload["passk_rows"])
    has_subset = bool(benchmark_payload["subset_rows"])
    if has_pass and (benchmark_payload["overall_rows"] or has_subset):
        return "mixed"
    if has_pass:
        return "passk_chart"
    if has_subset:
        return "subset_table"
    return "scalar_table"


def build_category_payloads(
    public_bundle: dict[str, Any]
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    records = public_bundle["records"]
    benchmark_payloads: dict[str, dict[str, Any]] = {}
    for benchmark in sorted({record["benchmark"] for record in records}, key=str.lower):
        benchmark_payloads[benchmark] = build_benchmark_detail(
            benchmark=benchmark,
            records=records,
            generated_at=public_bundle["generated_at"],
        )

    category_payloads: dict[str, dict[str, Any]] = {}
    for category in CATEGORY_ORDER:
        category_benchmarks = [
            payload
            for benchmark, payload in benchmark_payloads.items()
            if benchmark_category(benchmark) == category
        ]
        category_benchmarks.sort(key=lambda item: item["display_name"].lower())

        benchmarks = []
        scoped_records = [
            record
            for record in records
            if benchmark_category(record["benchmark"]) == category
        ]
        for payload in category_benchmarks:
            subset_names = sorted_unique(
                [row["subset"] for row in payload["subset_rows"]]
            )
            benchmarks.append(
                {
                    "benchmark": payload["benchmark"],
                    "display_name": payload["display_name"],
                    "display_type": category_display_type(payload),
                    "benchmark_data_path": f"./data/benchmarks/{payload['benchmark']}.json",
                    "model_rows": payload["overall_rows"],
                    "subset_drilldowns": {
                        "available": bool(payload["subset_rows"]),
                        "row_count": len(payload["subset_rows"]),
                        "preview_subsets": subset_names[:8],
                    },
                    "passk_groups": payload["passk_rows"],
                    "download": {
                        "json_path": payload["downloads"]["json_path"],
                        "artifact_count": len(payload["downloads"]["artifact_paths"]),
                        "sample_artifact_paths": payload["downloads"][
                            "artifact_paths"
                        ][:3],
                        "notes": payload["downloads"]["notes"],
                    },
                }
            )

        category_payloads[category] = {
            "category": category,
            "display_name": CATEGORY_META[category]["display_name"],
            "description": CATEGORY_META[category]["description"],
            "generated_at": public_bundle["generated_at"],
            "filters": {
                "models": sorted_unique([record["model"] for record in scoped_records]),
                "modes": sorted_unique([record["mode"] for record in scoped_records]),
                "benchmarks": sorted_unique(
                    [record["benchmark"] for record in scoped_records]
                ),
            },
            "benchmarks": benchmarks,
        }

    return category_payloads, benchmark_payloads


def build_index_payload(
    public_bundle: dict[str, Any],
    category_payloads: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    records = public_bundle["records"]
    category_summary = []
    featured_benchmarks = []

    for category in CATEGORY_ORDER:
        payload = category_payloads[category]
        benchmarks = payload["benchmarks"]
        benchmark_ids = [item["benchmark"] for item in benchmarks]
        model_count = len(
            {
                record["model"]
                for record in records
                if record["benchmark"] in benchmark_ids
            }
        )
        category_summary.append(
            {
                "category": category,
                "display_name": CATEGORY_META[category]["display_name"],
                "description": CATEGORY_META[category]["description"],
                "href": CATEGORY_META[category]["href"],
                "benchmark_count": len(benchmarks),
                "model_count": model_count,
                "benchmarks": [
                    {"benchmark": item["benchmark"], "display_name": item["display_name"]}
                    for item in benchmarks
                ],
                "featured_note": CATEGORY_META[category]["featured_note"],
            }
        )
        for item in benchmarks[:2]:
            featured_benchmarks.append(
                {
                    "category": category,
                    "benchmark": item["benchmark"],
                    "display_name": item["display_name"],
                }
            )

    return {
        "generated_at": public_bundle["generated_at"],
        "summary": {
            **public_bundle["summary"],
            "overall_record_count": sum(
                1 for record in records if record["is_overall"]
            ),
            "subset_record_count": sum(
                1 for record in records if not record["is_overall"]
            ),
        },
        "category_summary": category_summary,
        "featured_benchmarks": featured_benchmarks,
        "publication": {
            "public_results_root": PUBLIC_RESULTS_PREFIX,
            "layout": "published_results/models/<model>/<benchmark>/<mode>/<run_id>/",
            "sanitization_rules": [
                "Only allowlisted EvalScope config fields are published.",
                "Raw config files are never copied into the public site.",
                "Local paths, URLs, names, logs, and credentials are excluded.",
            ],
            "excluded_invalid_sources": {
                "benchmark_file_excludes": public_bundle["exclusions"][
                    "benchmark_file_excludes"
                ],
                "benchmark_keyword_excludes": public_bundle["exclusions"][
                    "benchmark_keyword_excludes"
                ],
            },
        },
        "downloads": {
            "detailed_results_json": "./data/detailed_results.json",
            "legacy_flat_bundle_json": "./data/site_data.json",
            "public_results_root": "published_results/",
        },
    }


def build_legacy_flat_payload(public_bundle: dict[str, Any]) -> dict[str, Any]:
    records = public_bundle["records"]
    return {
        "generated_at": public_bundle["generated_at"],
        "publication": {
            "public_results_root": PUBLIC_RESULTS_PREFIX,
            "layout": "published_results/models/<model>/<benchmark>/<mode>/<run_id>/",
        },
        "summary": {
            **public_bundle["summary"],
            "overall_record_count": sum(1 for record in records if record["is_overall"]),
            "subset_record_count": sum(
                1 for record in records if not record["is_overall"]
            ),
        },
        "filters": {
            "models": sorted_unique([record["model"] for record in records]),
            "modes": sorted_unique([record["mode"] for record in records]),
            "benchmarks": sorted_unique([record["benchmark"] for record in records]),
            "metrics": sorted_unique([record["metric"] for record in records]),
            "subsets": sorted_unique([record["subset"] for record in records]),
        },
        "run_settings": public_bundle["run_settings"],
        "exclusions": public_bundle["exclusions"],
        "records": records,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def build_site_payloads(output_root: Path) -> dict[str, Any]:
    bundle = collect_results_bundle()
    materialize_public_results(bundle)
    public_bundle = build_public_bundle(bundle)
    clean_output_dirs(output_root)

    protocol_payload = build_protocol_payload(public_bundle)
    category_payloads, benchmark_payloads = build_category_payloads(public_bundle)
    index_payload = build_index_payload(public_bundle, category_payloads)
    detailed_payload = {
        "generated_at": public_bundle["generated_at"],
        "records": public_bundle["records"],
        "download_notes": [
            "This file contains the full public-safe flat record export.",
            "Per-benchmark detail JSON is available under site/data/benchmarks/.",
        ],
    }
    legacy_payload = build_legacy_flat_payload(public_bundle)

    return {
        "bundle": bundle,
        "public_bundle": public_bundle,
        "index": index_payload,
        "protocol": protocol_payload,
        "categories": category_payloads,
        "benchmarks": benchmark_payloads,
        "detailed": detailed_payload,
        "legacy": legacy_payload,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate category-first static site data bundles from raw results."
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=SITE_DATA_ROOT,
        help=f"Output root (default: {relative_posix(SITE_DATA_ROOT)}).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_root = args.output_root
    payloads = build_site_payloads(output_root)

    write_json(output_root / "index.json", payloads["index"])
    write_json(output_root / "protocol.json", payloads["protocol"])
    for category, payload in payloads["categories"].items():
        write_json(output_root / "categories" / f"{category}.json", payload)
    for benchmark, payload in payloads["benchmarks"].items():
        write_json(output_root / "benchmarks" / f"{benchmark}.json", payload)
    write_json(output_root / "detailed_results.json", payloads["detailed"])
    write_json(output_root / "site_data.json", payloads["legacy"])

    summary = payloads["public_bundle"]["summary"]
    print(
        "Built site data: "
        f"{summary['record_count']} records, "
        f"{summary['model_count']} models, "
        f"{summary['benchmark_count']} benchmarks."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
