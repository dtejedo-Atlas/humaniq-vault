import React from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { 
  LayoutDashboard, 
  Users, 
  Upload, 
  Search, 
  Briefcase, 
  FolderOpen, 
  Settings, 
  LogOut,
  Sparkles
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { Button } from './ui/button';

const Sidebar = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuth();

  const navItems = [
    { path: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
    { path: '/candidates', icon: Users, label: 'Candidatos' },
    { path: '/upload', icon: Upload, label: 'Subir CVs' },
    { path: '/search', icon: Search, label: 'Búsqueda' },
    { path: '/jobs', icon: Briefcase, label: 'Vacantes' },
    { path: '/folders', icon: FolderOpen, label: 'Carpetas' },
    { path: '/validation', icon: Sparkles, label: 'Validación', roles: ['super_admin', 'recruiter'] },
    { path: '/admin', icon: Settings, label: 'Admin', roles: ['super_admin'] }
  ];

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const isActive = (path) => location.pathname === path || location.pathname.startsWith(path + '/');

  return (
    <div className="atlas-sidebar">
      <div className="p-6 border-b border-slate-700">
        <div className="flex items-center gap-2">
          <div className="w-10 h-10 bg-cyan-500 rounded-sm flex items-center justify-center">
            <Sparkles className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-white">Atlas</h1>
            <p className="text-xs text-slate-400">Talent Vault</p>
          </div>
        </div>
      </div>

      <nav className="flex-1 p-4">
        <ul className="space-y-1">
          {navItems.map((item) => {
            // Check role permissions
            if (item.roles && !item.roles.includes(user?.role)) {
              return null;
            }

            const Icon = item.icon;
            const active = isActive(item.path);

            return (
              <li key={item.path}>
                <Link
                  to={item.path}
                  data-testid={`nav-${item.label.toLowerCase().replace(' ', '-')}`}
                  className={`
                    flex items-center gap-3 px-4 py-2.5 rounded-sm transition-all
                    ${
                      active
                        ? 'bg-cyan-500 text-white font-medium'
                        : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                    }
                  `}
                >
                  <Icon className="w-5 h-5" strokeWidth={1.5} />
                  <span className="text-sm">{item.label}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      <div className="p-4 border-t border-slate-700">
        <div className="mb-3 px-2">
          <p className="text-xs text-slate-400 mb-1">Usuario</p>
          <p className="text-sm text-white font-medium">{user?.name}</p>
          <p className="text-xs text-slate-400">{user?.email}</p>
        </div>
        <Button
          variant="ghost"
          onClick={handleLogout}
          data-testid="logout-button"
          className="w-full justify-start text-slate-300 hover:text-white hover:bg-slate-800"
        >
          <LogOut className="w-4 h-4 mr-2" />
          Cerrar Sesión
        </Button>
      </div>
    </div>
  );
};

export default Sidebar;