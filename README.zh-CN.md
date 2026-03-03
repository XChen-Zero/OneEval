# OneEval

![OneEval logo](assets/logo.png)

OneEval 是一个以仓库为中心发布的开放模型评测产物（artifacts）集合。

## 动机

在开源 LLM 评测中，结果经常难以审阅、也难以复现。常见的两个缺口是：

- 评测协议（采样参数、重复次数、运行假设）信息不足，导致复现困难
- 丰富 benchmark 往往被压缩为单一 headline score，掩盖了 subset 结构（如 MMLU-Pro 领域划分）或多采样行为（如 pass@k 曲线）

OneEval 以证据链的方式发布用于审阅的必要信息：运行脚本、脱敏后的协议摘要，以及解释 overall 数值来源的细粒度结果切片。

**作者**

- Xuan Chen (<chenxuan026@icloud.com>)
- Qiuxuan Chen (<482501090@qq.com>)
- Bo Liu (<mjv1cp@gmail.com>)

**项目站点**

- https://XChen-Zero.github.io/OneEval/

## 项目边界

本仓库不做排行榜，也不发布综合分。重点在于产物发布与可审阅性，而不是排名。

## 发布内容

- [published_results/](published_results/): 对外公开的结果目录，统一组织为 `models/<model>/<benchmark>/<mode>/<run_id>/`
- [site/](site/): 静态展示站（GitHub Pages），按 benchmark 类型组织
- [site/data/](site/data/): 站点数据包，由公开结果派生
- [evaluation_code/](evaluation_code/): 实际用于运行评测的启动脚本和最小 monkey patch
- [scripts/](scripts/): 提取、构建站点数据、以及校验工具

## 阅读方式（站点）

站点按四类阅读路径组织结果，并使用 benchmark 语义化表格呈现：

- Knowledge
- Agentic
- IF（Instruction Following）
- Reasoning

表格呈现原则：

- QA 类型 benchmark 明确展示 `Correct / Incorrect / Abstain`
- subset-heavy benchmark 使用 overall 主表，并提供 subset drilldown
- pass@k benchmark 展示里程碑（k=1/8/32/64）并提供交互式曲线

## 本次发布包含的 benchmark

当前站点数据中包含的 benchmark（按阅读路径归类）：

- Knowledge: `chinese_simpleqa`, `gpqa_diamond`, `mmlu_pro`, `simple_qa`, `super_gpqa`
- Agentic: `bfcl_v3`
- IF: `ifeval`
- Reasoning: `aime24`, `aime25`, `hmmt25`, `zebralogicbench`

## 评测栈版本

本次发布的关键运行栈如下：

- EvalScope: `1.4.1`
- BFCL Eval: `2026.2.9`
- Qwen3 系列与 Llama 系列本地推理：`sglang 0.5.6`
- Qwen3 系列与 Llama 系列 agent 工具：`qwen_agent 0.0.31`
- Qwen3.5 系列推理路径：DashScope 接口
- Qwen3.5 系列 agent 工具：`qwen_agent 0.0.34`

补充说明（对应站点中的协议摘要）：

- Qwen3 系列（包括 DeepSeek-R1-Qwen3）使用统一的采样协议
- Llama 系列在当前发布中采用固定的单次重复设置
- BFCL v3 的 agentic 评测在适用场景下使用 `131072` 的 YaRN 扩展上下文


## 关于重建

本仓库已经包含物化后的公开发布内容（`published_results/` 与 `site/data/`）。[scripts/](scripts/) 下的构建脚本主要面向维护者，用于在持有对应原始输入时重新生成发布内容。

对开源读者的本地验证建议：

```bash
.venv/bin/python scripts/validate_raw_results.py
```

本地预览站点：

```bash
.venv/bin/python -m http.server 8000
```

然后打开 `http://localhost:8000/site/`。

## Citation

如果你在报告或二次分析中使用 OneEval，请引用该仓库：


```bibtex
@misc{oneeval,
  title        = {OneEval: Open-model evaluation artifacts},
  author       = {Chen, Xuan and Chen, Qiuxuan and Liu, Bo},
  year         = {2026},
  howpublished = {GitHub repository},
  note         = {Accessed: 2026-03-03},
  url          = {https://github.com/XChen-Zero/OneEval/}
}
```
