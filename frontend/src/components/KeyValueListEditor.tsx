import { useEffect, useRef, useState } from 'react';
import { Button, Input, Space } from 'antd';
import { DeleteOutlined, PlusOutlined } from '@ant-design/icons';

export interface KeyValueListEditorProps {
  value?: Record<string, string>;
  onChange?: (value: Record<string, string>) => void;
  disabled?: boolean;
}

/**
 * Simple add/remove-line-item key-value editor, following the same pattern as
 * `AnalysisPayloadView`'s list handling. Used for Environment `variables`.
 *
 * Rows are kept in local state (not derived fresh from `value` on every
 * render) precisely so a freshly-added row with an empty key can be typed
 * into: since `value` is a plain `Record<string, string>`, a row with an
 * empty key can't be represented in it at all, so deriving rows straight
 * from `value` would make a just-added blank row vanish the instant it's
 * emitted. Local state re-syncs from `value` only when it changes for a
 * reason other than this component's own last emission (e.g. switching which
 * environment is being edited). Two rows that end up with the same key
 * collapse to one on emit — acceptable for this simple v1 editor.
 */
export function KeyValueListEditor({ value, onChange, disabled }: KeyValueListEditorProps) {
  const [rows, setRows] = useState<[string, string][]>(() => Object.entries(value ?? {}));
  const lastEmitted = useRef<Record<string, string> | undefined>(value);

  useEffect(() => {
    if (value !== lastEmitted.current) {
      setRows(Object.entries(value ?? {}));
      lastEmitted.current = value;
    }
  }, [value]);

  const emit = (nextRows: [string, string][]) => {
    setRows(nextRows);
    const next: Record<string, string> = {};
    nextRows.forEach(([k, v]) => {
      if (k) next[k] = v;
    });
    lastEmitted.current = next;
    onChange?.(next);
  };

  const updateKey = (i: number, key: string) => {
    emit(rows.map((row, idx) => (idx === i ? ([key, row[1]] as [string, string]) : row)));
  };
  const updateValue = (i: number, val: string) => {
    emit(rows.map((row, idx) => (idx === i ? ([row[0], val] as [string, string]) : row)));
  };
  const remove = (i: number) => emit(rows.filter((_, idx) => idx !== i));
  const add = () => emit([...rows, ['', '']]);

  return (
    <Space direction="vertical" size={8} style={{ width: '100%' }}>
      {rows.map(([k, v], i) => (
        <Space key={i} style={{ width: '100%' }}>
          <Input
            placeholder="Key"
            value={k}
            disabled={disabled}
            style={{ width: 180 }}
            onChange={(e) => updateKey(i, e.target.value)}
          />
          <Input
            placeholder="Value"
            value={v}
            disabled={disabled}
            style={{ width: 240 }}
            onChange={(e) => updateValue(i, e.target.value)}
          />
          {!disabled && (
            <Button type="text" danger icon={<DeleteOutlined />} onClick={() => remove(i)} />
          )}
        </Space>
      ))}
      {!disabled && (
        <Button type="dashed" size="small" icon={<PlusOutlined />} onClick={add}>
          Add variable
        </Button>
      )}
    </Space>
  );
}
