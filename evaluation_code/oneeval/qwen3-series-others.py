import os
from argparse import ArgumentParser

from evalscope import TaskConfig, run_task

DEFAULT_MAX_TOKENS = 32768
AIME_MAX_TOKENS = 38912

THINKING_GEN_CONFIG = {
    "temperature": 0.6,
    "top_p": 0.95,
    "top_k": 20,
    "max_tokens": DEFAULT_MAX_TOKENS,
}

NON_THINKING_GEN_CONFIG = {
    "temperature": 0.7,
    "top_p": 0.8,
    "top_k": 20,
    "max_tokens": DEFAULT_MAX_TOKENS,
}


def get_args():
    parser = ArgumentParser()
    parser.add_argument("--base-path", type=str, required=True)
    parser.add_argument("--model-name", type=str, required=True)
    parser.add_argument(
        "--track",
        type=str,
        choices=["thinking", "non_thinking"],
        default="thinking",
    )
    parser.add_argument("--enable-thinking", type=str, required=True, choices=["true", "false", "none"])
    parser.add_argument("--filter-thinking", action="store_true", default=False)
    return parser.parse_args()


def get_generation_config(track, enable_thinking="none", max_tokens=None, extra=None):
    config = {
        "do_sample": True,
    }
    if track == "thinking":
        config = dict(THINKING_GEN_CONFIG)
    else:
        config = dict(NON_THINKING_GEN_CONFIG)


    if enable_thinking == "true":
        config["extra_body"] = {"chat_template_kwargs": {"enable_thinking": True}}
    elif enable_thinking == "false":
        config["extra_body"] = {"chat_template_kwargs": {"enable_thinking": False}}
    else:
        assert enable_thinking == "none"

    if max_tokens is not None:
        config["max_tokens"] = max_tokens
    if extra:
        config.update(extra)
    return config


def get_filter_thinking_config(filter_thinking):
    if filter_thinking:
        return {
            "filters": {
                "remove_until": "</think>"
            }
        }
    return {}

def run(args):
    filter_thinking_config = get_filter_thinking_config(args.filter_thinking)
    task_cfgs = [
        # knowledge
        TaskConfig(
            model=args.model_name,
            api_url="http://0.0.0.0:8080/v1",
            api_key="EMPTY",
            eval_type="openai_api",
            eval_batch_size=10,
            datasets=[
                "chinese_simpleqa",
                "simple_qa",
                "mmlu_pro"
            ],
            dataset_args={
                "chinese_simpleqa": {
                    "dataset_id": os.path.join(
                        args.base_path,
                        "datasets/benchmarks/AI-ModelScope/Chinese-SimpleQA",
                    ),
                    **filter_thinking_config,
                },
                "simple_qa": {
                    "dataset_id": os.path.join(
                        args.base_path,
                        "datasets/benchmarks/evalscope/SimpleQA",
                    ),
                    **filter_thinking_config,
                },
                "mmlu_pro": {
                    "dataset_id": os.path.join(
                        args.base_path,
                        "datasets/benchmarks/MMLU-Pro",
                    ),
                    **filter_thinking_config,
                }
            },
            generation_config=get_generation_config(args.track, args.enable_thinking),
            work_dir=os.path.join(
                args.base_path,
                f"evalscope_workdir/xeval/{args.model_name}/{args.track}",
            ),
            judge_model_args={
                "api_key": os.getenv("JUDGE_MODEL_API_KEY", "EMPTY"),
                "api_url": os.getenv("JUDGE_MODEL_API_URL"),
                "model_id": os.getenv("JUDGE_MODEL_ID"),
            },
        ),
        TaskConfig(
            model=args.model_name,
            api_url="http://0.0.0.0:8080/v1",
            api_key="EMPTY",
            eval_type="openai_api",
            eval_batch_size=10,
            datasets=["gpqa_diamond"],
            dataset_args={
                "gpqa_diamond": {
                    "dataset_id": os.path.join(
                        args.base_path,
                        "datasets/benchmarks/AI-ModelScope/gpqa_diamond",
                    ),
                    **filter_thinking_config,
                }
            },
            generation_config=get_generation_config(args.track, args.enable_thinking),
            repeats=10,
            work_dir=os.path.join(
                args.base_path,
                f"evalscope_workdir/xeval/{args.model_name}/{args.track}",
            ),
        ),  
        # alignment
        TaskConfig(
            model=args.model_name,
            api_url="http://0.0.0.0:8080/v1",
            api_key="EMPTY",
            eval_type="openai_api",
            eval_batch_size=10,
            datasets=["ifeval"],
            dataset_args={
                "ifeval": {
                    "dataset_id": os.path.join(
                        args.base_path,
                        "datasets/benchmarks/ifeval",
                    ),
                    **filter_thinking_config,
                },
            },
            generation_config=get_generation_config(args.track, args.enable_thinking),
            work_dir=os.path.join(
                args.base_path,
                f"evalscope_workdir/xeval/{args.model_name}/{args.track}",
            ),
        ),
        # reasoning
        TaskConfig(
            model=args.model_name,
            api_url="http://0.0.0.0:8080/v1",
            api_key="EMPTY",
            eval_type="openai_api",
            eval_batch_size=10,
            datasets=["aime24", "aime25"],
            dataset_args={
                "aime24": {
                    "dataset_id": os.path.join(
                        args.base_path,
                        "datasets/benchmarks/aime_2024",
                    ),
                    "aggregation": "mean_and_pass_at_k",
                },
                "aime25": {
                    "dataset_id": os.path.join(
                        args.base_path,
                        "datasets/benchmarks/AIME2025",
                    ),
                    "aggregation": "mean_and_pass_at_k",
                },
                "hmmt25":{
                    "dataset_id": os.path.join(
                        args.base_path,
                        "datasets/benchmarks/MathArena/hmmt_feb_2025",
                    ),
                    "aggregation": "mean_and_pass_at_k",
                }
            },
            generation_config=get_generation_config(
                args.track,
                args.enable_thinking,
                max_tokens=AIME_MAX_TOKENS,
            ),
            repeats=64,
            work_dir=os.path.join(
                args.base_path,
                f"evalscope_workdir/xeval/{args.model_name}/{args.track}",
            ),
        ),
        TaskConfig(
            model=args.model_name,
            api_url="http://0.0.0.0:8080/v1",
            api_key="EMPTY",
            eval_type="openai_api",
            eval_batch_size=10,
            datasets=["zebralogicbench"],
            dataset_args={
                "zebralogicbench": {
                    "dataset_id": os.path.join(
                        args.base_path,
                        "datasets/benchmarks/allenai/ZebraLogicBench-private",
                    ),
                    **filter_thinking_config,
                }
            },
            generation_config=get_generation_config(args.track, args.enable_thinking),
            work_dir=os.path.join(
                args.base_path,
                f"evalscope_workdir/xeval/{args.model_name}/{args.track}",
            ),
        ),
    ]

    for task_cfg in task_cfgs:
        run_task(task_cfg=task_cfg)


if __name__ == "__main__":
    args = get_args()
    run(args)

