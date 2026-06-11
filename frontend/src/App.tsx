import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import Portfolio from "./pages/Portfolio";
import StockDetail from "./pages/StockDetail";
import Help from "./pages/Help";
import Simulation from "./pages/Simulation";

export default function App() {
  return (
      <div className="app-shell">
        <header className="top-bar">
          <p className="brand-mark">AI INVESTMENT HELPER</p>
          <nav>
            <NavLink to="/" end>
              Dashboard
            </NavLink>
            <NavLink to="/portfolio" end>
              Portfolio
            </NavLink>
            <NavLink to="/simulation" end>
              Simulation
            </NavLink>
            <NavLink to="/help">Help</NavLink>
          </nav>
        </header>

        <main>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/portfolio" element={<Portfolio />} />
            <Route path="/simulation" element={<Simulation />} />
            <Route path="/stock/:symbol" element={<StockDetail />} />
            <Route path="/help" element={<Help />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
  );
}
