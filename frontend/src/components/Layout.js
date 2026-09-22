import React, { useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import Sidebar from './Sidebar';
import Header from './Header';

const Layout = ({ children, title, subtitle }) => {
  const [menuOpen, setMenuOpen] = useState(false);
  const { pathname } = useLocation();
  useEffect(() => { setMenuOpen(false); }, [pathname]);
  useEffect(() => {
    const onEscape = event => { if (event.key === 'Escape') setMenuOpen(false); };
    window.addEventListener('keydown', onEscape);
    return () => window.removeEventListener('keydown', onEscape);
  }, []);
  return (
    <div className="atlas-layout">
      <Sidebar mobileOpen={menuOpen} />
      {menuOpen && <button data-testid="mobile-menu-backdrop" aria-label="Cerrar menú de navegación" onClick={() => setMenuOpen(false)} className="fixed inset-0 z-40 bg-black/30 lg:hidden" />}
      <div className="atlas-main">
        <Header title={title} subtitle={subtitle} menuOpen={menuOpen} onMenuToggle={() => setMenuOpen(open => !open)} />
        <div className="atlas-content">
          {children}
        </div>
      </div>
    </div>
  );
};

export default Layout;