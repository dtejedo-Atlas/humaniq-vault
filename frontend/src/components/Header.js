import React from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Bell, Search } from 'lucide-react';
import { Input } from './ui/input';
import { Button } from './ui/button';

const Header = ({ title, subtitle }) => {
  const { user } = useAuth();

  return (
    <div className="bg-white border-b border-slate-200 px-6 py-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">{title}</h1>
          {subtitle && <p className="text-sm text-slate-600 mt-1">{subtitle}</p>}
        </div>
        
        <div className="flex items-center gap-4">
          <div className="relative hidden md:block">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-slate-400" />
            <Input
              placeholder="Buscar candidatos..."
              className="pl-10 w-64"
              data-testid="header-search-input"
            />
          </div>
          
          <Button variant="ghost" size="icon" data-testid="notifications-button">
            <Bell className="w-5 h-5 text-slate-600" />
          </Button>
        </div>
      </div>
    </div>
  );
};

export default Header;