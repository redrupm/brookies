import { useEffect, useState } from 'react';
import StockCard from '../components/StockCard';
import type { StockData } from '../types/stocks';
import { getAllStockData } from '../api/apiCaller'

export default function Dashboard() {

//    const holdings = getPortfolio();
    const [stockData, setStockData] = useState<StockData[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string>("");
    const [refreshing, setRefreshing] = useState(false);

    useEffect(() => {
        if (loading) return;
        async function load(){
            if (loading) return;
            try {
                setLoading(true);
                const data = await getAllStockData();
                setStockData(data);
            } catch (error) {
                if (error instanceof Error) {
                    setError(error.message);
                } else {
                    setError(String(error));
                }
            } finally {
                setLoading(false);
            }
        }
        load();
        setRefreshing(false);
    }, [refreshing]);    

    const refresh = () => {
        setRefreshing(true);
    };

    return (
        <section className="page">
            <button onClick={refresh}>Refresh</button>
            <div className="panel">
                {/*<h2>Stocks You Own</h2>
                {holdings.length ? (
                <div className="stock-grid">
                    {holdings.map(({ stock, subtitle, detailLines }) => (
                    <StockCard
                        key={`owned-${stock.symbol}`}
                        stock={stock}
                        subtitle={subtitle}
                        detailLines={detailLines}
                    />
                    ))}
                </div>
                ) : ( */}
                {/* <p className="placeholder">
                    Your owned section is currently empty. Add a ticker above to start
                    tracking your portfolio.
                </p>
                )} */}
            </div>
            <div className="panel">
                <h2>Prospective Stocks</h2>
                    {loading ? <p className="placeholder">Refreshing stock data...</p> : null}
                    {error ? <p className="placeholder">Using fallback data: {error}</p> : null}
                <div className="stock-grid">
                    {stockData.map((stock) => (
                        <StockCard
                        key = {`prospective-${stock.stock.ticker}`}
                        stockData = {stock}
                        grade = {stock.grade}
                        label = {"1M"}
                        />
                    ))}
                </div>
            </div>
        </section>
    );
}       