import CodeMirror from "@uiw/react-codemirror";

export function SparqlEditor(props: {
  title: string;
  value: string;
  onChange?: (value: string) => void;
  placeholder: string;
  readOnly?: boolean;
}) {
  return (
    <section className="code-panel">
      <div className="code-title">
        <span>{props.title}</span>
        <small>
          {props.readOnly ? "read only" : "editable"}
        </small>
      </div>

      {props.value ? (
        <CodeMirror
          value={props.value}
          height="112px"
          editable={!props.readOnly}
          basicSetup={{
            lineNumbers: true,
            foldGutter: false,
            highlightActiveLine: false,
          }}
          onChange={props.onChange}
        />
      ) : (
        <div className="code-empty">
          {props.placeholder}
        </div>
      )}
    </section>
  );
}