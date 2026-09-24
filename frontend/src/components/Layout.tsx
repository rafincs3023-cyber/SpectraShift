import { NavLink, Outlet } from "react-router-dom";

const NAV_LINKS = [
  { to: "/", label: "Home", end: true },
  { to: "/explore", label: "Explore" },
  { to: "/compare", label: "Compare" },
  { to: "/spectral", label: "Spectral View" },
  { to: "/candidates", label: "Candidates" },
  { to: "/about", label: "About" },
  { to: "/help", label: "Help" },
];

export function Layout() {
  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-header-inner">
          <NavLink to="/" className="brand" end>
            <span className="brand-mark" aria-hidden="true" />
            <span className="brand-text">
              Spectra<span className="brand-accent">Shift</span>
            </span>
          </NavLink>

          <nav className="main-nav" aria-label="Main navigation">
            {NAV_LINKS.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                end={link.end}
                className={({ isActive }) =>
                  isActive ? "nav-link nav-link-active" : "nav-link"
                }
              >
                {link.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>

      <main className="app-main">
        <Outlet />
      </main>

      <footer className="app-footer">
        <p>
          Preliminary, unconfirmed three-epoch motion candidates from SPHEREx
          data. Nothing shown here is a confirmed discovery.
        </p>
      </footer>
    </div>
  );
}
