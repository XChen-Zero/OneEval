const SVG_NS = "http://www.w3.org/2000/svg";
const CATEGORY_META = {
  knowledge: {
    label: "Knowledge",
    emphasis: "Subset-heavy factual evaluation",
  },
  agentic: {
    label: "Agentic",
    emphasis: "BFCL workflow and task execution",
  },
  instruction_following: {
    label: "IF",
    emphasis: "Instruction-following compliance evaluation",
  },
  reasoning: {
    label: "Reasoning",
    emphasis: "Pass@k math and logic evaluation",
  },
};
const QA_BREAKDOWN_BENCHMARKS = new Set(["chinese_simpleqa", "simple_qa"]);
const QA_BREAKDOWN_LABELS = ["Correct", "Incorrect", "Abstain"];
const BFCL_BENCHMARK = "bfcl_v3";
const BFCL_OVERALL_LABELS = [
  "Live Overall Acc",
  "Non-Live Overall Acc",
  "Multi Turn Overall Acc",
];
const BFCL_SUBSET_METRIC_ORDER = {
  live: [
    "Relevance Detection",
    "Irrelevance Detection",
    "AST Summary",
    "Python Simple AST",
    "Python Multiple AST",
    "Python Parallel AST",
    "Python Parallel Multiple AST",
  ],
  non_live: [
    "Irrelevance Detection",
    "AST Summary",
    "Simple AST",
    "Python Simple AST",
    "Java Simple AST",
    "JavaScript Simple AST",
    "Multiple AST",
    "Parallel AST",
    "Parallel Multiple AST",
  ],
  multi_turn: [
    "Base",
    "Long Context",
    "Miss Func",
    "Miss Param",
  ],
};
const IFEVAL_BENCHMARK = "ifeval";
const IFEVAL_LABELS = [
  "mean inst level loose",
  "mean inst level strict",
  "mean prompt level loose",
  "mean prompt level strict",
];
const ZEBRA_BENCHMARK = "zebralogicbench";
const ZEBRA_LABELS = [
  "puzzle acc",
  "cell acc",
  "easy puzzle acc",
  "medium puzzle acc",
  "hard puzzle acc",
  "large puzzle acc",
  "xl puzzle acc",
  "avg reason lens",
  "no answer num",
];
const ZEBRA_SUMMARY_LABELS = [
  "puzzle acc",
  "cell acc",
  "xl puzzle acc",
  "avg reason lens",
  "no answer num",
];
const PASS_MILESTONE_COLUMNS = ["k=1", "k=8", "k=32", "k=64", "Gain"];

const homeElements = {
  generatedAt: document.getElementById("generated-at"),
  recordCount: document.getElementById("home-record-count"),
  runCount: document.getElementById("home-run-count"),
  modelCount: document.getElementById("home-model-count"),
  benchmarkCount: document.getElementById("home-benchmark-count"),
  artifactCount: document.getElementById("home-artifact-count"),
  overallCount: document.getElementById("home-overall-count"),
  subsetCount: document.getElementById("home-subset-count"),
  excludedNote: document.getElementById("excluded-note"),
  protocolGroups: document.getElementById("protocol-groups"),
  categoryGrid: document.getElementById("category-grid"),
  featuredList: document.getElementById("featured-list"),
  detailedResultsLink: document.getElementById("detailed-results-link"),
  publicResultsLink: document.getElementById("public-results-link"),
  flatBundleLink: document.getElementById("flat-bundle-link"),
};

const categoryElements = {
  generatedAt: document.getElementById("page-generated-at"),
  description: document.getElementById("category-description"),
  benchmarkCount: document.getElementById("category-benchmark-count"),
  sectionCount: document.getElementById("section-count"),
  sectionsRoot: document.getElementById("sections-root"),
  model: document.getElementById("filter-model"),
  mode: document.getElementById("filter-mode"),
  benchmark: document.getElementById("filter-benchmark"),
  sort: document.getElementById("filter-sort"),
  reset: document.getElementById("reset-filters"),
};

const categoryState = {
  payload: null,
  filters: {
    model: "",
    mode: "",
    benchmark: "",
    sort: "score_desc",
  },
  detailCache: new Map(),
  openDetails: new Set(),
};

function isHomePage() {
  return document.body.dataset.page === "home";
}

function isCategoryPage() {
  return document.body.dataset.page === "category";
}

async function fetchJson(path) {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.json();
}

function createNode(tag, className, text) {
  const node = document.createElement(tag);
  if (className) {
    node.className = className;
  }
  if (text !== undefined) {
    node.textContent = text;
  }
  return node;
}

function createEmptyNote(message) {
  return createNode("div", "empty-note", message);
}

function optionNodes(values) {
  const base = document.createElement("option");
  base.value = "";
  base.textContent = "All";
  const nodes = [base];

  values.forEach((value) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    nodes.push(option);
  });
  return nodes;
}

function setSelectOptions(element, values) {
  if (!element) {
    return;
  }
  element.replaceChildren(...optionNodes(values));
}

function setBenchmarkOptions(element, entries) {
  if (!element) {
    return;
  }

  const base = document.createElement("option");
  base.value = "";
  base.textContent = "All";
  const nodes = [base];

  entries.forEach((entry) => {
    const option = document.createElement("option");
    option.value = entry.benchmark;
    option.textContent = entry.display_name;
    nodes.push(option);
  });
  element.replaceChildren(...nodes);
}

function formatNum(value) {
  if (value === null || value === undefined) {
    return "—";
  }
  return new Intl.NumberFormat("en-US").format(value);
}

function relativeLink(path) {
  if (!path) {
    return "#";
  }
  if (path === "published_results" || path.startsWith("published_results/")) {
    return `../${path}`;
  }
  return path.startsWith("./") ? path : `./${path}`;
}

function isQaBreakdownBenchmark(benchmark) {
  return QA_BREAKDOWN_BENCHMARKS.has(benchmark);
}

function isBfclBenchmark(benchmark) {
  return benchmark === BFCL_BENCHMARK;
}

function isIfEvalBenchmark(benchmark) {
  return benchmark === IFEVAL_BENCHMARK;
}

function isZebraBenchmark(benchmark) {
  return benchmark === ZEBRA_BENCHMARK;
}

function qaScoreMapFromSummaryRow(rowData) {
  const values = {
    Correct: "—",
    Incorrect: "—",
    Abstain: "—",
    CorrectRaw: null,
    IncorrectRaw: null,
    AbstainRaw: null,
  };
  const metrics = [
    {
      label: rowData.primary_metric_label,
      score_label: rowData.primary_score_label,
      score: rowData.primary_score,
    },
    ...(rowData.supporting_metrics || []),
  ];

  metrics.forEach((metric) => {
    if (metric && Object.prototype.hasOwnProperty.call(values, metric.label)) {
      values[metric.label] = metric.score_label;
      values[`${metric.label}Raw`] = metric.score;
    }
  });

  return values;
}

function sortQaBreakdownRows(rows) {
  const sortKey = categoryState.filters.sort || "score_desc";
  const correctScore = (row) => row.CorrectRaw ?? -Infinity;

  return [...rows].sort((a, b) => {
    if (sortKey === "model_asc") {
      return a.model.localeCompare(b.model) || a.mode.localeCompare(b.mode);
    }

    if (sortKey === "cot_first" || sortKey === "nocot_first") {
      return (
        modeRank(a.mode, sortKey) - modeRank(b.mode, sortKey) ||
        correctScore(b) - correctScore(a) ||
        a.model.localeCompare(b.model)
      );
    }

    return (
      correctScore(b) - correctScore(a) ||
      a.model.localeCompare(b.model) ||
      a.mode.localeCompare(b.mode)
    );
  });
}

function bfclOverallMapFromSummaryRow(rowData) {
  const values = {
    "Live Overall Acc": "—",
    "Non-Live Overall Acc": "—",
    "Multi Turn Overall Acc": "—",
    LiveRaw: null,
    NonLiveRaw: null,
    MultiTurnRaw: null,
  };
  const metrics = [
    {
      label: rowData.primary_metric_label,
      score_label: rowData.primary_score_label,
      score: rowData.primary_score,
    },
    ...(rowData.supporting_metrics || []),
  ];

  metrics.forEach((metric) => {
    if (!metric) {
      return;
    }
    if (metric.label === "Live Overall Acc") {
      values["Live Overall Acc"] = metric.score_label;
      values.LiveRaw = metric.score;
    } else if (metric.label === "Non-Live Overall Acc") {
      values["Non-Live Overall Acc"] = metric.score_label;
      values.NonLiveRaw = metric.score;
    } else if (metric.label === "Multi Turn Overall Acc") {
      values["Multi Turn Overall Acc"] = metric.score_label;
      values.MultiTurnRaw = metric.score;
    }
  });

  return values;
}

function sortBfclOverallRows(rows) {
  const sortKey = categoryState.filters.sort || "score_desc";
  const liveScore = (row) => row.LiveRaw ?? -Infinity;

  return [...rows].sort((a, b) => {
    if (sortKey === "model_asc") {
      return a.model.localeCompare(b.model) || a.mode.localeCompare(b.mode);
    }

    if (sortKey === "cot_first" || sortKey === "nocot_first") {
      return (
        modeRank(a.mode, sortKey) - modeRank(b.mode, sortKey) ||
        liveScore(b) - liveScore(a) ||
        a.model.localeCompare(b.model)
      );
    }

    return (
      liveScore(b) - liveScore(a) ||
      a.model.localeCompare(b.model) ||
      a.mode.localeCompare(b.mode)
    );
  });
}

function sortMetricMatrixRows(rows, primaryField) {
  const sortKey = categoryState.filters.sort || "score_desc";
  const primaryScore = (row) => row[`${primaryField}Raw`] ?? -Infinity;

  return [...rows].sort((a, b) => {
    if (sortKey === "model_asc") {
      return a.model.localeCompare(b.model) || a.mode.localeCompare(b.mode);
    }

    if (sortKey === "cot_first" || sortKey === "nocot_first") {
      return (
        modeRank(a.mode, sortKey) - modeRank(b.mode, sortKey) ||
        primaryScore(b) - primaryScore(a) ||
        a.model.localeCompare(b.model)
      );
    }

    return (
      primaryScore(b) - primaryScore(a) ||
      a.model.localeCompare(b.model) ||
      a.mode.localeCompare(b.mode)
    );
  });
}

function metricMatrixRowFromSummaryRow(rowData, labels) {
  const row = {
    model: rowData.model,
    mode: rowData.mode,
    num_samples: rowData.num_samples,
  };
  labels.forEach((label) => {
    row[label] = "—";
    row[`${label}Raw`] = null;
  });

  const metrics = [
    {
      label: rowData.primary_metric_label,
      score_label: rowData.primary_score_label,
      score: rowData.primary_score,
    },
    ...(rowData.supporting_metrics || []),
  ];
  metrics.forEach((metric) => {
    if (!metric) {
      return;
    }
    if (Object.prototype.hasOwnProperty.call(row, metric.label)) {
      row[metric.label] = metric.score_label;
      row[`${metric.label}Raw`] = metric.score;
    }
  });
  return row;
}

function renderMetricMatrixSummaryTable(rows, labels, className = "") {
  const shell = createNode("div", "table-shell");
  const table = createNode(
    "table",
    `academic-table metric-matrix-table${className ? ` ${className}` : ""}`,
  );
  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  ["Model", "Mode", ...labels, "N"].forEach((label) => {
    headRow.appendChild(createNode("th", "", label));
  });
  thead.appendChild(headRow);

  const tbody = document.createElement("tbody");
  sortMetricMatrixRows(
    rows.map((rowData) => metricMatrixRowFromSummaryRow(rowData, labels)),
    labels[0],
  ).forEach((rowData) => {
    const row = document.createElement("tr");
    [
      rowData.model,
      rowData.mode,
      ...labels.map((label) => rowData[label]),
      formatNum(rowData.num_samples),
    ].forEach((value) => row.appendChild(createNode("td", "", value)));
    tbody.appendChild(row);
  });

  table.append(thead, tbody);
  shell.appendChild(table);
  return shell;
}

function passMilestonesMap(passGroup) {
  const values = {
    "k=1": "—",
    "k=8": "—",
    "k=32": "—",
    "k=64": "—",
    Gain: "—",
    "k=1Raw": null,
  };
  (passGroup?.milestones || []).forEach((item) => {
    if (item.label === "Gain") {
      values.Gain = item.score_label;
    } else if (item.k !== undefined && values.hasOwnProperty(`k=${item.k}`)) {
      values[`k=${item.k}`] = item.score_label;
      if (item.k === 1) {
        values["k=1Raw"] = item.score;
      }
    }
  });
  return values;
}

function renderPassMilestoneTable(rows, passGroups) {
  const passBySubject = new Map();
  passGroups.forEach((group) => {
    passBySubject.set(`${group.model}::${group.mode}`, group);
  });

  const enrichedRows = rows.map((rowData) => ({
    model: rowData.model,
    mode: rowData.mode,
    num_samples: rowData.num_samples,
    ...passMilestonesMap(passBySubject.get(`${rowData.model}::${rowData.mode}`)),
  }));

  const shell = createNode("div", "table-shell");
  const table = createNode("table", "academic-table pass-milestone-table");
  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  ["Model", "Mode", "P@1", "P@8", "P@32", "P@64", "Gain", "N"].forEach((label) => {
    headRow.appendChild(createNode("th", "", label));
  });
  thead.appendChild(headRow);

  const tbody = document.createElement("tbody");
  sortMetricMatrixRows(enrichedRows, "k=1").forEach((rowData) => {
    const row = document.createElement("tr");
    [
      rowData.model,
      rowData.mode,
      rowData["k=1"],
      rowData["k=8"],
      rowData["k=32"],
      rowData["k=64"],
      rowData.Gain,
      formatNum(rowData.num_samples),
    ].forEach((value) => row.appendChild(createNode("td", "", value)));
    tbody.appendChild(row);
  });

  table.append(thead, tbody);
  shell.appendChild(table);
  return shell;
}

function orderedBfclMetricLabels(subsetName, labels) {
  const preferred = BFCL_SUBSET_METRIC_ORDER[subsetName] || [];
  const ranked = new Map(preferred.map((label, index) => [label, index]));
  return [...labels].sort((a, b) => {
    const aRank = ranked.has(a) ? ranked.get(a) : Number.MAX_SAFE_INTEGER;
    const bRank = ranked.has(b) ? ranked.get(b) : Number.MAX_SAFE_INTEGER;
    return aRank - bRank || a.localeCompare(b);
  });
}

function renderBfclSummaryTable(rows) {
  const shell = createNode("div", "table-shell");
  const table = createNode("table", "academic-table bfcl-table");
  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  ["Model", "Mode", ...BFCL_OVERALL_LABELS].forEach((label) => {
    headRow.appendChild(createNode("th", "", label));
  });
  thead.appendChild(headRow);

  const tbody = document.createElement("tbody");
  sortBfclOverallRows(
    rows.map((rowData) => ({
      model: rowData.model,
      mode: rowData.mode,
      ...bfclOverallMapFromSummaryRow(rowData),
    })),
  ).forEach((rowData) => {
    const row = document.createElement("tr");
    [
      rowData.model,
      rowData.mode,
      rowData["Live Overall Acc"],
      rowData["Non-Live Overall Acc"],
      rowData["Multi Turn Overall Acc"],
    ].forEach((value) => {
      row.appendChild(createNode("td", "", value));
    });
    tbody.appendChild(row);
  });

  table.append(thead, tbody);
  shell.appendChild(table);
  return shell;
}

function singleMetricLabelFromSummaryRows(rows, benchmark, category = "") {
  if (
    !["knowledge", "reasoning"].includes(category) ||
    isQaBreakdownBenchmark(benchmark) ||
    !rows.length
  ) {
    return "";
  }
  const labels = new Set(rows.map((row) => row.primary_metric_label));
  const hasSupporting = rows.some((row) => (row.supporting_metrics || []).length);
  if (hasSupporting || labels.size !== 1) {
    return "";
  }
  return Array.from(labels)[0];
}

function singleMetricLabelFromSubsetRows(rows, benchmark, category = "") {
  if (
    !["knowledge", "reasoning"].includes(category) ||
    isQaBreakdownBenchmark(benchmark) ||
    !rows.length
  ) {
    return "";
  }
  const labels = new Set(rows.map((row) => row.metric_label));
  if (labels.size !== 1) {
    return "";
  }
  return Array.from(labels)[0];
}

function protocolValueFromSummary(summary, tokens) {
  if (!summary) {
    return "—";
  }
  const parts = String(summary).split("·").map((part) => part.trim());
  for (const token of tokens) {
    const loweredToken = token.toLowerCase();
    for (const part of parts) {
      const lowered = part.toLowerCase();
      if (lowered.startsWith(loweredToken + " ")) {
        return part.slice(token.length).trim();
      }
    }
  }
  return "—";
}

function normalizeProtocolModeEntry(modeEntry) {
  const benchmarkRunCounts = Array.isArray(modeEntry.benchmark_run_counts)
    ? modeEntry.benchmark_run_counts
    : (modeEntry.benchmarks || []).map((benchmark) => ({
        benchmark,
        display_name: benchmark,
        run_count: 1,
      }));

  const settingsSummary = modeEntry.settings_summary || "No published config";

  return {
    ...modeEntry,
    temperature:
      modeEntry.temperature ||
      protocolValueFromSummary(settingsSummary, ["Temperature", "temp"]),
    top_p:
      modeEntry.top_p ||
      protocolValueFromSummary(settingsSummary, ["Top-p", "top-p"]),
    top_k:
      modeEntry.top_k ||
      protocolValueFromSummary(settingsSummary, ["Top-k", "top-k"]),
    benchmark_run_counts: benchmarkRunCounts,
    benchmark_count:
      modeEntry.benchmark_count ?? (modeEntry.benchmarks ? modeEntry.benchmarks.length : benchmarkRunCounts.length),
  };
}

function renderProtocolModeRow(modeEntry) {
  const normalized = normalizeProtocolModeEntry(modeEntry);
  const modeLabel = normalized.mode || "NoCoT";
  const row = document.createElement("tr");

  const modeCell = document.createElement("td");
  modeCell.appendChild(
    createNode("span", `mode-pill mode-${modeLabel.toLowerCase()}`, modeLabel),
  );

  const benchmarkCell = document.createElement("td");
  const benchmarkList = createNode("div", "protocol-chip-row");
  normalized.benchmark_run_counts.forEach((entry) => {
    benchmarkList.appendChild(
      createNode(
        "span",
        "protocol-chip",
        `${entry.display_name} ×${entry.run_count}`,
      ),
    );
  });
  benchmarkCell.appendChild(
    benchmarkList.childNodes.length
      ? benchmarkList
      : createNode("span", "compact-note", "No benchmark coverage."),
  );

  [
    modeCell,
    createNode("td", "", normalized.temperature || "—"),
    createNode("td", "", normalized.top_p || "—"),
    createNode("td", "", normalized.top_k || "—"),
    benchmarkCell,
  ].forEach((cell) => row.appendChild(cell));

  return row;
}

function renderHomeProtocolGroups(protocolPayload) {
  if (!homeElements.protocolGroups) {
    return;
  }

  const fragment = document.createDocumentFragment();
  (protocolPayload.families || []).forEach((familyGroup) => {
    const card = createNode("article", "protocol-family");
    const head = createNode("div", "protocol-family-head");
    const title = createNode("h3", "protocol-family-title", familyGroup.family);
    const meta = createNode(
      "div",
      "protocol-family-meta",
      `${familyGroup.family_run_count ?? (familyGroup.modes || []).reduce((sum, item) => sum + (item.coverage_count || 0), 0)} runs · ${familyGroup.benchmark_count ?? new Set((familyGroup.modes || []).flatMap((item) => item.benchmarks || [])).size} benchmarks`,
    );
    head.append(title, meta);

    const body = createNode("div", "table-shell protocol-shell");
    const table = createNode("table", "academic-table protocol-mini-table");
    const thead = document.createElement("thead");
    const headRow = document.createElement("tr");
    ["Mode", "Temperature", "Top-p", "Top-k", "Benchmark runs"].forEach((label) => {
      headRow.appendChild(createNode("th", "", label));
    });
    thead.appendChild(headRow);

    const tbody = document.createElement("tbody");
    (familyGroup.modes || []).forEach((modeEntry) => {
      tbody.appendChild(renderProtocolModeRow(modeEntry));
    });
    table.append(thead, tbody);
    body.appendChild(table);

    card.append(head, body);
    fragment.appendChild(card);
  });

  if (!(protocolPayload.families || []).length) {
    fragment.appendChild(createEmptyNote("No protocol rows were generated."));
  }

  homeElements.protocolGroups.replaceChildren(fragment);
}

function renderCategoryCards(indexPayload) {
  if (!homeElements.categoryGrid) {
    return;
  }

  const rawSummary = indexPayload.category_summary || [];
  const categoryEntries = Array.isArray(rawSummary)
    ? rawSummary
    : Object.entries(rawSummary).map(([category, stats]) => {
        const featuredBenchmarks = (indexPayload.featured_benchmarks || []).filter(
          (entry) => entry.category === category,
        );
        const href = category === "instruction_following" ? "./if.html" : `./${category}.html`;
        return {
          category,
          href,
          display_name: CATEGORY_META[category]?.label || category,
          featured_note: CATEGORY_META[category]?.emphasis || "Benchmark results",
          benchmark_count: stats?.benchmark_count || featuredBenchmarks.length,
          model_count: stats?.model_count || 0,
          description:
            category === "instruction_following"
              ? "Read instruction-following compliance results with benchmark-specific tables."
              : `Read ${CATEGORY_META[category]?.label || category} results with benchmark-specific tables.`,
          benchmarks: featuredBenchmarks,
        };
      });

  const fragment = document.createDocumentFragment();
  categoryEntries.forEach((entry) => {
    const card = document.createElement("a");
    card.className = "category-card";
    card.href = entry.href;

    const eyebrow = createNode("span", "card-kicker", entry.display_name);
    const title = createNode("strong", "card-title", entry.featured_note);
    const meta = createNode(
      "span",
      "card-meta",
      `${entry.benchmark_count} benchmarks · ${entry.model_count} models`,
    );
    const description = createNode("p", "card-copy", entry.description);

    const list = createNode("div", "chip-row");
    (entry.benchmarks || []).forEach((benchmark) => {
      list.appendChild(createNode("span", "chip", benchmark.display_name));
    });

    card.append(eyebrow, title, meta, description, list);
    fragment.appendChild(card);
  });

  homeElements.categoryGrid.replaceChildren(fragment);
}

function renderFeaturedBenchmarks(indexPayload) {
  if (!homeElements.featuredList) {
    return;
  }

  const fragment = document.createDocumentFragment();
  (indexPayload.featured_benchmarks || []).forEach((entry) => {
    const item = createNode(
      "span",
      "chip chip-muted",
      `${CATEGORY_META[entry.category].label}: ${entry.display_name}`,
    );
    fragment.appendChild(item);
  });
  homeElements.featuredList.replaceChildren(fragment);
}

function renderHomeSummary(indexPayload) {
  if (homeElements.generatedAt) {
    homeElements.generatedAt.textContent = indexPayload.generated_at;
  }
  if (homeElements.recordCount) {
    homeElements.recordCount.textContent = String(indexPayload.summary.record_count);
  }
  if (homeElements.runCount) {
    homeElements.runCount.textContent = String(indexPayload.summary.run_count);
  }
  if (homeElements.modelCount) {
    homeElements.modelCount.textContent = String(indexPayload.summary.model_count);
  }
  if (homeElements.benchmarkCount) {
    homeElements.benchmarkCount.textContent = String(indexPayload.summary.benchmark_count);
  }
  if (homeElements.artifactCount) {
    homeElements.artifactCount.textContent = String(indexPayload.summary.artifact_count);
  }
  if (homeElements.overallCount) {
    homeElements.overallCount.textContent = formatNum(indexPayload.summary.overall_record_count);
  }
  if (homeElements.subsetCount) {
    homeElements.subsetCount.textContent = formatNum(indexPayload.summary.subset_record_count);
  }

  const exclusions = indexPayload.publication.excluded_invalid_sources;
  if (homeElements.excludedNote) {
    homeElements.excludedNote.textContent =
      `Excluded exact benchmarks: ${exclusions.benchmark_file_excludes.join(", ")}. ` +
      `Excluded by keyword: ${exclusions.benchmark_keyword_excludes.join(", ")}.`;
  }

  if (homeElements.detailedResultsLink) {
    homeElements.detailedResultsLink.href = relativeLink(
      indexPayload.downloads.detailed_results_json,
    );
  }
  if (homeElements.publicResultsLink) {
    homeElements.publicResultsLink.href = relativeLink(
      indexPayload.downloads.public_results_root,
    );
  }
  if (homeElements.flatBundleLink) {
    homeElements.flatBundleLink.href = relativeLink(
      indexPayload.downloads.legacy_flat_bundle_json,
    );
  }
}

async function initHomePage() {
  const [indexPayload, protocolPayload] = await Promise.all([
    fetchJson("./data/index.json"),
    fetchJson("./data/protocol.json"),
  ]);

  renderHomeSummary(indexPayload);
  renderHomeProtocolGroups(protocolPayload);
  renderCategoryCards(indexPayload);
  renderFeaturedBenchmarks(indexPayload);
}

function renderCategoryMeta(payload) {
  categoryElements.generatedAt.textContent = payload.generated_at;
  categoryElements.description.textContent = payload.description;
  categoryElements.benchmarkCount.textContent = String(payload.benchmarks.length);
}

function populateCategoryFilters(payload) {
  setSelectOptions(categoryElements.model, payload.filters.models);
  setSelectOptions(categoryElements.mode, payload.filters.modes);
  setBenchmarkOptions(categoryElements.benchmark, payload.benchmarks);
}

function matchesCategoryFilters(entry) {
  if (
    categoryState.filters.benchmark &&
    entry.benchmark !== categoryState.filters.benchmark
  ) {
    return false;
  }
  return true;
}

function filterModelRows(rows) {
  return rows.filter((row) => {
    if (categoryState.filters.model && row.model !== categoryState.filters.model) {
      return false;
    }
    if (categoryState.filters.mode && row.mode !== categoryState.filters.mode) {
      return false;
    }
    return true;
  });
}

function filterPassGroups(groups) {
  return groups.filter((group) => {
    if (categoryState.filters.model && group.model !== categoryState.filters.model) {
      return false;
    }
    if (categoryState.filters.mode && group.mode !== categoryState.filters.mode) {
      return false;
    }
    return true;
  });
}

function filterSubsetRows(rows) {
  const filtered = rows.filter((row) => {
    if (categoryState.filters.model && row.model !== categoryState.filters.model) {
      return false;
    }
    if (categoryState.filters.mode && row.mode !== categoryState.filters.mode) {
      return false;
    }
    return true;
  });
  return sortSubsetRows(filtered);
}

function modeRank(mode, sortKey) {
  if (sortKey === "cot_first") {
    return mode === "CoT" ? 0 : 1;
  }
  if (sortKey === "nocot_first") {
    return mode === "NoCoT" ? 0 : 1;
  }
  return 0;
}

function sortSummaryRows(rows) {
  const sortKey = categoryState.filters.sort || "score_desc";
  return [...rows].sort((a, b) => {
    if (sortKey === "model_asc") {
      return (
        a.model.localeCompare(b.model) ||
        a.mode.localeCompare(b.mode) ||
        (b.primary_score ?? -Infinity) - (a.primary_score ?? -Infinity)
      );
    }

    if (sortKey === "cot_first" || sortKey === "nocot_first") {
      return (
        modeRank(a.mode, sortKey) - modeRank(b.mode, sortKey) ||
        (b.primary_score ?? -Infinity) - (a.primary_score ?? -Infinity) ||
        a.model.localeCompare(b.model)
      );
    }

    return (
      (b.primary_score ?? -Infinity) - (a.primary_score ?? -Infinity) ||
      a.model.localeCompare(b.model) ||
      a.mode.localeCompare(b.mode)
    );
  });
}

function sortPassGroups(groups) {
  const sortKey = categoryState.filters.sort || "score_desc";
  const scoreOf = (group) =>
    group.points.length ? group.points[group.points.length - 1].score ?? -Infinity : -Infinity;

  return [...groups].sort((a, b) => {
    if (sortKey === "model_asc") {
      return a.model.localeCompare(b.model) || a.mode.localeCompare(b.mode);
    }

    if (sortKey === "cot_first" || sortKey === "nocot_first") {
      return (
        modeRank(a.mode, sortKey) - modeRank(b.mode, sortKey) ||
        scoreOf(b) - scoreOf(a) ||
        a.model.localeCompare(b.model)
      );
    }

    return scoreOf(b) - scoreOf(a) || a.model.localeCompare(b.model) || a.mode.localeCompare(b.mode);
  });
}

function sortSubsetRows(rows) {
  const sortKey = categoryState.filters.sort || "score_desc";
  return [...rows].sort((a, b) => {
    if (sortKey === "model_asc") {
      return (
        a.model.localeCompare(b.model) ||
        a.mode.localeCompare(b.mode) ||
        a.metric.localeCompare(b.metric) ||
        a.subset.localeCompare(b.subset)
      );
    }

    if (sortKey === "cot_first" || sortKey === "nocot_first") {
      return (
        modeRank(a.mode, sortKey) - modeRank(b.mode, sortKey) ||
        ((b.score ?? -Infinity) - (a.score ?? -Infinity)) ||
        a.model.localeCompare(b.model) ||
        a.metric.localeCompare(b.metric) ||
        a.subset.localeCompare(b.subset)
      );
    }

    return (
      ((b.score ?? -Infinity) - (a.score ?? -Infinity)) ||
      a.model.localeCompare(b.model) ||
      a.mode.localeCompare(b.mode) ||
      a.metric.localeCompare(b.metric) ||
      a.subset.localeCompare(b.subset)
    );
  });
}

function sortSectionEntries(entries) {
  const sortKey = categoryState.filters.sort || "score_desc";
  const scoreOfEntry = (entry) => {
    const summaryRows = sortSummaryRows(filterModelRows(entry.model_rows));
    if (summaryRows.length) {
      return summaryRows[0].primary_score ?? -Infinity;
    }
    const passGroups = sortPassGroups(filterPassGroups(entry.passk_groups));
    if (passGroups.length) {
      const points = passGroups[0].points;
      return points.length ? points[points.length - 1].score ?? -Infinity : -Infinity;
    }
    return -Infinity;
  };
  const preferredModeOfEntry = (entry) => {
    const summaryRows = sortSummaryRows(filterModelRows(entry.model_rows));
    if (summaryRows.length) {
      return summaryRows[0].mode;
    }
    const passGroups = sortPassGroups(filterPassGroups(entry.passk_groups));
    if (passGroups.length) {
      return passGroups[0].mode;
    }
    return "";
  };

  return [...entries].sort((a, b) => {
    if (sortKey === "model_asc") {
      return a.display_name.localeCompare(b.display_name);
    }

    if (sortKey === "cot_first" || sortKey === "nocot_first") {
      return (
        modeRank(preferredModeOfEntry(a), sortKey) -
          modeRank(preferredModeOfEntry(b), sortKey) ||
        scoreOfEntry(b) - scoreOfEntry(a) ||
        a.display_name.localeCompare(b.display_name)
      );
    }

    return (
      scoreOfEntry(b) - scoreOfEntry(a) ||
      a.display_name.localeCompare(b.display_name)
    );
  });
}

function renderQaBreakdownSummaryTable(rows) {
  const shell = createNode("div", "table-shell");
  const table = createNode("table", "academic-table qa-breakdown-table");
  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  ["Model", "Mode", ...QA_BREAKDOWN_LABELS, "N", "Subsets"].forEach((label) => {
    headRow.appendChild(createNode("th", "", label));
  });
  thead.appendChild(headRow);

  const tbody = document.createElement("tbody");
  sortQaBreakdownRows(
    rows.map((rowData) => ({
      model: rowData.model,
      mode: rowData.mode,
      num_samples: rowData.num_samples,
      subset_count: rowData.subset_count,
      ...qaScoreMapFromSummaryRow(rowData),
    })),
  ).forEach((rowData) => {
    const row = document.createElement("tr");
    [
      rowData.model,
      rowData.mode,
      rowData.Correct,
      rowData.Incorrect,
      rowData.Abstain,
      formatNum(rowData.num_samples),
      rowData.subset_count ? `${rowData.subset_count} subsets` : "overall only",
    ].forEach((value) => {
      row.appendChild(createNode("td", "", value));
    });
    tbody.appendChild(row);
  });

  table.append(thead, tbody);
  shell.appendChild(table);
  return shell;
}

function renderSingleMetricSummaryTable(rows, metricLabel) {
  const shell = createNode("div", "table-shell");
  const table = createNode("table", "academic-table single-metric-table");
  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  ["Model", "Mode", metricLabel, "N", "Subsets"].forEach((label) => {
    headRow.appendChild(createNode("th", "", label));
  });
  thead.appendChild(headRow);

  const tbody = document.createElement("tbody");
  sortSummaryRows(rows).forEach((rowData) => {
    const row = document.createElement("tr");
    [
      rowData.model,
      rowData.mode,
      rowData.primary_score_label,
      formatNum(rowData.num_samples),
      rowData.subset_count ? `${rowData.subset_count} subsets` : "overall only",
    ].forEach((value) => {
      row.appendChild(createNode("td", "", value));
    });
    tbody.appendChild(row);
  });

  table.append(thead, tbody);
  shell.appendChild(table);
  return shell;
}

function renderAcademicSummaryTable(rows, benchmark = "", category = "") {
  if (isBfclBenchmark(benchmark)) {
    return renderBfclSummaryTable(rows);
  }

  if (isIfEvalBenchmark(benchmark)) {
    return renderMetricMatrixSummaryTable(rows, IFEVAL_LABELS, "ifeval-table");
  }

  if (isZebraBenchmark(benchmark)) {
    return renderMetricMatrixSummaryTable(rows, ZEBRA_SUMMARY_LABELS, "zebra-table");
  }

  if (isQaBreakdownBenchmark(benchmark)) {
    return renderQaBreakdownSummaryTable(rows);
  }

  const singleMetricLabel = singleMetricLabelFromSummaryRows(rows, benchmark, category);
  if (singleMetricLabel) {
    return renderSingleMetricSummaryTable(rows, singleMetricLabel);
  }

  const shell = createNode("div", "table-shell");
  const table = createNode("table", "academic-table");
  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  ["Model", "Mode", "Primary", "Supporting", "N", "Subsets"].forEach((label) => {
    headRow.appendChild(createNode("th", "", label));
  });
  thead.appendChild(headRow);

  const tbody = document.createElement("tbody");
  rows.forEach((rowData) => {
    const row = document.createElement("tr");
    const supporting = rowData.supporting_metrics.length
      ? rowData.supporting_metrics
          .slice(0, 3)
          .map((item) => `${item.label} ${item.score_label}`)
          .join(" · ")
      : "—";
    [
      rowData.model,
      rowData.mode,
      `${rowData.primary_metric_label} ${rowData.primary_score_label}`,
      supporting,
      formatNum(rowData.num_samples),
      rowData.subset_count ? `${rowData.subset_count} subsets` : "overall only",
    ].forEach((value) => {
      row.appendChild(createNode("td", "", value));
    });
    tbody.appendChild(row);
  });

  table.append(thead, tbody);
  shell.appendChild(table);
  return shell;
}

function createSvgNode(name, attrs = {}) {
  const node = document.createElementNS(SVG_NS, name);
  Object.entries(attrs).forEach(([key, value]) => {
    node.setAttribute(key, String(value));
  });
  return node;
}

function milestonePointSet(points, milestones) {
  const keys = new Set();
  milestones.forEach((item) => {
    if (item.k !== undefined) {
      keys.add(item.k);
    }
  });
  if (!keys.size && points.length) {
    keys.add(points[0].k);
    keys.add(points[points.length - 1].k);
  }
  return keys;
}

function buildPassChartFigure(group) {
  const figure = createNode("div", "chart-shell");
  const tooltip = createNode("div", "chart-tooltip");
  tooltip.hidden = true;

  const width = 680;
  const height = 230;
  const padding = { top: 24, right: 28, bottom: 40, left: 28 };
  const minK = Math.min(...group.points.map((point) => point.k));
  const maxK = Math.max(...group.points.map((point) => point.k));
  const minScore = Math.min(...group.points.map((point) => point.score));
  const maxScore = Math.max(...group.points.map((point) => point.score));
  const svg = createSvgNode("svg", {
    viewBox: `0 0 ${width} ${height}`,
    class: "pass-svg",
    "aria-hidden": "true",
  });

  const plotBottom = height - padding.bottom;
  const plotTop = padding.top;
  const plotLeft = padding.left;
  const plotRight = width - padding.right;
  const x = (k) => {
    if (maxK === minK) {
      return (plotLeft + plotRight) / 2;
    }
    return plotLeft + ((k - minK) / (maxK - minK)) * (plotRight - plotLeft);
  };
  const y = (score) => {
    if (maxScore === minScore) {
      return (plotTop + plotBottom) / 2;
    }
    return plotBottom - ((score - minScore) / (maxScore - minScore)) * (plotBottom - plotTop);
  };

  [0, 0.5, 1].forEach((ratio) => {
    const gridY = plotBottom - ratio * (plotBottom - plotTop);
    svg.appendChild(
      createSvgNode("line", {
        x1: plotLeft,
        y1: gridY,
        x2: plotRight,
        y2: gridY,
        class: "pass-grid",
      }),
    );
  });

  const pathData = group.points
    .map((point, index) => `${index === 0 ? "M" : "L"} ${x(point.k)} ${y(point.score)}`)
    .join(" ");
  svg.appendChild(createSvgNode("path", { d: pathData, class: "pass-line" }));

  const emphasized = milestonePointSet(group.points, group.milestones);
  group.points.forEach((point) => {
    if (emphasized.has(point.k)) {
      svg.appendChild(
        createSvgNode("circle", {
          cx: x(point.k),
          cy: y(point.score),
          r: 4,
          class: "pass-dot",
        }),
      );
    }
  });

  group.milestones
    .filter((item) => item.k !== undefined)
    .forEach((item) => {
      const label = createSvgNode("text", {
        x: x(item.k),
        y: height - 14,
        "text-anchor": "middle",
        class: "pass-axis-label",
      });
      label.textContent = `k=${item.k}`;
      svg.appendChild(label);
    });

  const startLabel = createSvgNode("text", {
    x: plotLeft,
    y: 14,
    "text-anchor": "start",
    class: "pass-value-label",
  });
  startLabel.textContent = `start ${group.points[0].score_label}`;
  svg.appendChild(startLabel);

  const endLabel = createSvgNode("text", {
    x: plotRight,
    y: 14,
    "text-anchor": "end",
    class: "pass-value-label",
  });
  endLabel.textContent = `end ${group.points[group.points.length - 1].score_label}`;
  svg.appendChild(endLabel);

  group.points.forEach((point) => {
    const target = createSvgNode("circle", {
      cx: x(point.k),
      cy: y(point.score),
      r: 10,
      class: "pass-hover-target",
    });

    const showTooltip = (event) => {
      tooltip.hidden = false;
      tooltip.textContent = `${group.model} · ${group.mode} · k=${point.k} · ${point.score_label}`;
      const bounds = figure.getBoundingClientRect();
      const offsetX = event.clientX - bounds.left;
      const offsetY = event.clientY - bounds.top;
      tooltip.style.left = `${Math.max(56, Math.min(offsetX, bounds.width - 56))}px`;
      tooltip.style.top = `${Math.max(16, offsetY - 12)}px`;
    };

    target.addEventListener("mouseenter", showTooltip);
    target.addEventListener("mousemove", showTooltip);
    target.addEventListener("mouseleave", () => {
      tooltip.hidden = true;
    });
    svg.appendChild(target);
  });

  figure.append(svg, tooltip);
  return figure;
}

function renderPassCards(groups) {
  const wrap = createNode("div", "pass-stack");
  const limit = categoryState.filters.model ? 6 : 3;
  const visibleGroups = groups.slice(0, limit);

  visibleGroups.forEach((group) => {
    const card = createNode("article", "pass-card");
    const title = createNode(
      "div",
      "pass-title",
      `${group.model} · ${group.mode} · ${group.metric_base}`,
    );
    const figure = buildPassChartFigure(group);
    const chips = createNode("div", "chip-row");

    group.milestones.forEach((item) => {
      const label = item.label
        ? `${item.label} ${item.score_label}`
        : `k=${item.k}: ${item.score_label}`;
      chips.appendChild(createNode("span", "chip chip-muted", label));
    });

    card.append(title, figure, chips);
    wrap.appendChild(card);
  });

  if (groups.length > visibleGroups.length) {
    wrap.appendChild(
      createNode(
        "p",
        "section-note compact-note",
        `Showing ${visibleGroups.length} of ${groups.length} pass@k curves. Narrow the model filter to inspect more.`,
      ),
    );
  }

  return wrap;
}

function sectionTools(entry) {
  const wrap = createNode("div", "section-tools");

  const detailLink = createNode("a", "text-link", "Benchmark JSON");
  detailLink.href = relativeLink(entry.download.json_path);
  detailLink.target = "_blank";
  detailLink.rel = "noreferrer";
  wrap.appendChild(detailLink);

  if (entry.download.sample_artifact_paths.length) {
    const artifactLink = createNode("a", "text-link", "Sample artifact");
    artifactLink.href = relativeLink(entry.download.sample_artifact_paths[0]);
    artifactLink.target = "_blank";
    artifactLink.rel = "noreferrer";
    wrap.appendChild(artifactLink);

    wrap.appendChild(
      createNode(
        "span",
        "compact-note",
        `${entry.download.artifact_count} artifact files`,
      ),
    );
  }

  return wrap;
}

function renderSubsetTable(detailPayload) {
  const filteredRows = filterSubsetRows(detailPayload.subset_rows);
  if (!filteredRows.length) {
    return createEmptyNote("No subset rows match the current filters.");
  }

  const grouped = new Map();
  filteredRows.forEach((row) => {
    if (!grouped.has(row.subset)) {
      grouped.set(row.subset, []);
    }
    grouped.get(row.subset).push(row);
  });

  const wrap = createNode("div", "subset-group-stack");
  Array.from(grouped.keys())
    .sort((a, b) => a.localeCompare(b))
    .forEach((subsetName) => {
      const subsetRows = grouped.get(subsetName);
      const singleMetricLabel = singleMetricLabelFromSubsetRows(
        subsetRows,
        detailPayload.benchmark,
        detailPayload.category,
      );
      const section = createNode("section", "subset-group");
      const header = createNode("div", "subset-head");
      const title = createNode("strong", "subset-title", subsetName);
      let metaText = `${subsetRows.length} rows`;
      let renderRows = subsetRows;
      let headLabels = ["Model", "Mode", "Metric", "Score", "N"];
      let rowValues = (rowData) => [
        rowData.model,
        rowData.mode,
        rowData.metric_label,
        rowData.score_label,
        formatNum(rowData.num_samples),
      ];

      if (isBfclBenchmark(detailPayload.benchmark)) {
        const metricLabels = orderedBfclMetricLabels(
          subsetName,
          new Set(subsetRows.map((rowData) => rowData.metric_label)),
        );
        const bySubject = new Map();
        subsetRows.forEach((rowData) => {
          const key = `${rowData.model}::${rowData.mode}`;
          if (!bySubject.has(key)) {
            const subject = {
              model: rowData.model,
              mode: rowData.mode,
            };
            metricLabels.forEach((label) => {
              subject[label] = "—";
              subject[`${label}Raw`] = null;
            });
            bySubject.set(key, subject);
          }
          const subject = bySubject.get(key);
          if (Object.prototype.hasOwnProperty.call(subject, rowData.metric_label)) {
            subject[rowData.metric_label] = rowData.score_label;
            subject[`${rowData.metric_label}Raw`] = rowData.score;
          }
        });
        renderRows = [...bySubject.values()].sort((a, b) => {
          const sortKey = categoryState.filters.sort || "score_desc";
          const primaryMetric = metricLabels[0];
          const primaryA = a[`${primaryMetric}Raw`] ?? -Infinity;
          const primaryB = b[`${primaryMetric}Raw`] ?? -Infinity;

          if (sortKey === "model_asc") {
            return a.model.localeCompare(b.model) || a.mode.localeCompare(b.mode);
          }

          if (sortKey === "cot_first" || sortKey === "nocot_first") {
            return (
              modeRank(a.mode, sortKey) - modeRank(b.mode, sortKey) ||
              primaryB - primaryA ||
              a.model.localeCompare(b.model)
            );
          }

          return (
            primaryB - primaryA ||
            a.model.localeCompare(b.model) ||
            a.mode.localeCompare(b.mode)
          );
        });
        metaText = `${renderRows.length} models · ${metricLabels.length} metrics`;
        headLabels = ["Model", "Mode", ...metricLabels];
        rowValues = (rowData) => [
          rowData.model,
          rowData.mode,
          ...metricLabels.map((label) => rowData[label]),
        ];
      } else if (isIfEvalBenchmark(detailPayload.benchmark)) {
        const bySubject = new Map();
        subsetRows.forEach((rowData) => {
          const key = `${rowData.model}::${rowData.mode}`;
          if (!bySubject.has(key)) {
            bySubject.set(key, {
              model: rowData.model,
              mode: rowData.mode,
              num_samples: rowData.num_samples,
              ...Object.fromEntries(
                IFEVAL_LABELS.flatMap((label) => [
                  [label, "—"],
                  [`${label}Raw`, null],
                ]),
              ),
            });
          }
          const subject = bySubject.get(key);
          if (Object.prototype.hasOwnProperty.call(subject, rowData.metric_label)) {
            subject[rowData.metric_label] = rowData.score_label;
            subject[`${rowData.metric_label}Raw`] = rowData.score;
          }
        });
        renderRows = sortMetricMatrixRows(Array.from(bySubject.values()), IFEVAL_LABELS[0]);
        metaText = `${renderRows.length} models`;
        headLabels = ["Model", "Mode", ...IFEVAL_LABELS, "N"];
        rowValues = (rowData) => [
          rowData.model,
          rowData.mode,
          ...IFEVAL_LABELS.map((label) => rowData[label]),
          formatNum(rowData.num_samples),
        ];
      } else if (isZebraBenchmark(detailPayload.benchmark)) {
        const bySubject = new Map();
        subsetRows.forEach((rowData) => {
          const key = `${rowData.model}::${rowData.mode}`;
          if (!bySubject.has(key)) {
            bySubject.set(key, {
              model: rowData.model,
              mode: rowData.mode,
              num_samples: rowData.num_samples,
              ...Object.fromEntries(
                ZEBRA_LABELS.flatMap((label) => [
                  [label, "—"],
                  [`${label}Raw`, null],
                ]),
              ),
            });
          }
          const subject = bySubject.get(key);
          if (Object.prototype.hasOwnProperty.call(subject, rowData.metric_label)) {
            subject[rowData.metric_label] = rowData.score_label;
            subject[`${rowData.metric_label}Raw`] = rowData.score;
          }
        });
        renderRows = sortMetricMatrixRows(Array.from(bySubject.values()), ZEBRA_LABELS[0]);
        metaText = `${renderRows.length} models`;
        headLabels = ["Model", "Mode", ...ZEBRA_LABELS, "N"];
        rowValues = (rowData) => [
          rowData.model,
          rowData.mode,
          ...ZEBRA_LABELS.map((label) => rowData[label]),
          formatNum(rowData.num_samples),
        ];
      } else if (isQaBreakdownBenchmark(detailPayload.benchmark)) {
        const bySubject = new Map();
        subsetRows.forEach((rowData) => {
          const key = `${rowData.model}::${rowData.mode}`;
          if (!bySubject.has(key)) {
            bySubject.set(key, {
              model: rowData.model,
              mode: rowData.mode,
              num_samples: rowData.num_samples,
              Correct: "—",
              Incorrect: "—",
              Abstain: "—",
              CorrectRaw: null,
              IncorrectRaw: null,
              AbstainRaw: null,
            });
          }
          const subject = bySubject.get(key);
          if (Object.prototype.hasOwnProperty.call(subject, rowData.metric_label)) {
            subject[rowData.metric_label] = rowData.score_label;
            subject[`${rowData.metric_label}Raw`] = rowData.score;
          }
        });
        renderRows = sortQaBreakdownRows(Array.from(bySubject.values()));
        metaText = `${renderRows.length} models`;
        headLabels = ["Model", "Mode", ...QA_BREAKDOWN_LABELS, "N"];
        rowValues = (rowData) => [
          rowData.model,
          rowData.mode,
          rowData.Correct,
          rowData.Incorrect,
          rowData.Abstain,
          formatNum(rowData.num_samples),
        ];
      } else if (singleMetricLabel) {
        headLabels = ["Model", "Mode", singleMetricLabel, "N"];
        rowValues = (rowData) => [
          rowData.model,
          rowData.mode,
          rowData.score_label,
          formatNum(rowData.num_samples),
        ];
      }

      const meta = createNode("span", "compact-note", metaText);
      header.append(title, meta);

      const shell = createNode("div", "table-shell detail-shell");
      const table = createNode(
        "table",
        `academic-table detail-table${isQaBreakdownBenchmark(detailPayload.benchmark) ? " qa-breakdown-table" : ""}${singleMetricLabel ? " single-metric-table" : ""}${isBfclBenchmark(detailPayload.benchmark) ? " bfcl-table metric-matrix-table" : ""}${isIfEvalBenchmark(detailPayload.benchmark) ? " ifeval-table metric-matrix-table" : ""}${isZebraBenchmark(detailPayload.benchmark) ? " zebra-table metric-matrix-table" : ""}`,
      );
      const thead = document.createElement("thead");
      const headRow = document.createElement("tr");
      headLabels.forEach((label) => {
        headRow.appendChild(createNode("th", "", label));
      });
      thead.appendChild(headRow);

      const tbody = document.createElement("tbody");
      renderRows.forEach((rowData) => {
        const row = document.createElement("tr");
        rowValues(rowData).forEach((value) =>
          row.appendChild(createNode("td", "", value)),
        );
        tbody.appendChild(row);
      });

      table.append(thead, tbody);
      shell.appendChild(table);
      section.append(header, shell);
      wrap.appendChild(section);
    });

  return wrap;
}

async function ensureBenchmarkDetail(entry) {
  const cacheKey = entry.benchmark_data_path;
  if (categoryState.detailCache.has(cacheKey)) {
    return categoryState.detailCache.get(cacheKey);
  }

  const promise = fetchJson(relativeLink(cacheKey))
    .then((payload) => {
      categoryState.detailCache.set(cacheKey, payload);
      return payload;
    })
    .catch((error) => {
      categoryState.detailCache.set(cacheKey, { error: error.message });
      return categoryState.detailCache.get(cacheKey);
    });

  categoryState.detailCache.set(cacheKey, { loading: true });
  return promise;
}

function toggleDetail(entry) {
  if (categoryState.openDetails.has(entry.benchmark)) {
    categoryState.openDetails.delete(entry.benchmark);
    renderCategorySections();
    return;
  }

  categoryState.openDetails.add(entry.benchmark);
  renderCategorySections();

  const cacheValue = categoryState.detailCache.get(entry.benchmark_data_path);
  if (!cacheValue) {
    ensureBenchmarkDetail(entry).then(() => {
      renderCategorySections();
    });
  }
}

function renderBenchmarkSection(entry) {
  const rows = sortSummaryRows(filterModelRows(entry.model_rows));
  const passGroups = sortPassGroups(filterPassGroups(entry.passk_groups));

  if (!rows.length && !passGroups.length) {
    return null;
  }

  const section = createNode("section", "benchmark-section");
  const header = createNode("div", "section-head");
  const copy = createNode("div");
  copy.appendChild(createNode("span", "eyebrow", entry.display_name));
  copy.appendChild(createNode("h2", "benchmark-title", entry.display_name));
  copy.appendChild(
    createNode(
      "p",
      "section-note compact-note",
      CATEGORY_META[document.body.dataset.category].emphasis,
    ),
  );
  const meta = createNode(
    "span",
    "panel-meta",
    `${rows.length} summarized rows · ${entry.display_type}`,
  );
  header.append(copy, meta);

  section.append(header, sectionTools(entry));

  if (rows.length) {
    if (document.body.dataset.category === "reasoning" && passGroups.length) {
      section.appendChild(renderPassMilestoneTable(rows, passGroups));
    } else {
      section.appendChild(
        renderAcademicSummaryTable(
          rows,
          entry.benchmark,
          document.body.dataset.category || "",
        ),
      );
    }
  } else {
    section.appendChild(
      createEmptyNote("This benchmark section currently exposes pass@k curves only."),
    );
  }

  if (passGroups.length) {
    section.appendChild(renderPassCards(passGroups));
  }

  if (entry.subset_drilldowns.available) {
    const subsetCountHint = entry.model_rows.length
      ? Math.max(...entry.model_rows.map((row) => row.subset_count || 0))
      : 0;
    let detailLabel = `Show subset details (${entry.subset_drilldowns.row_count} rows)`;
    if (isBfclBenchmark(entry.benchmark)) {
      detailLabel = `Show task-family details (${subsetCountHint || entry.subset_drilldowns.preview_subsets.length} groups)`;
    } else if (isIfEvalBenchmark(entry.benchmark)) {
      detailLabel = "Show metric details";
    } else if (isZebraBenchmark(entry.benchmark)) {
      detailLabel = "Show puzzle breakdown";
    } else if (document.body.dataset.category === "reasoning" && passGroups.length) {
      detailLabel = `Show benchmark splits (${subsetCountHint || entry.subset_drilldowns.preview_subsets.length} subsets)`;
    } else if (document.body.dataset.category === "knowledge" && subsetCountHint) {
      detailLabel = `Show subset details (${subsetCountHint} subsets)`;
    }
    const toggle = createNode(
      "button",
      "detail-toggle",
      categoryState.openDetails.has(entry.benchmark)
        ? "Hide subset details"
        : detailLabel,
    );
    toggle.type = "button";
    toggle.addEventListener("click", () => toggleDetail(entry));
    section.appendChild(toggle);

    if (categoryState.openDetails.has(entry.benchmark)) {
      const detailWrap = createNode("div", "detail-wrap");
      const cached = categoryState.detailCache.get(entry.benchmark_data_path);

      if (!cached || cached.loading) {
        detailWrap.appendChild(createEmptyNote("Loading benchmark detail…"));
        if (!cached) {
          ensureBenchmarkDetail(entry).then(() => {
            renderCategorySections();
          });
        }
      } else if (cached.error) {
        detailWrap.appendChild(
          createEmptyNote(`Could not load benchmark detail: ${cached.error}`),
        );
      } else {
        detailWrap.appendChild(renderSubsetTable(cached));
      }

      section.appendChild(detailWrap);
    }
  }

  return section;
}

function renderCategorySections() {
  if (!categoryState.payload) {
    return;
  }

  const eligibleEntries = sortSectionEntries(
    categoryState.payload.benchmarks.filter(matchesCategoryFilters),
  );
  const fragment = document.createDocumentFragment();
  let visibleSections = 0;

  eligibleEntries.forEach((entry) => {
    const section = renderBenchmarkSection(entry);
    if (section) {
      fragment.appendChild(section);
      visibleSections += 1;
    }
  });

  categoryElements.sectionCount.textContent = `${visibleSections} visible sections`;
  if (!visibleSections) {
    categoryElements.sectionsRoot.replaceChildren(
      createEmptyNote("No benchmark sections match the current filters."),
    );
    return;
  }

  categoryElements.sectionsRoot.replaceChildren(fragment);
}

function wireCategoryFilters() {
  [
    ["model", categoryElements.model],
    ["mode", categoryElements.mode],
    ["benchmark", categoryElements.benchmark],
    ["sort", categoryElements.sort],
  ].forEach(([key, element]) => {
    element.addEventListener("change", (event) => {
      categoryState.filters[key] = event.target.value;
      renderCategorySections();
    });
  });

  categoryElements.reset.addEventListener("click", () => {
    categoryState.filters = {
      model: "",
      mode: "",
      benchmark: "",
      sort: "score_desc",
    };
    categoryElements.model.value = "";
    categoryElements.mode.value = "";
    categoryElements.benchmark.value = "";
    categoryElements.sort.value = "score_desc";
    renderCategorySections();
  });
}

async function initCategoryPage() {
  const category = document.body.dataset.category;
  const payload = await fetchJson(`./data/categories/${category}.json`);
  categoryState.payload = payload;
  categoryState.detailCache = new Map();
  categoryState.openDetails = new Set();

  renderCategoryMeta(payload);
  populateCategoryFilters(payload);
  wireCategoryFilters();
  renderCategorySections();
}

function renderFailure(message) {
  if (homeElements.excludedNote) {
    homeElements.excludedNote.textContent = message;
  }
  if (homeElements.categoryGrid) {
    homeElements.categoryGrid.replaceChildren(createEmptyNote(message));
  }
  if (homeElements.protocolGroups) {
    homeElements.protocolGroups.replaceChildren(createEmptyNote(message));
  }
  if (homeElements.featuredList) {
    homeElements.featuredList.replaceChildren();
  }
  if (categoryElements.description) {
    categoryElements.description.textContent = message;
  }
  if (categoryElements.sectionsRoot) {
    categoryElements.sectionsRoot.replaceChildren(createEmptyNote(message));
  }

  if (homeElements.generatedAt) {
    homeElements.generatedAt.textContent = "Failed";
  }
  if (categoryElements.generatedAt) {
    categoryElements.generatedAt.textContent = "Failed";
  }
}

async function init() {
  try {
    if (isHomePage()) {
      await initHomePage();
      return;
    }
    if (isCategoryPage()) {
      await initCategoryPage();
    }
  } catch (error) {
    renderFailure(`Could not load site data: ${error.message}`);
  }
}

init();
