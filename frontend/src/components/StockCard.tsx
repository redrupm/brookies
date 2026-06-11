import { Link } from 'react-router-dom';
import type { StockCardData } from '../types/stocks';
import StockPriceChart from './StockPriceChart';

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
  const changeTone = changePercent >= 0 ? 'change-positive' : 'change-negative';

  return (
    <Link to={`/stock/${stockData.stock.ticker}`} className="stock-card">
      <div className="stock-card-top">
        <div>
          <p className="stock-symbol">{stock.ticker}</p>
          <p className="stock-name">{stock.companyName}</p>
        </div>
        <span className={`grade-badge ${stockCard.grade.toLowerCase()}`}>{stockCard.grade}</span>
      </div>

      {/* <p className="stock-subtitle">{subtitle}</p>
      {detailLines?.length ? (
        <div className="stock-card-details">
          {detailLines.map((line) => (
            <span key={line} className="stock-card-detail">
              {line}
            </span>
          ))}
        </div>
      ) : null} */}
      <StockPriceChart data={prices} compact />

      <div className="stock-card-bottom">
        <p>${lastPrice.toFixed(2)}</p>
        <p className={changeTone}>
          {changePercent >= 0 ? '+' : ''}
          {changePercent.toFixed(2)}%
        </p>
      </div>
    </Link>
  );
}
