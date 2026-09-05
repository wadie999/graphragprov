import { useRef } from "react";
import CodeMirror from "@uiw/react-codemirror";
import { EditorView } from "@codemirror/view";

export function SparqlEditor(props: {
  title: string;
  value: string;
  onChange?: (value: string) => void;
  placeholder: string;
  readOnly?: boolean;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const title = props.title.replace("NPCS", "SparqlProv");

  function editor() {
    return (
      <CodeMirror
        value={props.value}
        placeholder={props.placeholder}
        editable={!props.readOnly}
        readOnly={Boolean(props.readOnly)}
        extensions={[EditorView.lineWrapping]}
        basicSetup={{
          lineNumbers: true,
          foldGutter: false,
          highlightActiveLine: !props.readOnly,
        }}
        onChange={props.onChange}
        aria-label={title}
      />
    );
  }

  return (
    <section className="code-panel">
      <div className="code-title">
        <span>{title}</span>
        <button
          type="button"
          className="secondary-button"
          onClick={() => dialog.current?.showModal()}
        >
          Expand
        </button>
      </div>

      {editor()}

      <dialog
        ref={dialog}
        className="query-dialog"
        aria-label={title}
      >
        <div className="query-dialog-header">
          <strong>{title}</strong>
          <span>{props.readOnly ? "Read only" : "Changes apply immediately"}</span>
          <button
            type="button"
            className="secondary-button"
            autoFocus
            onClick={() => dialog.current?.close()}
          >
            Close · Esc
          </button>
        </div>
        <div className="query-dialog-editor">
          {editor()}
        </div>
      </dialog>
    </section>
  );
}
