#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

from extract_results import (
    PUBLIC_RESULTS_ROOT,
    REPO_ROOT,
    SAFE_GENERATION_CONFIG_KEYS,
    SAFE_TOP_LEVEL_CONFIG_KEYS,
    XEVAL_EXACT_EXCLUDES,
    XEVAL_KEYWORD_EXCLUDES,
    collect_results_bundle,
)

SITE_DATA_ROOT = REPO_ROOT / "site" / "data"
REQUIRED_ROOT_FILES = [
    SITE_DATA_ROOT / "index.json",
    SITE_DATA_ROOT / "protocol.json",
    SITE_DATA_ROOT / "detailed_results.json",
    SITE_DATA_ROOT / "site_data.json",
]
CATEGORY_FILES = [
    SITE_DATA_ROOT / "categories" / "knowledge.json",
    SITE_DATA_ROOT / "categories" / "agentic.json",
    SITE_DATA_ROOT / "categories" / "instruction_following.json",
    SITE_DATA_ROOT / "categories" / "reasoning.json",
]
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


def benchmark_is_forbidden(name: str) -> bool:
    lowered = name.lower()
    if lowered in XEVAL_EXACT_EXCLUDES:
        return True
    return any(keyword in lowered for keyword in XEVAL_KEYWORD_EXCLUDES)


def load_json(path: Path, errors: list[str]) -> dict | list | None:
    if not path.exists():
        errors.append(f"Missing required JSON: {path.relative_to(REPO_ROOT)}")
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        errors.append(f"Invalid JSON in {path.relative_to(REPO_ROOT)}: {exc}")
        return None


def main() -> int:
    bundle = collect_results_bundle()
    records = bundle["records"]
    errors: list[str] = []

    if not records:
        errors.append("No result records were extracted.")

    duplicate_ids = [
        record_id
        for record_id, count in Counter(
            record["record_id"] for record in records
        ).items()
        if count > 1
    ]
    if duplicate_ids:
        errors.append(f"Duplicate record ids found: {len(duplicate_ids)}")

    for record in records:
        artifact_path = record["artifact_path"]
        artifact = REPO_ROOT / artifact_path
        if not artifact.exists():
            errors.append(f"Missing artifact file: {artifact_path}")
        if "/configs/" in artifact_path or artifact_path.endswith((".yaml", ".yml")):
            errors.append(f"Unsafe config reference leaked into records: {artifact_path}")
        if "/logs/" in artifact_path or artifact_path.endswith(".log"):
            errors.append(f"Unsafe log reference leaked into records: {artifact_path}")
        if record["source"] == "xeval" and benchmark_is_forbidden(record["benchmark"]):
            errors.append(
                f"Forbidden xeval benchmark was extracted: {record['benchmark']}"
            )

    for run_setting in bundle["run_settings"].values():
        config_excerpt = run_setting["config_excerpt"]
        for key in config_excerpt:
            if key == "generation_config":
                continue
            if key not in SAFE_TOP_LEVEL_CONFIG_KEYS:
                errors.append(f"Unsafe config key surfaced: {key}")
        generation_config = config_excerpt.get("generation_config", {})
        for key in generation_config:
            if key not in SAFE_GENERATION_CONFIG_KEYS:
                errors.append(f"Unsafe generation config key surfaced: {key}")

    for path in REQUIRED_ROOT_FILES + CATEGORY_FILES:
        load_json(path, errors)

    benchmark_files = sorted((SITE_DATA_ROOT / "benchmarks").glob("*.json"))
    if not benchmark_files:
        errors.append("No benchmark detail files found under site/data/benchmarks.")

    for benchmark, category in BENCHMARK_CATEGORY.items():
        benchmark_path = SITE_DATA_ROOT / "benchmarks" / f"{benchmark}.json"
        payload = load_json(benchmark_path, errors)
        if not isinstance(payload, dict):
            continue
        if payload.get("category") != category:
            errors.append(
                f"Benchmark category mismatch for {benchmark}: "
                f"expected {category}, found {payload.get('category')}"
            )

    forbidden_fragments = [
        "results/xeval",
        "results/bfcl_v3",
        "/Users/",
        "http://",
        "https://",
        '"artifact_path"',
        '"source"',
        "configs/task_config",
        "eval_log.log",
    ]
    for json_path in SITE_DATA_ROOT.rglob("*.json"):
        text = json_path.read_text()
        for fragment in forbidden_fragments:
            if fragment in text:
                errors.append(
                    f"Public JSON leaks forbidden fragment {fragment!r}: "
                    f"{json_path.relative_to(REPO_ROOT)}"
                )

    index_payload = load_json(SITE_DATA_ROOT / "index.json", errors)
    if isinstance(index_payload, dict):
        category_summary = index_payload.get("category_summary", [])
        if len(category_summary) != 4:
            errors.append(
                "index.json should expose exactly 4 category summary entries."
            )

    protocol_payload = load_json(SITE_DATA_ROOT / "protocol.json", errors)
    if isinstance(protocol_payload, dict):
        if not protocol_payload.get("families"):
            errors.append("protocol.json contains no family rows.")

    if PUBLIC_RESULTS_ROOT.exists():
        unsafe_files = list(PUBLIC_RESULTS_ROOT.glob("**/*.yaml"))
        unsafe_files += list(PUBLIC_RESULTS_ROOT.glob("**/*.yml"))
        unsafe_files += list(PUBLIC_RESULTS_ROOT.glob("**/*.log"))
        if unsafe_files:
            errors.append(
                f"Unsafe files found under published_results: {len(unsafe_files)}"
            )

    if errors:
        print("Validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    summary = bundle["summary"]
    print(
        "Validation passed: "
        f"{summary['record_count']} records, "
        f"{summary['model_count']} models, "
        f"{summary['benchmark_count']} benchmarks."
    )
    if bundle["warnings"]:
        print(f"Warnings: {len(bundle['warnings'])}")
        for warning in bundle["warnings"]:
            print(f"- {warning}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
