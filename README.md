# OneEval

OneEval is a repository-first release of open-model evaluation evidence.

中文说明见 [README.zh-CN.md](README.zh-CN.md).

**Authors**

- Xuan Chen (<chenxuan026@icloud.com>)
- Qiuxuan Chen (<482501090@qq.com>)
- Bo Liu (<mjv1cp@gmail.com>)

The project exists to address two recurring problems in open LLM evaluation:

- results that are difficult to reproduce because the exact evaluation setup is underspecified
- benchmark reports that publish only headline aggregates while hiding subset-level behavior

OneEval uses EvalScope to run a unified suite across open Llama, Qwen, DeepSeek-R1-Qwen3, and Qwen3.5 models, then publishes the pieces that are usually missing from benchmark releases: launch scripts, protocol assumptions, and detailed result slices.

This repository is intentionally **not** a leaderboard. It is a publication surface for reproducible evaluation artifacts.

## What This Repository Publishes

- [published_results/](published_results/): the public result tree, organized as `models/<model>/<benchmark>/<mode>/<run_id>/`
- [site/](site/): a GitHub Pages-friendly static site for browsing results by benchmark type
- [site/data/detailed_results.json](site/data/detailed_results.json): detailed rows used by the site
- [evaluation_code/](evaluation_code/): the launch scripts and targeted monkey patches used to run the evaluations
- [evaluation_code/oneeval/](evaluation_code/oneeval/): OneEval-side EvalScope launch entrypoints and orchestration scripts
- [scripts/extract_results.py](scripts/extract_results.py): extracts valid artifacts, sanitizes config metadata, and materializes `published_results/`
- [scripts/build_site_data.py](scripts/build_site_data.py): rebuilds the static site data bundles
- [scripts/validate_raw_results.py](scripts/validate_raw_results.py): verifies consistency and checks for leaks

The public site separates results into four academic reading tracks:

- Knowledge
- Agentic
- IF (Instruction Following)
- Reasoning

## Why OneEval Is Useful

Most public benchmark writeups stop at a single average, even when the benchmark itself contains much richer structure. This is common in:

- MMLU-Pro, where many reports show only one overall score while domain subsets remain hidden
- AIME-style reasoning benchmarks, where papers often emphasize `pass@64` or one aggregate instead of the full curve

OneEval keeps those internal distributions visible. The release is meant to answer:

- what was actually run
- with which sampling assumptions
- and how the result decomposes beyond one headline number

## Evaluation Stack

The evaluation stack used in this release is fixed and should be read as part of the methodology:

- EvalScope: `1.4.1`
- BFCL Eval: `2026.2.9`
- Qwen3 series and Llama family local serving: `sglang 0.5.6`
- Qwen3 series and Llama family agent tooling: `qwen_agent 0.0.31`
- Qwen3.5 series inference path: DashScope-compatible API
- Qwen3.5 series agent tooling: `qwen_agent 0.0.34`

Operational notes:

- Qwen3 family models, including DeepSeek-R1-Qwen3 variants, are evaluated under the unified sampling protocol documented in the site.
- Llama-family runs use fixed single-repeat settings where the sampling configuration is deterministic.
- BFCL v3 agentic evaluation uses a YaRN-extended context setup to `131072` where applicable.

## Security Boundary

The private raw source tree may contain local paths, internal names, and config/log material that must not be published. OneEval treats that raw tree as a build input only.

Public outputs are restricted to:

- sanitized result files copied into [published_results/](published_results/)
- derived site data under [site/data/](site/data/)
- the static frontend under [site/](site/)

The build pipeline never publishes raw config files. It only extracts a strict allowlist of safe evaluation metadata, such as:

- `evalscope_version`
- `eval_backend`
- `eval_batch_size`
- `eval_type`
- `judge_strategy`
- `limit`
- `debug`
- selected `generation_config` fields like `temperature`, `top_p`, `top_k`, `max_tokens`, and `do_sample`

Known invalid or intentionally excluded sources are filtered out before publication:

- xeval code-style benchmarks
- xeval `bfcl_v3`
- xeval files whose names contain `code`, `humaneval`, `mbpp`, or `bfcl`

## Rebuild The Release

Rebuild the public result tree and site data:

```bash
.venv/bin/python scripts/build_site_data.py
```

Run the consistency and leakage checks:

```bash
.venv/bin/python scripts/validate_raw_results.py
```

If you need the extracted flat bundle for debugging:

```bash
.venv/bin/python scripts/extract_results.py --output site/data/extracted_results.json --pretty --materialize-public-results
```

Preview the site locally:

```bash
.venv/bin/python -m http.server 8000
```

Then open `http://localhost:8000/site/`.

## Deploy To GitHub Pages

This repository includes a GitHub Pages workflow at [.github/workflows/deploy-pages.yml](.github/workflows/deploy-pages.yml). It publishes the `site/` directory directly through GitHub Actions.

1. Push this project to a GitHub repository.
2. In GitHub, open `Settings` -> `Pages`.
3. Under `Build and deployment`, choose `GitHub Actions`.
4. Commit and push to your default branch.
5. The `Deploy GitHub Pages` workflow will upload `site/` and publish it automatically.

After the first successful run, the site will be served from:

```text
https://<your-github-username>.github.io/<your-repository-name>/
```

Any later commit that updates [published_results/](published_results/), [site/](site/), or the generated data under `site/data/` will trigger a new deployment.

## Scope

OneEval keeps the release deliberately narrow:

- no leaderboard
- no backend service
- no normalized warehouse layer
- no hidden evaluation pipeline

The point is simple: publish the evaluation evidence in a form that is inspectable, structured, and reusable.
