# graphragprov

**GraphRAGProv** is a research platform for provenance-aware question answering over
knowledge graphs constructed from text.

The current research workflow starts from natural-language source documents, constructs a
grounded RDF graph, asks questions over that graph with SPARQL, executes the query in
GraphDB, and uses NPCS to recover how-provenance back to the exact RDF occurrences and
source evidence that contributed to an answer.

```text
source text
    ↓
LLM RDF extraction
    ↓
deterministic grounding
    ↓
GraphDB
    ↓
LLM-generated SPARQL
    ↓
query execution
    ↓
NPCS provenance rewriting
    ↓
provenance derivation
    ↓
RDF occurrences
    ↓
source spans
```

The repository is currently used primarily for controlled multi-hop QA experiments on
[MuSiQue](https://github.com/StonyBrookNLP/musique).

---

## Setup

Activate the Python environment and configure the external services:

```bash
export DEEPSEEK_API_KEY="..."

export GRAPHRAGPROV_GRAPHDB_URL="http://localhost:7200"
export GRAPHRAGPROV_GRAPHDB_REPOSITORY="graphragprov"

export GRAPHRAGPROV_NPCS_URL="http://localhost:8002"
```

Start GraphDB and NPCS:

```bash
docker start graphdb npcs
```

The MuSiQue dataset is kept outside Git and is resolved through the project configuration.
Commands that accept `--dataset-path` can override the configured path explicitly.

---

# Inspect MuSiQue

The CLI can inspect the benchmark before running an experiment.

```bash
graphragprov benchmark musique --help
```

## List cases

List 3-hop cases:

```bash
graphragprov benchmark musique list \
  --hops 3 \
  --limit 10
```

List only answerable 4-hop cases:

```bash
graphragprov benchmark musique list \
  --hops 4 \
  --limit 10 \
  --answerable-only
```

## Inspect one case

```bash
graphragprov benchmark musique case \
  2hop__525242_52835
```

Show only the supporting paragraphs:

```bash
graphragprov benchmark musique case \
  2hop__525242_52835 \
  --supports-only
```

A case inspection shows the question, answer, decomposition, paragraph indices, source-unit
IDs, titles, and source text.

## Inspect one source unit

```bash
graphragprov benchmark musique unit \
  u_0cc951978629
```

Source units have stable IDs so the same textual source can be tracked across cases and
experiments.

---

# Generate grounded RDF graphs

A graph-only MuSiQue experiment can be run independently of question answering.

The command selects MuSiQue cases, extracts grounded RDF statements from their source
paragraphs, measures source coverage, and materializes the resulting graph into GraphDB.

```bash
python -m graphragprov.experiments.musique_materialization \
  --experiment-id musique-3hop-reference \
  --hop-count 3 \
  --limit 10 \
  --model deepseek-v4-flash \
  --max-tokens 16384 \
  --verbose
```

By default, only answerable cases are selected.

| Argument | Meaning |
|---|---|
| `--experiment-id` | Name of the persisted experiment under `runs/`. |
| `--hop-count` | Select MuSiQue cases with exactly this number of hops. |
| `--limit` | Number of matching cases to use. Default: `5`. |
| `--include-unanswerable` | Include unanswerable cases. They are excluded by default. |
| `--dataset-path` | Override the configured MuSiQue JSONL path. |
| `--runs-root` | Root directory for experiment artifacts. Default: `runs`. |
| `--model` | DeepSeek model used for RDF extraction. |
| `--max-tokens` | Maximum output-token budget per model request. |
| `--cache-root` | Override the extraction checkpoint/cache directory. |
| `--retry-failures` | Re-run failed cached extractions while keeping successful ones. |
| `--replace-repository` | Explicitly clear the current GraphDB repository before materialization. |
| `--verbose` | Print grounding, correction, and source-coverage diagnostics. |

`--replace-repository` is intentionally explicit because it clears the currently materialized
GraphDB experiment.

---

# H0 multi-hop fidelity experiment

The current H0 protocol constructs an executable reference artifact for one MuSiQue case:

```text
gold supporting paragraphs
       ↓
grounded reference RDF graph
       ↓
frozen graph
       ↓
reference query construction
       ↓
GraphDB execution
       ↓
NPCS provenance
       ↓
exact source occurrences
```

The runtime is designed primarily as a **collector**. Scientific judgments such as answer
correctness, shortcut reasoning, dependency fidelity, and semantic graph fidelity belong to
offline evaluation rather than controlling collection.

## Run one case

```bash
python -m graphragprov.experiments.multihop_fidelity.run_one \
  --case-id 2hop__445963_6063 \
  --query-scope support \
  --artifacts runs/multihop_fidelity/example \
  --model deepseek-v4-flash \
  --max-tokens 16384 \
  --max-source-attempts 3 \
  --max-query-attempts 5 \
  --llm-timeout-seconds 60 \
  --verbose
```

The verbose mode shows the complete scientific trace:

```text
REFERENCE GRAPH EXTRACTION
DETERMINISTIC GROUNDING
SOURCE COVERAGE
MATERIALIZATION
FROZEN SEMANTIC GRAPH
QUERY
GRAPHDB RESULT
PROVENANCE
TOKEN USAGE
STAGE TIMINGS
```

### `run_one` arguments

| Argument | Meaning |
|---|---|
| `--case-id` | MuSiQue case to execute. Required. |
| `--query-scope support` | Execute only over the case's supporting named graphs. This is the main controlled H0 condition. |
| `--query-scope repository` | Execute the semantic query over GraphDB's repository-wide dataset. |
| `--dataset-path` | Override the configured MuSiQue dataset. |
| `--artifacts` | Root directory in which the case result and checkpoints are persisted. |
| `--model` | DeepSeek model used for graph and query generation. |
| `--max-tokens` | Maximum output-token budget for one LLM request. Default: `16384`. |
| `--max-source-attempts` | Maximum whole-source extraction attempts after mechanical/grounding failure. Default: `3`. |
| `--max-query-attempts` | Maximum query-generation attempts after mechanically invalid responses. Default: `5`. |
| `--llm-timeout-seconds` | Timeout for one DeepSeek request. Transport retries are disabled. |
| `--reuse-llm-checkpoints` | Resume an interrupted run by reusing prompt-matched stored LLM responses. |
| `--verbose` | Print the complete readable execution trace. |

A result is written under:

```text
<artifacts>/<case-id>/<query-scope>/result.json
```

The artifact records the experiment configuration, source extractions, frozen graph,
generated query, execution result, provenance result, source occurrences, telemetry, and
timings.

### Resume an interrupted case

LLM calls are checkpointed by call order and exact prompt hash. To continue an interrupted
execution without paying again for completed identical requests:

```bash
python -m graphragprov.experiments.multihop_fidelity.run_one \
  --case-id 2hop__445963_6063 \
  --query-scope support \
  --artifacts runs/multihop_fidelity/example \
  --reuse-llm-checkpoints \
  --verbose
```

Checkpoint reuse is deliberately strict: if the prompt sequence changes, the stored call is
not silently reused.

---

# Run a cohort in parallel

`run_many` is a thin scheduler around `run_one`. Each case is still executed by the same
one-case worker.

Create a text file containing one MuSiQue case ID per line:

```text
2hop__445963_6063
3hop1__145411_443779_52195
4hop1__342858_131850_33952_34053
```

Then run:

```bash
python -m graphragprov.experiments.multihop_fidelity.run_many \
  --case-ids-file experiments/cohorts/h0-100-v2.txt \
  --workers 4 \
  --query-scope support \
  --artifacts runs/multihop_fidelity/h0-100-v2 \
  --model deepseek-v4-flash \
  --max-tokens 16384 \
  --max-source-attempts 3 \
  --max-query-attempts 5 \
  --llm-timeout-seconds 60
```

This is the command used for the frozen H0 100-case experiment.

### `run_many` arguments

| Argument | Meaning |
|---|---|
| `--case-ids-file` | Text file containing one MuSiQue case ID per line. |
| `--workers` | Maximum number of cases executed concurrently. |
| `--query-scope` | Passed through to `run_one`: `support` or `repository`. |
| `--dataset-path` | Optional MuSiQue dataset override passed to each worker. |
| `--artifacts` | Shared batch artifact root; each case gets its own directory. |
| `--model` | LLM model passed to every case. |
| `--max-tokens` | LLM output-token limit passed to every case. |
| `--max-source-attempts` | Extraction-attempt bound passed to every case. |
| `--max-query-attempts` | Query-generation-attempt bound passed to every case. |
| `--llm-timeout-seconds` | Timeout for each LLM request. |
| `--resume` | Skip cases that already have a completed `result.json`; incomplete cases resume from their LLM checkpoints. |

`run_many` streams each worker's verbose output with its case identifier, while also saving
per-case logs and a batch summary.

Cases that share source units are not run concurrently, preventing simultaneous
case-conditioned writes to the same GraphDB named graph.

For repository-wide execution, use a single worker:

```bash
python -m graphragprov.experiments.multihop_fidelity.run_many \
  --case-ids-file experiments/cohorts/h0-100-v2.txt \
  --workers 1 \
  --query-scope repository \
  --artifacts runs/multihop_fidelity/h0-100-repository
```

---

# Golden H0 experiment

The repository preserves the first frozen 100-case H0 run:

```text
experiments/cohorts/h0-100-v2.txt
runs/multihop_fidelity/h0-100-v2/
```

The cohort contains:

```text
33 × 2-hop
33 × 3-hop
34 × 4-hop
```

The `runs/` directory is normally experimental output, but this run is intentionally
version-controlled as a research artifact.

Raw `result.json` files should be treated as immutable observations. Evaluation and derived
judgments should be stored separately rather than written back into collection artifacts.

---

# Development

Run the complete validation gate before committing experiment-code changes:

```bash
ruff check --fix src tests && \
ruff format src tests && \
ruff check src tests && \
mypy src tests && \
pytest -q && \
git diff --check
```

---

# Current research direction

GraphRAGProv is being developed as an experimental instrument for studying a distinction that
end-answer accuracy alone cannot expose:

```text
correct answer
      ≠
correct computation
      ≠
correct provenance target
```

The project therefore keeps the following objects separately observable:

```text
benchmark decomposition
frozen RDF graph
query-agent claimed evidence
actual SPARQL computation
database answer
database provenance
exact source occurrences
```

The next evaluation layer operates over these frozen artifacts to study graph adequacy,
query executability, answer correctness, provenance coverage, and multi-hop derivation
fidelity.