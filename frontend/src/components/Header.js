import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Bell, Search, Menu } from 'lucide-react';
import { Input } from './ui/input';
import { Button } from './ui/button';

const Header = ({ title, subtitle, menuOpen, onMenuToggle }) => {
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      navigate(`/search?q=${encodeURIComponent(searchQuery.trim())}`);
      setSearchQuery(''); // Clear after redirect
    }
  };

  return (
    <div className="bg-white border-b border-slate-200 px-4 sm:px-6 py-4">
      <div className="flex items-center justify-between gap-3">
        <Button data-testid="mobile-menu-toggle" variant="ghost" size="icon" className="shrink-0 lg:hidden" aria-label="Abrir menú de navegación" aria-expanded={menuOpen} aria-controls="workspace-navigation" onClick={onMenuToggle}><Menu className="h-5 w-5" /></Button>
        <div className="min-w-0 flex-1">
          <h1 data-testid="page-heading" className="text-2xl font-bold text-slate-900 break-words">{title}</h1>
          {subtitle && <p data-testid="page-subtitle" className="text-sm text-slate-600 mt-1 break-words">{subtitle}</p>}
        </div>
        
        <div className="flex shrink-0 items-center gap-2 sm:gap-4">
          <form onSubmit={handleSearchSubmit} className="relative hidden md:block">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-slate-400" />
            <Input
              placeholder="Buscar candidatos... (Enter)"
              className="pl-10 w-64"
              data-testid="header-search-input"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </form>
          
          <Button variant="ghost" size="icon" data-testid="notifications-button">
            <Bell className="w-5 h-5 text-slate-600" />
          </Button>
        </div>
      </div>
    </div>
  );
};

export default Header;