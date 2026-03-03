import os
from argparse import ArgumentParser

from evalscope import TaskConfig, run_task

DEFAULT_MAX_TOKENS = 16384
AIME_MAX_TOKENS = 16384 + 4096

GEN_CONFIG = {
    "do_sample": False,
    "temperature": 0.0,
    "max_tokens": DEFAULT_MAX_TOKENS,
}

MATH_GEN_CONFIG = {
    "do_sample": False,
    "temperature": 0.0,
    "max_tokens": AIME_MAX_TOKENS,
}

def get_args():
    parser = ArgumentParser()
    parser.add_argument("--base-path", type=str, required=True)
    parser.add_argument("--model-name", type=str, required=True)
    return parser.parse_args()

def run(args):
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
                },
                "simple_qa": {
                    "dataset_id": os.path.join(
                        args.base_path,
                        "datasets/benchmarks/evalscope/SimpleQA",
                    ),
                },
                "mmlu_pro": {
                    "dataset_id": os.path.join(
                        args.base_path,
                        "datasets/benchmarks/MMLU-Pro",
                    ),
                }
            },
            generation_config=GEN_CONFIG,
            work_dir=os.path.join(
                args.base_path,
                f"evalscope_workdir/xeval/{args.model_name}",
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
                }
            },
            generation_config=GEN_CONFIG,
            work_dir=os.path.join(
                args.base_path,
                f"evalscope_workdir/xeval/{args.model_name}",
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
                },
            },
            generation_config=GEN_CONFIG,
            work_dir=os.path.join(
                args.base_path,
                f"evalscope_workdir/xeval/{args.model_name}",
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
                },
                "aime25": {
                    "dataset_id": os.path.join(
                        args.base_path,
                        "datasets/benchmarks/AIME2025",
                    ),
                },
                "hmmt25":{
                    "dataset_id": os.path.join(
                        args.base_path,
                        "datasets/benchmarks/MathArena/hmmt_feb_2025",
                    ),
                }
            },
            generation_config=MATH_GEN_CONFIG,
            work_dir=os.path.join(
                args.base_path,
                f"evalscope_workdir/xeval/{args.model_name}",
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
                }
            },
            generation_config=GEN_CONFIG,
            work_dir=os.path.join(
                args.base_path,
                f"evalscope_workdir/xeval/{args.model_name}",
            ),
        ),
    ]

    for task_cfg in task_cfgs:
        run_task(task_cfg=task_cfg)


if __name__ == "__main__":
    args = get_args()
    run(args)

