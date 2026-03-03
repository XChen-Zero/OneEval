# OneEval

OneEval 是一个以仓库为中心发布的开放模型评测证据集。

它主要回应开源 LLM 评测中的两个长期问题：

- 很多结果很难复现，因为论文或官方报告没有把完整评测设置讲清楚
- 很多 benchmark 只公开一个 headline score，却隐藏了 subset 级别的内部表现

OneEval 使用 EvalScope 跑一套统一的开源模型评测，然后把通常缺失的关键信息一起公开出来：启动脚本、采样协议、以及细粒度评测结果。

这个仓库**不是**排行榜。它的定位是一个面向复查、复用和审阅的评测证据发布仓库。

**作者**

- Xuan Chen (<chenxuan026@icloud.com>)
- Qiuxuan Chen (<482501090@qq.com>)
- Bo Liu (<mjv1cp@gmail.com>)

## 仓库公开了什么

- [published_results/](published_results/): 对外公开的结果目录，统一组织为 `models/<model>/<benchmark>/<mode>/<run_id>/`
- [site/](site/): 面向 GitHub Pages 的静态展示站
- [site/data/detailed_results.json](site/data/detailed_results.json): 站点使用的详细结果行
- [evaluation_code/](evaluation_code/): 实际用于运行评测的启动脚本和针对官方代码的最小 monkey patch
- [evaluation_code/oneeval/](evaluation_code/oneeval/): OneEval 自己的 EvalScope 启动与组织脚本
- [scripts/extract_results.py](scripts/extract_results.py): 提取有效结果、脱敏配置、生成 `published_results/`
- [scripts/build_site_data.py](scripts/build_site_data.py): 重建站点数据
- [scripts/validate_raw_results.py](scripts/validate_raw_results.py): 做一致性与泄露检查

站点按四类阅读路径组织结果：

- Knowledge
- Agentic
- IF（Instruction Following）
- Reasoning

## 为什么这个仓库有价值

很多公开 benchmark 报告只给一个平均分，但 benchmark 本身的结构远比平均分丰富。例如：

- MMLU-Pro 往往只公开 overall score，但实际包含大量 domain subset
- AIME 一类数学 reasoning benchmark 经常只强调 `pass@64` 或一个平均值，而不是完整曲线

OneEval 的目标，就是把这些被压扁的信息重新展开，让人真正看见：

- 到底跑了什么
- 用了什么采样设置
- 每个 benchmark 在内部是如何分解的

## 评测栈版本

本次发布对应的关键运行栈如下：

- EvalScope: `1.4.1`
- BFCL Eval: `2026.2.9`
- Qwen3 系列与 Llama 系列本地推理：`sglang 0.5.6`
- Qwen3 系列与 Llama 系列 agent 工具：`qwen_agent 0.0.31`
- Qwen3.5 系列推理路径：DashScope 接口
- Qwen3.5 系列 agent 工具：`qwen_agent 0.0.34`

补充说明：

- Qwen3 系列（包括 DeepSeek-R1-Qwen3）使用统一的采样协议
- Llama 系列在当前发布中采用固定的单次重复设置
- BFCL v3 的 agentic 评测在适用场景下使用 `131072` 的 YaRN 扩展上下文

## 安全边界

原始私有结果目录可能包含本地路径、内部名称、配置文件和日志，这些都不应该被公开。OneEval 将原始源仅作为构建输入，不直接对外发布。

真正对外发布的只有：

- [published_results/](published_results/)
- [site/data/](site/data/)
- [site/](site/)

构建过程不会公开原始 config 文件，只会提取白名单内的安全字段，例如：

- `evalscope_version`
- `eval_backend`
- `eval_batch_size`
- `eval_type`
- `judge_strategy`
- `limit`
- `debug`
- `generation_config` 中的 `temperature`、`top_p`、`top_k`、`max_tokens`、`do_sample` 等

已知无效或故意排除的来源会在发布前被过滤：

- xeval 中的 code 类 benchmark
- xeval 中的 `bfcl_v3`
- 文件名包含 `code`、`humaneval`、`mbpp`、`bfcl` 的 xeval 结果

## 如何重建发布内容

重建公开结果目录和站点数据：

```bash
.venv/bin/python scripts/build_site_data.py
```

运行一致性和泄露检查：

```bash
.venv/bin/python scripts/validate_raw_results.py
```

如果要导出平铺的提取结果：

```bash
.venv/bin/python scripts/extract_results.py --output site/data/extracted_results.json --pretty --materialize-public-results
```

本地预览站点：

```bash
.venv/bin/python -m http.server 8000
```

然后打开 `http://localhost:8000/site/`。

## 如何部署到 GitHub Pages

仓库里已经带了一个 GitHub Pages 工作流：[.github/workflows/deploy-pages.yml](.github/workflows/deploy-pages.yml)。它会直接把 `site/` 目录作为静态站点发布。

1. 将当前项目推到 GitHub 仓库。
2. 打开仓库的 `Settings` -> `Pages`。
3. 在 `Build and deployment` 中选择 `GitHub Actions`。
4. 提交并推送到默认分支。
5. `Deploy GitHub Pages` 工作流会自动上传 `site/` 并完成发布。

发布后，访问地址通常是：

```text
https://<你的 GitHub 用户名>.github.io/<你的仓库名>/
```

之后只要更新 [published_results/](published_results/) 、[site/](site/) 或 `site/data/` 下的数据，再提交并推送，GitHub Pages 就会重新发布。

## 项目边界

OneEval 刻意保持边界清晰：

- 不做排行榜
- 不做后端服务
- 不做数据库仓库层
- 不做隐藏的自动评测平台

核心目标只有一个：把评测证据以可检查、可复用、可追溯的方式公开出来。
