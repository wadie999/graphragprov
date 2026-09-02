import type { Metric } from "../api/snapshotTypes";

const visible = ["graph.node_count", "graph.edge_count", "graph.occurrence_count", "coverage.text.mean"];

export function MetricsStrip({ metrics }: { metrics: Metric[] }) {
  const selected = visible.map((key) => metrics.find((item) => item.key === key)).filter(Boolean) as Metric[];
  if (!selected.length) return null;
  return <div className="metrics-strip">{selected.map((metric) => (
    <div key={metric.key}><span>{metric.label}</span><strong>{format(metric)}</strong></div>
  ))}</div>;
}

function format(metric: Metric): string {
  if (typeof metric.value === "number" && metric.unit === "%") return `${metric.value.toFixed(1)}%`;
  return `${metric.value}${metric.unit ?? ""}`;
}
