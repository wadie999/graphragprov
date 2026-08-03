# graphragprov

## run the system 

```bash
export DEEPSEEK_API_KEY=xx
export GRAPHRAGPROV_GRAPHDB_URL="http://localhost:7200"
export GRAPHRAGPROV_GRAPHDB_REPOSITORY="graphragprov"
export GRAPHRAGPROV_NPCS_URL="http://localhost:8002"
docker start graphdb npcs
```

## Inspect MuSiQue

```bash
graphragprov benchmark musique --help
```

### List cases

```bash
graphragprov benchmark musique list \
  --hops 3 \
  --limit 10
```

```bash
graphragprov benchmark musique list \
  --hops 4 \
  --limit 10 \
  --answerable-only
```

### Inspect a case

```bash
graphragprov benchmark musique case \
  2hop__525242_52835
```

```bash
graphragprov benchmark musique case \
  2hop__231890_595414 \
  --supports-only
```

### Inspect a source unit

```bash
graphragprov benchmark musique unit \
  u_0cc951978629
```

```bash
python -m uvicorn graphragprov.api.app:app --reload
```

```bash
url -sS http://127.0.0.1:8000/health \
  | python -m json.tool

curl -sS http://127.0.0.1:8000/api/v1/experiments \
  | python -m json.tool

curl -sS http://127.0.0.1:8000/api/v1/experiments/musique_pilot \
  | python -m json.tool
```