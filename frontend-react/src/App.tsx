import { BrowserRouter, NavLink, Route, Routes } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import History from "./pages/History";
import QuickFeedback from "./pages/QuickFeedback";
import Troubleshoot from "./pages/Troubleshoot";

function App() {
  return (
    <BrowserRouter>
      <div className="bg-wash" />
      <div className="app-shell">
        <header className="topbar">
          <NavLink to="/" className="brand-block">
            <span className="brand-mark">NSW</span>
            <span>
              <strong className="brand-name">NSW Automation</strong>
              <span className="brand-product">Defect Detective</span>
            </span>
          </NavLink>
          <nav className="nav-links">
            <NavLink to="/" end className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}>
              Home
            </NavLink>
            <NavLink to="/troubleshoot" className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}>
              Troubleshoot
            </NavLink>
            <NavLink to="/history" className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}>
              History
            </NavLink>
          </nav>
        </header>

        <main className="main-content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/troubleshoot" element={<Troubleshoot />} />
            <Route path="/history" element={<History />} />
            <Route path="/quick-feedback" element={<QuickFeedback />} />
          </Routes>
        </main>

        <footer className="app-footer">
          <span>
            Applications aligned with{" "}
            <a href="https://nswautomation.com/NSW/" target="_blank" rel="noreferrer">
              nswautomation.com
            </a>
          </span>
          <span className="muted">Nozzle ID ≥ 5× largest powder particle · AI Horizon 2026</span>
        </footer>
      </div>
    </BrowserRouter>
  );
}

export default App;
