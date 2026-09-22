import { Card, Statistic, Typography } from 'antd';
import type { ReactNode } from 'react';

export interface StatTileProps {
  title: string;
  /** Numeric value to display. Omit (or pass null/undefined) to render `emptyText` instead. */
  value?: number | null;
  suffix?: ReactNode;
  /** Shown when `value` is not provided — e.g. "No data yet". */
  emptyText?: string;
}

/**
 * Reusable dashboard tile. Sprint 1 only ever renders zero/empty states
 * (there's no backend data yet), but later sprints will pass real numbers
 * through the same `value` prop.
 */
export function StatTile({ title, value, suffix, emptyText = 'No data yet' }: StatTileProps) {
  const hasValue = value !== undefined && value !== null;

  return (
    <Card>
      <Typography.Text type="secondary">{title}</Typography.Text>
      <div style={{ marginTop: 8 }}>
        {hasValue ? (
          <Statistic value={value} suffix={suffix} />
        ) : (
          <Typography.Text style={{ fontSize: 20, color: 'rgba(0, 0, 0, 0.45)' }}>
            {emptyText}
          </Typography.Text>
        )}
      </div>
    </Card>
  );
}
