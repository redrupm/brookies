import {useEffect, useState} from 'react';
import {getAllStockData} from "../api/apiCaller";
import StockCard from '../components/StockCardCompact';
import type {StockData} from '../types/stocks';
import '../styles/Dashboard.css';
import { useNavigate } from 'react-router-dom';

export default function Dashboard() {
    const [allStockData, setAllStockData] = useState<StockData[]>([]);
    const navigate = useNavigate();
    useEffect(() => {
        fetchData();
    }, []); 

    const fetchData = async () => {
        const cacheData = JSON.parse(localStorage.getItem("cacheData") || "[]");
        const unparsedCacheTime = localStorage.getItem("cacheTime");
        const cacheTime = unparsedCacheTime ? new Date(unparsedCacheTime) : null;
        try {
            const currentDate = new Date();
            if(!cacheTime || !cacheData || !cacheData.length || !(
                    currentDate.getFullYear() === cacheTime.getFullYear()
                    && currentDate.getMonth() === cacheTime.getMonth()
                    && currentDate.getDate() === cacheTime.getDate())) {
                const data = await getAllStockData(); 
                setAllStockData(data);
                localStorage.setItem("cacheData", JSON.stringify(data));
                localStorage.setItem("cacheTime", new Date().toISOString());
            } else {
                setAllStockData(cacheData);
            }                    
        } catch (error) {
            console.error("Failed to fetch stock data:", error);
        }
    };

    return (
        <div>
            <p className="stockDisplayHeader">Your Stocks</p>
            <div className="stockCardDisplay">
                {allStockData.map((stockData) => {
                    if(stockData){
                        return (
                            <div className="stockCardClickable" 
                                onClick={() => navigate('/stock/' + stockData.stock.ticker)}>
                                <StockCard 
                                key={stockData.stock.ticker}
                                stockData={stockData} 
                                label="1M"
                                />
                            </div>    
                        );
                    }
                })}
            </div>
            <p className="stockDisplayHeader">Prospective Stocks</p>
            <div className="stockCardDisplay">
                {allStockData.map((stockData) => {
                    if(stockData){
                        return (
                            <StockCard 
                                key={stockData.stock.ticker}
                                stockData={stockData} 
                                label="1M"
                            />
                        );
                    }
                })}
            </div>
        </div>
    );
}       