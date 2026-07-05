import { useParams } from "react-router-dom";
import { useState } from "react";
import '../styles/StockDetail.css';
import type { StockData } from '../types/stocks';
import StockCard from '../components/StockCard';

export default function StockDetail() {
  let { symbol } = useParams();
  const [label, setLabel] = useState("1M");
  const cacheData = JSON.parse(localStorage.getItem("cacheData") || "[]");
  const stockData = cacheData.find(
      (s: StockData) => s.stock.ticker.toUpperCase() === symbol?.toUpperCase()
    );

   if (!stockData) {
    return <p>Stock not found</p>;
  }
  return (
    <div className="stockDetailPage">
      <p className="stockTicker">{symbol}</p>
      <div className="stockTitlePlacement">
        <p className="stockCompanyDetails">{stockData.stock.companyName} • {stockData.stock.sector}</p>
        <div className="dateLabelContainer">
          <p className="dateLabelTitle">Time Range</p>
          <div className="dateLabels">
            <button 
              className={label === "1D" ? "active" : ""} 
              onClick={() => setLabel("1D")}
            > 
              1D
            </button>
            <button 
              className={label === "5D" ? "active" : ""} 
              onClick={() => setLabel("5D")}
            >
              5D
            </button>
            <button 
              className={label === "1M" ? "active" : ""} 
              onClick={() => setLabel("1M")}
            >
              1M
            </button>
            <button 
              className={label === "6M" ? "active" : ""} 
              onClick={() => setLabel("6M")}
            >
              6M
            </button>
            <button 
              className={label === "1Y" ? "active" : ""} 
              onClick={() => setLabel("1Y")}
            >
              1Y
            </button>
          </div>
        </div>
      </div>  
      <StockCard key={symbol}
        stockData={stockData} 
        label={label}></StockCard>
    </div>
  );
}
