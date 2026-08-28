import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import Troubleshoot from './pages/Troubleshoot';
import History from './pages/History';

function App() {
  return (
    <BrowserRouter>
      <div className="bg-mesh"></div>
      <div className="app-container">
        
        {/* Header Navbar */}
        <header className="app-header">
          <div className="brand-section">
            <h1 className="brand">Defect Detective</h1>
            <span className="brand-sub">NSW Automation</span>
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
        </header>

        {/* Main Content Area */}
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/troubleshoot" element={<Troubleshoot />} />
            <Route path="/history" element={<History />} />
          </Routes>
        </main>

        {/* Footer */}
        <footer className="app-footer">
          <p>
            <strong>NSW 5× rule:</strong> Nozzle ID ≥ 5× largest powder particle.
          </p>
          <p className="muted">
            Ranking is rule-based, not a generic chatbot. AI Horizon 2026.
          </p>
        </footer>

      </div>
    </BrowserRouter>
  );
}

export default App;
