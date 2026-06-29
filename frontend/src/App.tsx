import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import Portfolio from "./pages/Portfolio";
import StockDetail from "./pages/StockDetail";
import Help from "./pages/Help";
import Simulation from "./pages/Simulation";
import Profile from "./pages/Profile";
import './styles/App.css';

export default function App() {
  return (
      <div className="app">
        <header className="navbar">
          <p>BROOKIES</p>
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
            <NavLink to="/profile"><div className="profileIcon"/></NavLink>
          </nav>
        </header>

        <main>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/portfolio" element={<Portfolio />} />
            <Route path="/simulation" element={<Simulation />} />
            <Route path="/stock/:symbol" element={<StockDetail />} />
            <Route path="/help" element={<Help />} />
            <Route path="/profile" element={<Profile />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
  );
}
