# graphragprov

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
  2hop__153573_109006
```

```bash
graphragprov benchmark musique case \
  2hop__153573_109006 \
  --supports-only
```

### Inspect a source unit

```bash
graphragprov benchmark musique unit \
  u_0cc951978629
```
