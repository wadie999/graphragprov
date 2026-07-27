interface AppHeaderProps {
  canExport: boolean;
  onExport: () => void;
}

export function AppHeader({
  canExport,
  onExport,
}: AppHeaderProps) {
  return (
    <header className="app-header">
      <div>
        <h1>GraphRAGProv Research Instrument</h1>
        <p>
          First functional interface. No final visual design or
          backend persistence.
        </p>
      </div>

      <button
        type="button"
        onClick={onExport}
        disabled={!canExport}
      >
        Export run JSON
      </button>
    </header>
  );
}
