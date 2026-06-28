/** Textarea that edits a JSON object and reports parse validity to the parent. */

import { useEffect, useState } from "react";
import type { Json } from "../types";

interface Props {
  value: Json;
  onChange: (value: Json, valid: boolean) => void;
  rows?: number;
}

export function JsonEditor({ value, onChange, rows = 4 }: Props) {
  const [text, setText] = useState(() => JSON.stringify(value, null, 2));
  const [error, setError] = useState<string>();

  // Re-sync when the parent resets the value (e.g. after a successful save).
  useEffect(() => {
    setText(JSON.stringify(value, null, 2));
    setError(undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(value)]);

  function handle(next: string) {
    setText(next);
    if (next.trim() === "") {
      setError(undefined);
      onChange({}, true);
      return;
    }
    try {
      const parsed = JSON.parse(next) as Json;
      setError(undefined);
      onChange(parsed, true);
    } catch (err) {
      setError((err as Error).message);
      onChange(value, false);
    }
  }

  return (
    <div>
      <textarea
        className={`json-editor ${error ? "invalid" : ""}`}
        rows={rows}
        value={text}
        spellCheck={false}
        onChange={(e) => handle(e.target.value)}
      />
      {error && <span className="field-hint error-text">Invalid JSON: {error}</span>}
    </div>
  );
}
