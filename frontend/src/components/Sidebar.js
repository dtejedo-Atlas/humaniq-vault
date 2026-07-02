import React, { useState, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { 
  LayoutDashboard, 
  Users, 
  Upload, 
  Search, 
  Briefcase, 
  Settings, 
  LogOut,
  UserCog,
  ChevronDown,
  ChevronRight,
  Landmark,
  Settings2,
  TrendingUp,
  Megaphone,
  Cpu,
  Scale,
  Truck,
  Send,
  Star,
  ClipboardCheck,
  PlusCircle,
  FolderPlus,
  GitMerge,
  AlertCircle
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { foldersAPI } from '../api';
import axios from 'axios';

const API_BASE = process.env.REACT_APP_BACKEND_URL || '';

// Mapeo de iconos
const ICON_MAP = {
  'landmark': Landmark,
  'settings': Settings2,
  'trending-up': TrendingUp,
  'megaphone': Megaphone,
  'users': Users,
  'cpu': Cpu,
  'scale': Scale,
  'truck': Truck,
  'briefcase': Briefcase,
  'send': Send,
  'star': Star,
  'clipboard-check': ClipboardCheck,
  'plus-circle': PlusCircle,
  'folder': Briefcase
};

// Mapeo de colores
const COLOR_MAP = {
  'emerald': 'text-emerald-400',
  'blue': 'text-blue-400',
  'orange': 'text-orange-400',
  'pink': 'text-pink-400',
  'purple': 'text-purple-400',
  'cyan': 'text-cyan-400',
  'slate': 'text-slate-400',
  'amber': 'text-amber-400',
  'indigo': 'text-indigo-400',
  'green': 'text-green-400',
  'yellow': 'text-yellow-400',
  'teal': 'text-teal-400'
};

const Sidebar = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  
  const [folders, setFolders] = useState({ verticals: [], process: [], custom: [] });
  const [loadingFolders, setLoadingFolders] = useState(true);
  const [verticalsExpanded, setVerticalsExpanded] = useState(true);
  const [processExpanded, setProcessExpanded] = useState(true);
  const [customExpanded, setCustomExpanded] = useState(true);
  const [pendingClassificationsCount, setPendingClassificationsCount] = useState(0);

  // Cargar folders
  useEffect(() => {
    loadFolders();
    loadPendingClassificationsCount();
  }, []);

  const loadFolders = async () => {
    try {
      const response = await foldersAPI.getAll(true);
      setFolders(response.data.by_category || { verticals: [], process: [], custom: [] });
    } catch (error) {
      console.error('Error loading folders:', error);
    } finally {
      setLoadingFolders(false);
    }
  };

  const loadPendingClassificationsCount = async () => {
    try {
      const response = await axios.get(`${API_BASE}/api/atlas/classifications/pending/count`);
      setPendingClassificationsCount(response.data.count || 0);
    } catch (error) {
      // Silently fail - not critical
      console.warn('Error loading pending classifications count:', error?.response?.status || error?.message);
    }
  };

  const mainNavItems = [
    { path: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
    { path: '/candidates', icon: Users, label: 'Candidatos' },
    { path: '/upload', icon: Upload, label: 'Subir CVs' },
    { path: '/search', icon: Search, label: 'Búsqueda' },
    { path: '/review', icon: AlertCircle, label: 'Por Revisar', badge: pendingClassificationsCount },
  ];

  const bottomNavItems = [
    { path: '/jobs', icon: Briefcase, label: 'Vacantes' },
    { path: '/duplicates', icon: GitMerge, label: 'Duplicados', roles: ['super_admin', 'admin', 'recruiter'] },
    { path: '/users', icon: UserCog, label: 'Usuarios', roles: ['super_admin', 'admin'] },
    { path: '/admin', icon: Settings, label: 'Admin', roles: ['super_admin'] }
  ];

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const isActive = (path) => location.pathname === path || location.pathname.startsWith(path + '/');
  const isFolderActive = (folderId) => location.pathname === `/folders/${folderId}`;

  const renderNavItem = (item) => {
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
            flex items-center justify-between px-3 py-2 rounded-sm transition-all text-sm
            ${
              active
                ? 'bg-cyan-500/20 text-cyan-400 font-medium'
                : 'text-slate-400 hover:bg-slate-800 hover:text-white'
            }
          `}
        >
          <div className="flex items-center gap-3">
            <Icon className="w-4 h-4" strokeWidth={1.5} />
            <span>{item.label}</span>
          </div>
          {item.badge > 0 && (
            <Badge className="bg-amber-500 text-white text-xs px-1.5 py-0 min-w-[20px] h-5 flex items-center justify-center">
              {item.badge > 99 ? '99+' : item.badge}
            </Badge>
          )}
        </Link>
      </li>
    );
  };

  const renderFolderItem = (folder) => {
    const IconComponent = ICON_MAP[folder.icon] || Briefcase;
    const colorClass = COLOR_MAP[folder.color] || 'text-slate-400';
    const active = isFolderActive(folder.id);
    
    return (
      <li key={folder.id}>
        <Link
          to={`/folders/${folder.id}`}
          className={`
            flex items-center justify-between px-3 py-1.5 rounded-sm transition-all text-sm
            ${
              active
                ? 'bg-cyan-500/20 text-cyan-400'
                : 'text-slate-400 hover:bg-slate-800 hover:text-white'
            }
          `}
        >
          <div className="flex items-center gap-2 min-w-0">
            <IconComponent className={`w-4 h-4 flex-shrink-0 ${active ? 'text-cyan-400' : colorClass}`} strokeWidth={1.5} />
            <span className="truncate">{folder.name}</span>
          </div>
          {folder.candidate_count > 0 && (
            <span className={`
              text-xs px-1.5 py-0.5 rounded-full flex-shrink-0
              ${active ? 'bg-cyan-500/30 text-cyan-300' : 'bg-slate-700 text-slate-400'}
            `}>
              {folder.candidate_count}
            </span>
          )}
        </Link>
      </li>
    );
  };

  const renderFolderSection = (title, folders, expanded, setExpanded, showAdd = false) => {
    if (folders.length === 0 && !showAdd) return null;
    
    return (
      <div className="mb-2">
        <button
          onClick={() => setExpanded(!expanded)}
          className="w-full flex items-center justify-between px-3 py-1.5 text-xs font-semibold text-slate-500 uppercase tracking-wider hover:text-slate-300"
        >
          <span>{title}</span>
          {expanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
        </button>
        {expanded && (
          <ul className="space-y-0.5 mt-1">
            {folders.map(renderFolderItem)}
            {showAdd && (
              <li>
                <Link
                  to="/folders/new"
                  className="flex items-center gap-2 px-3 py-1.5 text-sm text-slate-500 hover:text-cyan-400 transition-colors"
                >
                  <FolderPlus className="w-4 h-4" />
                  <span>Nuevo Folder</span>
                </Link>
              </li>
            )}
          </ul>
        )}
      </div>
    );
  };

  return (
    <div className="atlas-sidebar flex flex-col h-screen">
      {/* Logo - Fixed */}
      <div className="flex-shrink-0 p-4 border-b border-slate-700">
        <div className="flex items-center gap-3">
          <img 
            src="/humaniq-icon.png" 
            alt="Humaniq Logo" 
            className="w-10 h-10 object-contain"
          />
          <div>
            <h1 className="text-base font-bold text-white">Humaniq</h1>
            <p className="text-xs text-slate-400">Talent Vault</p>
          </div>
        </div>
      </div>

      {/* Navegación Principal - Fixed */}
      <div className="flex-shrink-0 px-3 pt-3">
        <ul className="space-y-0.5">
          {mainNavItems.map(renderNavItem)}
        </ul>
      </div>

      {/* Smart Folders - Scrollable */}
      <div className="flex-1 min-h-0 overflow-y-auto px-3 py-3 border-t border-slate-700/50 mt-3">
        {loadingFolders ? (
          <div className="text-xs text-slate-500 px-3 py-2">Cargando folders...</div>
        ) : (
          <>
            {renderFolderSection('Verticales', folders.verticals, verticalsExpanded, setVerticalsExpanded)}
            {renderFolderSection('Proceso', folders.process, processExpanded, setProcessExpanded)}
            {renderFolderSection('Mis Folders', folders.custom, customExpanded, setCustomExpanded, true)}
          </>
        )}
      </div>

      {/* Navegación Inferior - Fixed */}
      <div className="flex-shrink-0 px-3 py-2 border-t border-slate-700">
        <ul className="space-y-0.5">
          {bottomNavItems.map(renderNavItem)}
        </ul>
      </div>

      {/* Usuario - Fixed */}
      <div className="flex-shrink-0 p-3 border-t border-slate-700">
        <div className="mb-2 px-2">
          <p className="text-xs text-white font-medium truncate">{user?.name}</p>
          <p className="text-xs text-slate-500 truncate">{user?.email}</p>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={handleLogout}
          data-testid="logout-button"
          className="w-full justify-start text-slate-400 hover:text-white hover:bg-slate-800 h-8"
        >
          <LogOut className="w-4 h-4 mr-2" />
          Salir
        </Button>
      </div>
    </div>
  );
};

export default Sidebar;
