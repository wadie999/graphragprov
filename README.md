<p align="center">
  <img src="frontend/public/graphragprov-logo.png" alt="GraphRAGProv" width="520">
</p>

Ask questions over text-derived knowledge graphs. Inspect executed SPARQL,
how-provenance polynomials, and the exact source spans behind each answer.

## Run

Requires Git and Docker Compose.

```bash
git clone https://github.com/wadie999/graphragprov.git
cd graphragprov
git submodule update --init --recursive
mkdir -p secrets
```

Request a [GraphDB Free license](https://graphdb.ontotext.com/).
Save the license for GraphDB 11.3.1 as:

```text
secrets/graphdb.license
```

Then start:

```bash
export DEEPSEEK_API_KEY="your-api-key"
docker compose up --build
```

Open **http://localhost:8080**.

The API key is needed for LLM extraction and question-to-SPARQL generation.
Inspecting saved results and executing existing SPARQL do not require it.

Stop with `Ctrl+C`. Restart with the same command.

## Experiments

Configure datasets and experiments in `workbench.toml`.

| Folder | Contents |
|---|---|
| `experiments/cohorts/` | Selected case IDs and cohort datasets |
| `experiments/runs/` | Experiment outputs |
| `external/benchmarks/` | Benchmark datasets |

Dataset and run paths must exist inside the container.
Configure their mounts in `compose.yaml`.

## Development

With Docker services running, develop the frontend with live reload:

```bash
cd frontend
npm ci
npm run dev
```

Open **http://localhost:5173**. API requests go to the backend on port 8080.

After Python or deployment changes, rebuild:

```bash
docker compose up --build
```

## Provenance engine and papers

- [SparqlProv](https://github.com/wadie999/sparql-prov) — Rust provenance rewriting engine
- [NPCS paper](https://doi.org/10.1145/3589334.3645557) — Original provenance method
- [NPCS Java repository](https://github.com/ZubariaForthAcc/NPCS) — Java Reference implementation.
  