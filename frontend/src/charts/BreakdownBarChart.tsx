import { Tooltip, Typography } from 'antd';
import type { BreakdownEntry } from '../api/types';
import { CHART_CHROME, CHARTABLE_STATUSES, STATUS_COLOR, STATUS_LABEL } from './statusPalette';

const NO_RUNS_COLOR = '#c3c2b7'; // one step lighter than `skipped`'s muted gray — a distinct "never run" state, not an outcome.
const BAR_HEIGHT = 20;
const SEGMENT_GAP = 2; // surface gap between touching stacked segments

export interface BreakdownRow {
  label: string;
  entry: BreakdownEntry;
}

interface BreakdownBarChartProps {
  rows: BreakdownRow[];
  testId?: string;
}

/**
 * Horizontal stacked bar chart — one row per dimension bucket (testing
 * level / category / priority), segments in fixed status order plus a
 * trailing "No runs" segment for test cases with zero executions. Horizontal
 * because bucket names (e.g. "business_logic", "performance") can be long —
 * per choosing-a-form: "stacked bar, go horizontal for long-named categories".
 */
export function BreakdownBarChart({ rows, testId }: BreakdownBarChartProps) {
  if (rows.length === 0) {
    return (
      <Typography.Text type="secondary" style={{ display: 'block', padding: '12px 0' }}>
        No data yet.
      </Typography.Text>
    );
  }

  const maxTotal = Math.max(1, ...rows.map((r) => r.entry.total));

  return (
    <div data-testid={testId}>
      {rows.map(({ label, entry }) => {
        const noRuns = Math.max(0, entry.no_runs);
        const segments = [
          ...CHARTABLE_STATUSES.map((status) => ({
            key: status,
            value: entry[status],
            color: STATUS_COLOR[status],
            name: STATUS_LABEL[status],
          })),
          { key: 'no_runs', value: noRuns, color: NO_RUNS_COLOR, name: 'No runs' },
        ].filter((s) => s.value > 0);

        const barWidthPct = (entry.total / maxTotal) * 100;

        return (
          <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 10 }}>
            <Typography.Text style={{ width: 140, flexShrink: 0, fontSize: 12 }} title={label} ellipsis>
              {label}
            </Typography.Text>
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
              <div
                style={{
                  display: 'flex',
                  height: BAR_HEIGHT,
                  width: `${Math.max(barWidthPct, entry.total > 0 ? 2 : 0)}%`,
                  minWidth: entry.total > 0 ? 4 : 0,
                  borderRadius: 4,
                  overflow: 'hidden',
                  background: CHART_CHROME.gridline,
                }}
              >
                {segments.map((seg, i) => (
                  <Tooltip
                    key={seg.key}
                    title={
                      <span>
                        <strong>{seg.value}</strong> {seg.name.toLowerCase()}
                      </span>
                    }
                  >
                    <div
                      style={{
                        width: `${(seg.value / entry.total) * 100}%`,
                        height: '100%',
                        background: seg.color,
                        marginRight: i === segments.length - 1 ? 0 : SEGMENT_GAP,
                      }}
                    />
                  </Tooltip>
                ))}
              </div>
              <Typography.Text type="secondary" style={{ fontSize: 12, flexShrink: 0 }}>
                {entry.total}
              </Typography.Text>
            </div>
          </div>
        );
      })}
    </div>
  );
}
