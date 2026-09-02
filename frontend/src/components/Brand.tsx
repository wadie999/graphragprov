import { Network } from "lucide-react";

export function Brand() {
  return (
    <div className="brand">
      <span className="brand-mark"><Network size={20} /></span>
      <span><strong>GraphRAGProv</strong><small>Research Workbench</small></span>
    </div>
  );
}
