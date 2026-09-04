import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import Troubleshoot from './pages/Troubleshoot';
import History from './pages/History';
import QuickFeedback from './pages/QuickFeedback';

function App() {
  return (
    <BrowserRouter>
      <div className="bg-mesh"></div>
      <div className="app-container">
        
        {/* Header Navbar */}
        <header className="app-header">
          <div className="brand-section">
            <div className="brand-logo-badge">⚡</div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                <h1 className="brand">Defect Detective</h1>
                <span className="brand-sub">NSW Automation</span>
              </div>
            </div>
          </div>
          
          <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem' }}>
            <div className="system-status-indicator">
              <span className="status-dot"></span>
              <span>SYSTEM ONLINE</span>
            </div>

            <nav className="nav-links">
              <NavLink to="/" end className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                Dashboard
              </NavLink>
              <NavLink to="/troubleshoot" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                Troubleshoot
              </NavLink>
              <NavLink to="/history" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                Case History
              </NavLink>
            </nav>
          </div>
        </header>

        {/* Main Content Area */}
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/troubleshoot" element={<Troubleshoot />} />
            <Route path="/history" element={<History />} />
            <Route path="/quick-feedback" element={<QuickFeedback />} />
          </Routes>
        </main>

        {/* Footer */}
        <footer className="app-footer">
          <div>
            <strong>NSW 5× Rule Engine:</strong> Nozzle ID ≥ 5× largest powder particle size.
          </div>
          <div className="muted mono" style={{ fontSize: '0.78rem' }}>
            Deterministic Physics & Bayesian Inference Engine · AI Horizon Solution Challenge 2026
          </div>
        </footer>

      </div>
    </BrowserRouter>
  );
}

export default App;
