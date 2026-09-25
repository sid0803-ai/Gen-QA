import type { CSSProperties } from 'react';

/**
 * Lightweight, dependency-free JSON syntax highlighter used by the API
 * Performer's Response card (body + headers). Deliberately not pulling in
 * react-json-view / react-syntax-highlighter for what's effectively one
 * regex pass over pretty-printed JSON text — keeps the bundle small.
 *
 * This module is plain data/logic (no JSX) so it can export non-component
 * helpers without tripping the "fast refresh" component-only-exports lint
 * rule; `JsonView.tsx` turns the tokens this produces into React spans.
 */

const TOKEN_COLORS = {
  key: '#a626a4',
  string: '#0a7f3f',
  number: '#005cc5',
  boolean: '#d73a49',
  null: '#6a737d',
};

const JSON_TOKEN_REGEX =
  /("(?:\\u[a-fA-F0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(?:true|false)\b|\bnull\b|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)/g;

export interface JsonToken {
  text: string;
  /** undefined = plain punctuation/whitespace, rendered with no color override. */
  color?: string;
}

/** Tokenizes `text` (expected to be pretty-printed JSON) into colored/plain segments. Never throws — non-JSON or partial text just yields uncolored tokens. */
export function tokenizeJson(text: string): JsonToken[] {
  const tokens: JsonToken[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  JSON_TOKEN_REGEX.lastIndex = 0;
  while ((match = JSON_TOKEN_REGEX.exec(text)) !== null) {
    if (match.index > lastIndex) {
      tokens.push({ text: text.slice(lastIndex, match.index) });
    }
    const token = match[0];
    let color: string;
    if (token.startsWith('"')) {
      color = /:\s*$/.test(token) ? TOKEN_COLORS.key : TOKEN_COLORS.string;
    } else if (token === 'true' || token === 'false') {
      color = TOKEN_COLORS.boolean;
    } else if (token === 'null') {
      color = TOKEN_COLORS.null;
    } else {
      color = TOKEN_COLORS.number;
    }
    tokens.push({ text: token, color });
    lastIndex = JSON_TOKEN_REGEX.lastIndex;
  }
  if (lastIndex < text.length) {
    tokens.push({ text: text.slice(lastIndex) });
  }
  return tokens;
}

/** Attempts `JSON.parse` + pretty-print; returns null if `text` isn't valid JSON (caller falls back to plain rendering). */
export function tryPrettyPrintJson(text: string): string | null {
  try {
    return JSON.stringify(JSON.parse(text), null, 2);
  } catch {
    return null;
  }
}

export const jsonPreStyle: CSSProperties = {
  fontFamily: 'Menlo, Consolas, monospace',
  fontSize: 12,
  background: '#f5f5f5',
  padding: 12,
  borderRadius: 4,
  maxHeight: 400,
  overflow: 'auto',
  whiteSpace: 'pre-wrap',
  wordBreak: 'break-word',
  margin: 0,
};
