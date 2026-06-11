import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from 'recharts';
import type { PricePoint } from '../types/stocks';

interface StockPriceChartProps {
  data: PricePoint[];
  compact?: boolean;
  showYAxis?: boolean;
}

export default function StockPriceChart({
  data,
  compact = false
  , showYAxis = false
}: StockPriceChartProps) {
  const formatAxisTick = (value: number | string) => {
    const numericValue = Number(value);
    if (!Number.isFinite(numericValue) || Math.abs(numericValue) > 1_000_000) {
      return '';
    }

    return numericValue.toLocaleString(undefined, {
      maximumFractionDigits: 2
    });
  };

  const chartMargin = compact
    ? (showYAxis ? { top: 4, right: -4, left: -10, bottom: 0 } : { top: 4, right: -4, left: -22, bottom: 0 })
    : (showYAxis ? { top: 8, right: 8, left: 56, bottom: 0 } : { top: 8, right: 8, left: 0, bottom: 0 });

  return (
    <div className={compact ? 'chart compact' : 'chart'}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart
          data={data}
          margin={chartMargin}
        >
          <defs>
            <linearGradient id="stockGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#a385f0" stopOpacity={0.6} />
              <stop offset="95%" stopColor="#606fe6" stopOpacity={0.1} />
            </linearGradient>
          </defs>

          {!compact ? (
            <CartesianGrid strokeDasharray="4 4" stroke="rgba(233, 173, 199, 0.14)" />
          ) : null}

          <XAxis
            dataKey="label"
            padding={compact ? { left: 0, right: 0 } : { left: 8, right: 8 }}
            tick={compact ? false : { fill: '#b5bdd5', fontSize: 12 }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            domain={["auto", "auto"]}
            hide={compact && !showYAxis}
            width={showYAxis ? (compact ? 36 : 48) : 0}
            tick={showYAxis ? { fill: '#b5bdd5', fontSize: compact ? 10 : 12 } : false}
            tickFormatter={showYAxis ? formatAxisTick : undefined}
            axisLine={false}
            tickLine={false}
          />
          {!compact ? (
            <Tooltip
              contentStyle={{
                backgroundColor: '#202531',
                borderColor: 'rgba(233, 173, 199, 0.3)',
                borderRadius: '8px'
              }}
              formatter={(value) => [`$${value}`, 'Price']}
            />
          ) : null}
          <Area
            type="linear"
            dataKey="close"
            stroke="#a385f0"
            strokeWidth={2.2}
            fill="url(#stockGradient)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
