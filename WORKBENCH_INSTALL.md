# GraphRAGProv Research Workbench — Installation and First Run

This package is an **overlay for the repository root**. It adds a new research-workbench API and a React frontend without modifying the existing experiment/extraction machinery.

## What it adds

- `src/graphragprov/workbench_api/` — read-only experiment projection + interactive query API
- `frontend/` — React/Vite workbench UI using Sigma.js + Graphology
- `workbench.toml` — single configuration file
- `scripts/run_workbench_dev.py` — development launcher for API + frontend

The persisted experiment filesystem is the authoritative input contract. Interactive work is written under `.workbench/`, not into the frozen experiment directories.

## 1. Back up / branch first

From your current repository root:

```bash
git status --short
git switch -c feat/research-workbench
```

(or use your preferred branch name).

## 2. Extract the overlay

Put the ZIP next to / inside the repository and extract its contents **at the repository root**, where `pyproject.toml` and `src/` already exist.

Example:

```bash
cd ~/graphragprov
unzip ~/Downloads/graphragprov-workbench-overlay-2026-08-29.zip
```

After extraction you should have:

```text
graphragprov/
├── frontend/
├── scripts/
│   └── run_workbench_dev.py
├── src/
│   └── graphragprov/
│       └── workbench_api/
├── workbench.toml
└── pyproject.toml                 # your existing file, unchanged by this overlay
```

No existing stable source file is replaced by this package.

## 3. Edit the single config file

Open `workbench.toml` and verify the paths for your real experiments.

Expected examples:

```toml
[[experiments]]
id = "2wiki-compositional-200-v2"
path = "experiments/runs/2wiki-compositional-200-v2"

[[experiments]]
id = "musique-answerable-200-v2"
path = "experiments/runs/musique-answerable-200-v2"
```

Also verify:

- GraphDB URL/repository
- NPCS URL
- MuSiQue dataset path
- cohort paths
- planner model

All paths are resolved relative to `workbench.toml` unless absolute.

## 4. Install Python dependencies

Inside your existing virtual environment:

```bash
python -m pip install -e ".[api]"
```

For development/testing tools as well:

```bash
python -m pip install -e ".[api,dev]"
```

The workbench reuses your existing GraphRAGProv package and clients; it does not duplicate them.

## 5. Install frontend dependencies

```bash
cd frontend
npm install
cd ..
```

## 6. Configure the planner secret

Only needed for natural-language → SPARQL planning:

```bash
export DEEPSEEK_API_KEY='...'
```

Do not put the key in `workbench.toml` or Git.

Manual artifact inspection does not need the planner. Live SPARQL/provenance execution needs GraphDB/NPCS as appropriate.

## 7. Start GraphDB and NPCS

Start them exactly as you currently do for the experiment runner and ensure the addresses in `workbench.toml` match.

Defaults in the supplied config:

```text
GraphDB  http://localhost:7200/repositories/graphragprov
NPCS     http://localhost:8002/api/content/rewrite
```

## 8. Start the workbench in development mode

From repository root:

```bash
python scripts/run_workbench_dev.py
```

This starts:

- FastAPI: `http://127.0.0.1:8080`
- Vite: `http://127.0.0.1:5173`

Open:

```text
http://127.0.0.1:5173
```

The Vite server proxies `/api` to FastAPI.

## 9. Useful first checks

API health:

```bash
curl http://127.0.0.1:8080/api/v1/system/health
```

Experiments:

```bash
curl http://127.0.0.1:8080/api/v1/experiments
```

Python syntax/import smoke test:

```bash
python -m compileall -q src/graphragprov/workbench_api scripts/run_workbench_dev.py
python -c 'from graphragprov.workbench_api.config import load_config; print(load_config())'
```

Frontend build check:

```bash
cd frontend
npm run build
```

## 10. Production-style local run later

Build the frontend:

```bash
cd frontend
npm run build
cd ..
```

Then the FastAPI application will mount `frontend/dist` automatically:

```bash
export GRAPHRAGPROV_WORKBENCH_CONFIG="$PWD/workbench.toml"
python -m graphragprov.workbench_api
```

Open `http://127.0.0.1:8080`.

## Important invariants

- Experiment `result.json` files are read-only inputs.
- The API projects them into stable workbench DTOs; React does not parse raw experiment JSON.
- Selecting/hovering graph objects is frontend state and does not mutate the backend.
- Editing SPARQL creates a new interactive query run; it does not rebuild or mutate the graph snapshot.
- Natural-language questions generate SPARQL against the selected frozen graph; they do not rerun extraction.
- Interactive run state is stored separately under `.workbench/`.
- GraphDB is treated as disposable execution workspace; experiment artifacts remain authoritative.

## Known handoff status

This is an iterative development handoff, not a declared production release. Python files passed syntax compilation in the packaging environment. Full dependency-backed FastAPI import and the frontend `npm install`/build could not be completed there because the environment lacked installed project dependencies / registry network access. Run the checks above locally and bring back the first concrete error; the architecture is intentionally split into small files so fixes remain local.
