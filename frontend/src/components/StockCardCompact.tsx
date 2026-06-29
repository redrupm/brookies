
import type { StockCardData } from '../types/stocks';
import {
  ComposedChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Area            
} from "recharts";
import type { TooltipProps } from "recharts";
import '../styles/StockCardCompact.css';

export default function StockCard(stockCard: StockCardData) {
  const stockData = stockCard.stockData;
  const stock = stockData.stock;
  let prices = null;
  if (stockCard.label === '1D'){
    prices = stockData.prices['1D']
  } else if (stockCard.label == '5D'){
    prices = stockData.prices['5D']
  } else if (stockCard.label == '1M'){
    prices = stockData.prices['1M']
  } else if (stockCard.label == '6M'){
    prices = stockData.prices['6M']
  } else {
    prices = stockData.prices['1Y']
  }
  if(!prices || prices.length === 0){
    console.log(`No price data available for ${stock.ticker} with label ${stockCard.label}`);
    return null;
  }
  const lastPrice = prices[prices.length - 1]?.close ?? 0;
  const changePercent = ((lastPrice - prices[0].close) / (prices[0].close || 1)) * 100; 
  const changeTone = changePercent >= 0 ? 'stockPercentPositive' : 'stockPercentNegative';
  changeTone.toString();
  
  return (
    <div className="stockChartContainer">
      <div className="stockChartTitle">
        <p>{stock.ticker}</p>
        <p className={"stockChartGrade" + stockData.grade}>{stockData.grade}</p>
      </div>
      <p className="stockChartSubtitle">{stock.companyName}</p>
      <div className="stockChart">
        <ResponsiveContainer>
          <ComposedChart data={prices} margin={{ top: 10, right: 15, left: -25, bottom: 15 }}>
            <defs>
              <linearGradient id="lineGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#2855c6" stopOpacity={0.8} />
                <stop offset="100%" stopColor="#1b47b6" stopOpacity={0} />
              </linearGradient>
            </defs>
            {/* <CartesianGrid strokeDasharray="3 3" /> */}
            <XAxis dataKey="label" hide />
            <YAxis hide={false}
              tick={{ fill: "rgba(255,255,255,0.55)", fontSize: 11 }}
              tickFormatter={(value) => Math.round(value).toString()}
              tickLine={false}
              axisLine={{ stroke: "rgba(255,255,255,0.15)", strokeWidth: 1 }}
              domain={["dataMin - 1", "dataMax + 1"]} />
            <Tooltip content={<CustomTooltip />} />
            <Area
              type="monotone"
              dataKey="close"
              stroke="none"
              fill="url(#lineGradient)"
              fillOpacity={1}
              activeDot={{ r: 6 }}
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="close"
              stroke="#4876e8"
              strokeWidth={1.75}
              dot={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <div className="stockChartTitle">
        <p className="stockPrice">${lastPrice}</p>
        <p className={changeTone}>{Math.round(changePercent * 100)/ 100}%</p>
      </div>
    </div>
  );
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{ date: string, value: number }>;
  label?: string | number;
}

export const CustomTooltip: React.FC<CustomTooltipProps> = ({
  active,
  payload,
  label
}) => {
  if (!active || !payload || payload.length === 0) return null;

  const close = payload[0].value;

  return (
    <div className="custom-tooltip">
      <p>Date: {label}</p>
      <p>Close: ${close}</p>
    </div>
  );
};
