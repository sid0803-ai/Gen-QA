import { Fragment } from 'react';
import { jsonPreStyle, tokenizeJson, tryPrettyPrintJson } from '../utils/jsonHighlight';

/**
 * Renders `text` as syntax-highlighted, pretty-printed JSON when it parses as
 * JSON; otherwise falls back to plain monospace text. Used by the API
 * Performer's Response card for both the response body and response headers.
 */
export function JsonOrPlainView({
  text,
  emptyText = '',
}: {
  text: string;
  emptyText?: string;
}) {
  if (!text) {
    return (
      <pre style={jsonPreStyle}>
        <span style={{ color: '#8c8c8c' }}>{emptyText}</span>
      </pre>
    );
  }

  const pretty = tryPrettyPrintJson(text);
  if (pretty === null) {
    return <pre style={jsonPreStyle}>{text}</pre>;
  }

  const tokens = tokenizeJson(pretty);
  return (
    <pre style={jsonPreStyle}>
      {tokens.map((token, i) => (
        <Fragment key={i}>
          {token.color ? <span style={{ color: token.color }}>{token.text}</span> : token.text}
        </Fragment>
      ))}
    </pre>
  );
}
