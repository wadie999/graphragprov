# GraphRAGProv frontend instrument

This is the first research interface, not the final visual design.

It is intentionally simple. Its job is to validate the workflow:

- browse experiments and MuSiQue cases;
- keep one benchmark reference visible;
- edit the question and run configuration;
- consume the live NDJSON QA stream;
- navigate turns, result bindings, polynomials, derivations, and occurrences;
- highlight exact source spans;
- display a small provenance graph;
- export the complete browser-side run as JSON.

## Run

Start the FastAPI backend on `127.0.0.1:8000`, then:

```bash
cd frontend
npm install
npm run dev
```

Open the URL printed by Vite, normally `http://127.0.0.1:5173`.

The Vite development server proxies `/api` and `/health` to the backend, so no backend CORS change is required for local development.

## Verify

```bash
npm run typecheck
npm run build
```

## Structure

```text
src/
├── api/          HTTP and NDJSON transport
├── components/   small UI components grouped by responsibility
├── domain/       backend-independent TypeScript contracts
├── state/        experiment loading, stream reduction, and selection
└── utils/        export and runtime guards
```

The frontend stores no run on the backend. Refreshing the page clears browser state. Use **Export run JSON** before refreshing.
