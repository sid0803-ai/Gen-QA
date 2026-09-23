import { useMemo, useState } from 'react';
import { Typography } from 'antd';
import type { TrendPoint } from '../api/types';
import { CHART_CHROME, CHARTABLE_STATUSES, STATUS_COLOR, STATUS_LABEL } from './statusPalette';

const WIDTH = 760;
const HEIGHT = 280;
const MARGIN = { top: 12, right: 16, bottom: 28, left: 40 };
const PLOT_W = WIDTH - MARGIN.left - MARGIN.right;
const PLOT_H = HEIGHT - MARGIN.top - MARGIN.bottom;

/** Rounds a max value up to a "clean" tick ceiling (1/2/5 * 10^n) — per marks-and-anatomy: axis ticks round to clean numbers. */
function niceMax(value: number): number {
  if (value <= 0) return 4;
  const magnitude = Math.pow(10, Math.floor(Math.log10(value)));
  const normalized = value / magnitude;
  const step = normalized <= 1 ? 1 : normalized <= 2 ? 2 : normalized <= 5 ? 5 : 10;
  return step * magnitude;
}

function formatDateShort(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

interface TrendChartProps {
  data: TrendPoint[];
}

/**
 * Multi-line trend chart — one 2px line per terminal execution status, fixed
 * status colors (never cycled categorical hues, since this genuinely is
 * status data — see `statusPalette.ts`), a crosshair+tooltip hover layer,
 * and a legend (mandatory for >=2 series). Handles the empty-data case
 * (zero-filled trend with no executions at all) without crashing.
 */
export function TrendChart({ data }: TrendChartProps) {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  const maxY = useMemo(() => {
    let max = 0;
    for (const point of data) {
      for (const status of CHARTABLE_STATUSES) {
        max = Math.max(max, point[status]);
      }
    }
    return niceMax(max);
  }, [data]);

  if (data.length === 0) {
    return (
      <div data-testid="reports-trend-chart" style={{ padding: 32, textAlign: 'center' }}>
        <Typography.Text type="secondary">No execution activity in this range yet.</Typography.Text>
      </div>
    );
  }

  const xFor = (i: number) =>
    data.length === 1 ? PLOT_W / 2 : (i / (data.length - 1)) * PLOT_W;
  const yFor = (v: number) => PLOT_H - (v / maxY) * PLOT_H;

  const linePaths = CHARTABLE_STATUSES.map((status) => {
    const d = data
      .map((point, i) => `${i === 0 ? 'M' : 'L'} ${xFor(i).toFixed(2)} ${yFor(point[status]).toFixed(2)}`)
      .join(' ');
    return { status, d };
  });

  const yTicks = [0, 0.25, 0.5, 0.75, 1].map((f) => Math.round(maxY * f));
  // Show at most ~8 x-axis labels so dense ranges (90 days) stay legible.
  const labelStride = Math.max(1, Math.ceil(data.length / 8));

  const hovered = hoverIndex != null ? data[hoverIndex] : null;

  const handleMove = (e: React.PointerEvent<SVGRectElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const relX = e.clientX - rect.left;
    const ratio = data.length === 1 ? 0 : relX / rect.width;
    const idx = Math.min(data.length - 1, Math.max(0, Math.round(ratio * (data.length - 1))));
    setHoverIndex(idx);
  };

  return (
    <div data-testid="reports-trend-chart">
      {/* Legend — mandatory for >=2 series; a short line-key rather than a box, mirroring the line mark. */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, marginBottom: 8 }}>
        {CHARTABLE_STATUSES.map((status) => (
          <div key={status} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span
              aria-hidden
              style={{ display: 'inline-block', width: 14, height: 2, background: STATUS_COLOR[status] }}
            />
            <Typography.Text style={{ fontSize: 12 }} type="secondary">
              {STATUS_LABEL[status]}
            </Typography.Text>
          </div>
        ))}
      </div>

      <div style={{ position: 'relative' }}>
        <svg
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          width="100%"
          height={HEIGHT}
          role="img"
          aria-label="Executions by status over time"
        >
          <g transform={`translate(${MARGIN.left},${MARGIN.top})`}>
            {/* Gridlines — hairline, recessive, one-step-off-surface gray */}
            {yTicks.map((tick) => (
              <g key={tick}>
                <line
                  x1={0}
                  x2={PLOT_W}
                  y1={yFor(tick)}
                  y2={yFor(tick)}
                  stroke={CHART_CHROME.gridline}
                  strokeWidth={1}
                />
                <text x={-8} y={yFor(tick)} textAnchor="end" dominantBaseline="middle" fontSize={11} fill={CHART_CHROME.textMuted}>
                  {tick.toLocaleString()}
                </text>
              </g>
            ))}

            {/* X labels */}
            {data.map((point, i) =>
              i % labelStride === 0 ? (
                <text
                  key={point.date}
                  x={xFor(i)}
                  y={PLOT_H + 18}
                  textAnchor="middle"
                  fontSize={11}
                  fill={CHART_CHROME.textMuted}
                >
                  {formatDateShort(point.date)}
                </text>
              ) : null,
            )}

            {/* Lines */}
            {linePaths.map(({ status, d }) => (
              <path key={status} d={d} fill="none" stroke={STATUS_COLOR[status]} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
            ))}

            {/* End-markers with surface ring */}
            {CHARTABLE_STATUSES.map((status) => {
              const last = data[data.length - 1];
              return (
                <circle
                  key={status}
                  cx={xFor(data.length - 1)}
                  cy={yFor(last[status])}
                  r={4}
                  fill={STATUS_COLOR[status]}
                  stroke={CHART_CHROME.surface}
                  strokeWidth={2}
                />
              );
            })}

            {/* Crosshair */}
            {hoverIndex != null && (
              <line
                x1={xFor(hoverIndex)}
                x2={xFor(hoverIndex)}
                y1={0}
                y2={PLOT_H}
                stroke={CHART_CHROME.baseline}
                strokeWidth={1}
              />
            )}

            {/* Hover hit layer — the mark is wider than the painted line per interaction.md */}
            <rect
              x={0}
              y={0}
              width={PLOT_W}
              height={PLOT_H}
              fill="transparent"
              onPointerMove={handleMove}
              onPointerLeave={() => setHoverIndex(null)}
              data-testid="reports-trend-hover-layer"
            />
          </g>
        </svg>

        {hovered && hoverIndex != null && (
          <div
            role="tooltip"
            style={{
              position: 'absolute',
              left: Math.min(WIDTH - 180, MARGIN.left + xFor(hoverIndex) + 12),
              top: MARGIN.top,
              background: CHART_CHROME.surface,
              border: `1px solid ${CHART_CHROME.gridline}`,
              borderRadius: 6,
              padding: '8px 10px',
              boxShadow: '0 2px 8px rgba(0,0,0,0.12)',
              pointerEvents: 'none',
              minWidth: 150,
            }}
          >
            <Typography.Text strong style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
              {formatDateShort(hovered.date)}
            </Typography.Text>
            {CHARTABLE_STATUSES.map((status) => (
              <div key={status} style={{ display: 'flex', justifyContent: 'space-between', gap: 12, fontSize: 12 }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: 6, color: CHART_CHROME.textSecondary }}>
                  <span aria-hidden style={{ width: 8, height: 8, borderRadius: '50%', background: STATUS_COLOR[status], display: 'inline-block' }} />
                  {STATUS_LABEL[status]}
                </span>
                <strong>{hovered[status]}</strong>
              </div>
            ))}
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, fontSize: 12, marginTop: 4, borderTop: `1px solid ${CHART_CHROME.gridline}`, paddingTop: 4 }}>
              <span style={{ color: CHART_CHROME.textSecondary }}>Total</span>
              <strong>{hovered.total}</strong>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
