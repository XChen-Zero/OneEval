#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_ROOT = REPO_ROOT / "results"
SITE_ROOT = REPO_ROOT / "site"
PUBLIC_RESULTS_ROOT = REPO_ROOT / "published_results"
PUBLIC_RESULTS_PREFIX = "published_results"
XEVAL_ROOT = RESULTS_ROOT / "xeval"
BFCL_ROOT = RESULTS_ROOT / "bfcl_v3" / "bfcl_project_root"

# User-provided exclusions:
# 1. Exclude xeval code-style benchmarks.
# 2. Exclude xeval's bfcl benchmark.
XEVAL_EXACT_EXCLUDES = {
    "bfcl_v3",
    "live_code_bench",
    "multiple_humaneval",
    "multiple_mbpp",
}
XEVAL_KEYWORD_EXCLUDES = ("code", "humaneval", "mbpp", "bfcl")

SAFE_TOP_LEVEL_CONFIG_KEYS = {
    "evalscope_version",
    "eval_backend",
    "eval_batch_size",
    "eval_type",
    "judge_strategy",
    "limit",
    "debug",
    "max_model_len",
    "max-model-len",
}
SAFE_GENERATION_CONFIG_KEYS = {
    "batch_size",
    "do_sample",
    "max_tokens",
    "max_new_tokens",
    "temperature",
    "top_k",
    "top_p",
    "min_p",
    "presence_penalty",
    "repetition_penalty",
    "n",
    "num_generations",
    "pass_k",
}


def now_utc_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def relative_posix(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def safe_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    if text.endswith("%"):
        text = text[:-1]
    try:
        return float(text)
    except ValueError:
        return None


def safe_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    try:
        return int(str(value).strip())
    except ValueError:
        return None


def format_category_name(value: Any) -> str:
    if isinstance(value, list):
        parts = [str(item).strip() for item in value if str(item).strip()]
        return " / ".join(parts)
    if value is None:
        return ""
    return str(value).strip()


def infer_mode_from_model_name(model_name: str) -> str:
    lowered = model_name.lower()
    if "thinking" in lowered:
        return "thinking"
    if "instruct" in lowered:
        return "instruct"
    return "base"


def normalize_mode_label(mode_value: str) -> str:
    lowered = mode_value.strip().lower()
    if lowered in {"cot", "thinking"}:
        return "CoT"
    if lowered in {"nocot", "non_thinking", "non-thinking"}:
        return "NoCoT"
    if "thinking" in lowered and "non" not in lowered:
        return "CoT"
    return "NoCoT"


def should_skip_xeval_benchmark(benchmark_name: str) -> bool:
    lowered = benchmark_name.lower()
    if lowered in XEVAL_EXACT_EXCLUDES:
        return True
    return any(keyword in lowered for keyword in XEVAL_KEYWORD_EXCLUDES)


def parse_run_sort_value(run_id: str) -> int | None:
    compact = run_id.replace("_", "")
    if compact.isdigit():
        return int(compact)
    if run_id.startswith("run_"):
        suffix = run_id[4:]
        if suffix.isdigit():
            return int(suffix)
    return None


def make_record_id(
    source: str,
    artifact_path: str,
    metric: str,
    category: str,
    subset: str,
    run_id: str,
) -> str:
    parts = [
        source,
        artifact_path,
        run_id,
        metric or "",
        category or "",
        subset or "",
    ]
    return "::".join(parts)


def slugify_segment(value: str) -> str:
    text = value.strip().lower()
    chars: list[str] = []
    last_dash = False
    for char in text:
        if char.isalnum():
            chars.append(char)
            last_dash = False
            continue
        if char in {".", "_", "-"}:
            chars.append(char)
            last_dash = False
            continue
        if not last_dash:
            chars.append("-")
            last_dash = True
    slug = "".join(chars).strip("._-")
    return slug or "item"


def parse_scalar(text: str) -> Any:
    value = text.strip()
    if not value:
        return None
    if value.startswith(("'", '"')) and value.endswith(("'", '"')) and len(value) >= 2:
        return value[1:-1]

    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered in {"null", "none", "~"}:
        return None

    try:
        if any(char in value for char in (".", "e", "E")):
            return float(value)
        return int(value)
    except ValueError:
        return value


def extract_safe_config_excerpt(config_path: Path | None) -> dict[str, Any]:
    if config_path is None or not config_path.exists():
        return {}

    excerpt: dict[str, Any] = {}
    generation_config: dict[str, Any] = {}
    current_top_key: str | None = None

    for raw_line in config_path.read_text().splitlines():
        stripped_line = raw_line.lstrip()
        if not stripped_line or stripped_line.startswith("#"):
            continue
        if ":" not in stripped_line:
            continue

        indent = len(raw_line) - len(stripped_line)
        key_text, value_text = stripped_line.split(":", 1)
        key = key_text.strip().strip("-").strip()
        value = value_text.strip()

        if indent == 0:
            current_top_key = key
            if key in SAFE_TOP_LEVEL_CONFIG_KEYS and value:
                parsed = parse_scalar(value)
                if parsed is not None:
                    excerpt[key] = parsed
            continue

        if current_top_key == "generation_config" and key in SAFE_GENERATION_CONFIG_KEYS:
            if value:
                parsed = parse_scalar(value)
                if parsed is not None:
                    generation_config[key] = parsed

    if generation_config:
        excerpt["generation_config"] = generation_config

    return excerpt


def find_xeval_config_path(run_dir: Path) -> Path | None:
    config_dir = run_dir / "configs"
    if not config_dir.exists():
        return None
    config_files = sorted(config_dir.glob("*.yaml")) + sorted(config_dir.glob("*.yml"))
    if not config_files:
        return None
    return config_files[0]


def make_run_key(model: str, mode: str, run_id: str) -> str:
    return f"{slugify_segment(model)}::{slugify_segment(mode)}::{run_id}"


def build_public_artifact_path(
    model: str,
    benchmark: str,
    mode: str,
    run_id: str,
    filename: str,
) -> str:
    return (
        Path(PUBLIC_RESULTS_PREFIX)
        / "models"
        / slugify_segment(model)
        / slugify_segment(benchmark)
        / slugify_segment(mode)
        / run_id
        / filename
    ).as_posix()


def make_public_meta_path(public_artifact_path: str) -> str:
    return (Path(public_artifact_path).parent / "meta.json").as_posix()


def ensure_run_setting(
    run_settings: dict[str, dict[str, Any]],
    *,
    model: str,
    mode: str,
    run_id: str,
    benchmark: str,
    config_excerpt: dict[str, Any],
    public_meta_path: str,
) -> str:
    run_key = make_run_key(model, mode, run_id)
    entry = run_settings.setdefault(
        run_key,
        {
            "run_key": run_key,
            "model": model,
            "mode": mode,
            "run_id": run_id,
            "run_sort_value": parse_run_sort_value(run_id),
            "benchmarks": set(),
            "config_excerpt": {},
            "public_meta_path": public_meta_path,
        },
    )
    entry["benchmarks"].add(benchmark)
    if config_excerpt and not entry["config_excerpt"]:
        entry["config_excerpt"] = dict(config_excerpt)
    if public_meta_path:
        entry["public_meta_path"] = public_meta_path
    return run_key


def register_artifact(
    artifacts: dict[str, dict[str, Any]],
    *,
    artifact_path: str,
    public_artifact_path: str,
    public_meta_path: str,
    model: str,
    benchmark: str,
    benchmark_display: str,
    mode: str,
    run_id: str,
    config_excerpt: dict[str, Any],
) -> None:
    if artifact_path in artifacts:
        return
    artifacts[artifact_path] = {
        "artifact_path": artifact_path,
        "public_artifact_path": public_artifact_path,
        "public_meta_path": public_meta_path,
        "model": model,
        "benchmark": benchmark,
        "benchmark_display": benchmark_display,
        "mode": mode,
        "run_id": run_id,
        "config_excerpt": dict(config_excerpt),
    }


def build_xeval_record(
    *,
    model: str,
    mode: str,
    benchmark: str,
    benchmark_display: str,
    metric: str,
    category: str,
    subset: str,
    num_samples: int | None,
    score: float | None,
    run_id: str,
    run_key: str,
    artifact_path: str,
    public_artifact_path: str,
    public_meta_path: str,
    is_overall: bool,
) -> dict[str, Any]:
    category_value = category.strip()
    subset_value = subset.strip() or "OVERALL"
    return {
        "record_id": make_record_id(
            "xeval",
            artifact_path,
            metric,
            category_value,
            subset_value,
            run_id,
        ),
        "source": "xeval",
        "model": model,
        "mode": mode,
        "benchmark": benchmark,
        "benchmark_display": benchmark_display,
        "metric": metric,
        "category": category_value,
        "subset": subset_value,
        "num_samples": num_samples,
        "score": score,
        "score_unit": "ratio",
        "is_overall": is_overall,
        "run_id": run_id,
        "run_key": run_key,
        "run_sort_value": parse_run_sort_value(run_id),
        "artifact_path": artifact_path,
        "public_artifact_path": public_artifact_path,
        "public_meta_path": public_meta_path,
    }


def extract_xeval_records(
    run_settings: dict[str, dict[str, Any]],
    artifacts: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str], int, int]:
    records: list[dict[str, Any]] = []
    warnings: list[str] = []
    skipped = 0
    used = 0
    config_cache: dict[str, dict[str, Any]] = {}

    if not XEVAL_ROOT.exists():
        return records, warnings, skipped, used

    for report_path in sorted(XEVAL_ROOT.glob("**/reports/*/*.json")):
        benchmark_file = report_path.stem
        if should_skip_xeval_benchmark(benchmark_file):
            skipped += 1
            continue

        try:
            rel_parts = report_path.relative_to(XEVAL_ROOT).parts
            reports_index = rel_parts.index("reports")
        except ValueError:
            warnings.append(
                f"Could not parse xeval layout for {relative_posix(report_path)}"
            )
            continue

        prefix = rel_parts[:reports_index]
        if len(prefix) == 3:
            model_dir, raw_mode, run_id = prefix
            mode = normalize_mode_label(raw_mode)
        elif len(prefix) == 2:
            model_dir, run_id = prefix
            mode = normalize_mode_label(infer_mode_from_model_name(model_dir))
        else:
            warnings.append(
                f"Unexpected xeval directory shape for {relative_posix(report_path)}"
            )
            continue

        try:
            payload = json.loads(report_path.read_text())
        except json.JSONDecodeError as exc:
            warnings.append(
                f"Invalid JSON in {relative_posix(report_path)}: {exc.msg}"
            )
            continue

        used += 1
        artifact_path = relative_posix(report_path)
        model_name = str(payload.get("model_name") or model_dir)
        benchmark = str(payload.get("dataset_name") or benchmark_file)
        benchmark_display = str(payload.get("dataset_pretty_name") or benchmark)
        public_artifact_path = build_public_artifact_path(
            model_name, benchmark, mode, run_id, "result.json"
        )
        public_meta_path = make_public_meta_path(public_artifact_path)

        run_dir = report_path.parents[2]
        run_dir_key = relative_posix(run_dir)
        config_excerpt = config_cache.get(run_dir_key)
        if config_excerpt is None:
            config_excerpt = extract_safe_config_excerpt(find_xeval_config_path(run_dir))
            config_cache[run_dir_key] = config_excerpt

        run_key = ensure_run_setting(
            run_settings,
            model=model_name,
            mode=mode,
            run_id=run_id,
            benchmark=benchmark,
            config_excerpt=config_excerpt,
            public_meta_path=public_meta_path,
        )
        register_artifact(
            artifacts,
            artifact_path=artifact_path,
            public_artifact_path=public_artifact_path,
            public_meta_path=public_meta_path,
            model=model_name,
            benchmark=benchmark,
            benchmark_display=benchmark_display,
            mode=mode,
            run_id=run_id,
            config_excerpt=config_excerpt,
        )

        metrics = payload.get("metrics")
        if not isinstance(metrics, list):
            warnings.append(f"Missing metrics list in {relative_posix(report_path)}")
            continue

        for metric_entry in metrics:
            if not isinstance(metric_entry, dict):
                continue
            metric_name = str(metric_entry.get("name") or "unknown_metric")
            metric_num = safe_int(metric_entry.get("num"))
            metric_score = safe_float(metric_entry.get("score"))

            records.append(
                build_xeval_record(
                    model=model_name,
                    mode=mode,
                    benchmark=benchmark,
                    benchmark_display=benchmark_display,
                    metric=metric_name,
                    category="",
                    subset="OVERALL",
                    num_samples=metric_num,
                    score=metric_score,
                    run_id=run_id,
                    run_key=run_key,
                    artifact_path=artifact_path,
                    public_artifact_path=public_artifact_path,
                    public_meta_path=public_meta_path,
                    is_overall=True,
                )
            )

            categories = metric_entry.get("categories")
            if not isinstance(categories, list):
                continue

            for category_entry in categories:
                if not isinstance(category_entry, dict):
                    continue
                category_name = format_category_name(category_entry.get("name"))
                subsets = category_entry.get("subsets")
                if isinstance(subsets, list) and subsets:
                    for subset_entry in subsets:
                        if not isinstance(subset_entry, dict):
                            continue
                        subset_name = str(
                            subset_entry.get("name") or category_name or "default"
                        )
                        records.append(
                            build_xeval_record(
                                model=model_name,
                                mode=mode,
                                benchmark=benchmark,
                                benchmark_display=benchmark_display,
                                metric=metric_name,
                                category=category_name,
                                subset=subset_name,
                                num_samples=safe_int(subset_entry.get("num"))
                                or safe_int(category_entry.get("num")),
                                score=safe_float(subset_entry.get("score")),
                                run_id=run_id,
                                run_key=run_key,
                                artifact_path=artifact_path,
                                public_artifact_path=public_artifact_path,
                                public_meta_path=public_meta_path,
                                is_overall=False,
                            )
                        )
                    continue

                if category_name and category_name.lower() != "default":
                    records.append(
                        build_xeval_record(
                            model=model_name,
                            mode=mode,
                            benchmark=benchmark,
                            benchmark_display=benchmark_display,
                            metric=metric_name,
                            category=category_name,
                            subset=category_name,
                            num_samples=safe_int(category_entry.get("num")),
                            score=safe_float(category_entry.get("score")),
                            run_id=run_id,
                            run_key=run_key,
                            artifact_path=artifact_path,
                            public_artifact_path=public_artifact_path,
                            public_meta_path=public_meta_path,
                            is_overall=False,
                        )
                    )

    return records, warnings, skipped, used


def parse_bfcl_subset(filename: str) -> str:
    mapping = {
        "data_live.csv": "live",
        "data_non_live.csv": "non_live",
        "data_multi_turn.csv": "multi_turn",
    }
    return mapping.get(filename, Path(filename).stem)


def extract_bfcl_records(
    run_settings: dict[str, dict[str, Any]],
    artifacts: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str], int]:
    records: list[dict[str, Any]] = []
    warnings: list[str] = []
    used = 0

    if not BFCL_ROOT.exists():
        return records, warnings, used

    for csv_path in sorted(BFCL_ROOT.glob("**/score/*.csv")):
        rel_parts = csv_path.relative_to(BFCL_ROOT).parts
        if len(rel_parts) < 5:
            warnings.append(
                f"Unexpected bfcl_v3 directory shape for {relative_posix(csv_path)}"
            )
            continue

        model, raw_mode, run_id = rel_parts[0], rel_parts[1], rel_parts[2]
        mode = normalize_mode_label(raw_mode)
        subset = parse_bfcl_subset(csv_path.name)
        artifact_path = relative_posix(csv_path)
        public_artifact_path = build_public_artifact_path(
            model, "bfcl_v3", mode, run_id, f"{subset}.csv"
        )
        public_meta_path = make_public_meta_path(public_artifact_path)

        run_key = ensure_run_setting(
            run_settings,
            model=model,
            mode=mode,
            run_id=run_id,
            benchmark="bfcl_v3",
            config_excerpt={},
            public_meta_path=public_meta_path,
        )
        register_artifact(
            artifacts,
            artifact_path=artifact_path,
            public_artifact_path=public_artifact_path,
            public_meta_path=public_meta_path,
            model=model,
            benchmark="bfcl_v3",
            benchmark_display="BFCL v3",
            mode=mode,
            run_id=run_id,
            config_excerpt={},
        )

        try:
            with csv_path.open(newline="") as handle:
                reader = csv.DictReader(handle)
                rows = list(reader)
        except OSError as exc:
            warnings.append(f"Could not read {artifact_path}: {exc}")
            continue

        if not rows:
            warnings.append(f"No rows found in {artifact_path}")
            continue

        used += 1
        for row in rows:
            for key, raw_value in row.items():
                if key in {"Rank", "Model"}:
                    continue
                score = safe_float(raw_value)
                records.append(
                    {
                        "record_id": make_record_id(
                            "bfcl_v3",
                            artifact_path,
                            key,
                            subset,
                            subset,
                            run_id,
                        ),
                        "source": "bfcl_v3",
                        "model": model,
                        "mode": mode,
                        "benchmark": "bfcl_v3",
                        "benchmark_display": "BFCL v3",
                        "metric": key,
                        "category": subset,
                        "subset": subset,
                        "num_samples": None,
                        "score": score,
                        "score_unit": "percent",
                        "is_overall": "overall" in key.lower(),
                        "run_id": run_id,
                        "run_key": run_key,
                        "run_sort_value": parse_run_sort_value(run_id),
                        "artifact_path": artifact_path,
                        "public_artifact_path": public_artifact_path,
                        "public_meta_path": public_meta_path,
                    }
                )

    return records, warnings, used


def finalize_run_settings(
    run_settings: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    finalized: dict[str, dict[str, Any]] = {}
    for run_key, entry in run_settings.items():
        finalized[run_key] = {
            "run_key": entry["run_key"],
            "model": entry["model"],
            "mode": entry["mode"],
            "run_id": entry["run_id"],
            "run_sort_value": entry["run_sort_value"],
            "benchmarks": sorted(entry["benchmarks"], key=str.lower),
            "benchmark_count": len(entry["benchmarks"]),
            "config_excerpt": dict(entry["config_excerpt"]),
            "public_meta_path": entry["public_meta_path"],
        }
    return finalized


def collect_results_bundle() -> dict[str, Any]:
    run_settings: dict[str, dict[str, Any]] = {}
    artifacts: dict[str, dict[str, Any]] = {}

    xeval_records, xeval_warnings, xeval_skipped, xeval_used = extract_xeval_records(
        run_settings, artifacts
    )
    bfcl_records, bfcl_warnings, bfcl_used = extract_bfcl_records(
        run_settings, artifacts
    )

    records = xeval_records + bfcl_records
    records.sort(
        key=lambda item: (
            item["model"].lower(),
            item["benchmark"].lower(),
            item["mode"].lower(),
            -(item["run_sort_value"] or 0),
            item["run_id"].lower(),
            item["metric"].lower(),
            item["category"].lower(),
            item["subset"].lower(),
        )
    )

    warnings = xeval_warnings + bfcl_warnings
    duplicate_ids = sorted(
        record_id
        for record_id, count in Counter(
            record["record_id"] for record in records
        ).items()
        if count > 1
    )
    if duplicate_ids:
        warnings.append(f"Duplicate record ids detected: {len(duplicate_ids)}")

    finalized_run_settings = finalize_run_settings(run_settings)

    return {
        "generated_at": now_utc_iso(),
        "records": records,
        "artifacts": sorted(
            artifacts.values(),
            key=lambda item: (
                item["model"].lower(),
                item["benchmark"].lower(),
                item["mode"].lower(),
                -(parse_run_sort_value(item["run_id"]) or 0),
                item["run_id"].lower(),
            ),
        ),
        "run_settings": finalized_run_settings,
        "warnings": warnings,
        "exclusions": {
            "benchmark_file_excludes": sorted(XEVAL_EXACT_EXCLUDES),
            "benchmark_keyword_excludes": list(XEVAL_KEYWORD_EXCLUDES),
        },
        "summary": {
            "record_count": len(records),
            "artifact_count": len(artifacts),
            "run_count": len(finalized_run_settings),
            "model_count": len({record["model"] for record in records}),
            "benchmark_count": len({record["benchmark"] for record in records}),
            "xeval_reports_used": xeval_used,
            "xeval_reports_skipped": xeval_skipped,
            "bfcl_csv_files_used": bfcl_used,
            "warning_count": len(warnings),
        },
    }


def materialize_public_results(
    bundle: dict[str, Any],
) -> None:
    meta_payloads: dict[str, dict[str, Any]] = {}
    run_settings = bundle["run_settings"]

    if PUBLIC_RESULTS_ROOT.exists():
        shutil.rmtree(PUBLIC_RESULTS_ROOT)

    for artifact in bundle["artifacts"]:
        source_path = REPO_ROOT / artifact["artifact_path"]
        dest_path = REPO_ROOT / artifact["public_artifact_path"]
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, dest_path)

        run_setting = run_settings.get(
            make_run_key(artifact["model"], artifact["mode"], artifact["run_id"])
        )
        meta_path = REPO_ROOT / artifact["public_meta_path"]
        meta_key = relative_posix(meta_path)
        meta_payload = meta_payloads.setdefault(
            meta_key,
            {
                "model": artifact["model"],
                "benchmark": artifact["benchmark"],
                "benchmark_display": artifact["benchmark_display"],
                "mode": artifact["mode"],
                "run_id": artifact["run_id"],
                "config_excerpt": (
                    dict(run_setting["config_excerpt"]) if run_setting else {}
                ),
                "artifacts": [],
            },
        )
        meta_payload["artifacts"].append(artifact["public_artifact_path"])

    for meta_key, meta_payload in meta_payloads.items():
        meta_path = REPO_ROOT / meta_key
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        meta_path.write_text(json.dumps(meta_payload, ensure_ascii=False, indent=2) + "\n")


def build_public_summary(bundle: dict[str, Any]) -> dict[str, Any]:
    summary = bundle["summary"]
    return {
        "record_count": summary["record_count"],
        "artifact_count": summary["artifact_count"],
        "run_count": summary["run_count"],
        "model_count": summary["model_count"],
        "benchmark_count": summary["benchmark_count"],
        "json_artifact_count": summary["xeval_reports_used"],
        "csv_artifact_count": summary["bfcl_csv_files_used"],
        "skipped_invalid_file_count": summary["xeval_reports_skipped"],
        "warning_count": summary["warning_count"],
    }


def build_public_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    public_records = []
    for record in bundle["records"]:
        public_record_id = "::".join(
            [
                "public",
                record["public_artifact_path"],
                record["run_id"],
                record["metric"],
                record["category"] or "",
                record["subset"] or "",
            ]
        )
        public_records.append(
            {
                "record_id": public_record_id,
                "model": record["model"],
                "mode": record["mode"],
                "benchmark": record["benchmark"],
                "benchmark_display": record["benchmark_display"],
                "metric": record["metric"],
                "category": record["category"],
                "subset": record["subset"],
                "num_samples": record["num_samples"],
                "score": record["score"],
                "score_unit": record["score_unit"],
                "is_overall": record["is_overall"],
                "run_id": record["run_id"],
                "run_key": record["run_key"],
                "public_artifact_path": record["public_artifact_path"],
                "public_meta_path": record["public_meta_path"],
            }
        )

    return {
        "generated_at": bundle["generated_at"],
        "summary": build_public_summary(bundle),
        "exclusions": dict(bundle["exclusions"]),
        "run_settings": bundle["run_settings"],
        "artifacts": [
            {
                "public_artifact_path": artifact["public_artifact_path"],
                "public_meta_path": artifact["public_meta_path"],
                "model": artifact["model"],
                "benchmark": artifact["benchmark"],
                "benchmark_display": artifact["benchmark_display"],
                "mode": artifact["mode"],
                "run_id": artifact["run_id"],
            }
            for artifact in bundle["artifacts"]
        ],
        "records": public_records,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract safe result rows from raw xeval and bfcl_v3 outputs."
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional JSON output path for the public-safe extracted bundle.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON when --output is set.",
    )
    parser.add_argument(
        "--materialize-public-results",
        action="store_true",
        help="Copy safe raw artifacts into published_results/ using the public layout.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    bundle = collect_results_bundle()
    summary = bundle["summary"]

    if args.materialize_public_results:
        materialize_public_results(bundle)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        indent = 2 if args.pretty else None
        public_bundle = build_public_bundle(bundle)
        args.output.write_text(
            json.dumps(public_bundle, ensure_ascii=False, indent=indent) + "\n"
        )
        print(f"Wrote extracted bundle to {relative_posix(args.output)}")

    print(
        "Extracted "
        f"{summary['record_count']} records from "
        f"{summary['xeval_reports_used']} xeval reports and "
        f"{summary['bfcl_csv_files_used']} bfcl_v3 CSV files "
        f"({summary['xeval_reports_skipped']} xeval reports skipped by rule)."
    )

    if bundle["warnings"]:
        print("Warnings:")
        for warning in bundle["warnings"]:
            print(f"- {warning}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
