import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Layout from '../components/Layout';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Checkbox } from '../components/ui/checkbox';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../components/ui/table';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue 
} from '../components/ui/select';
import { 
  ArrowLeft, 
  Loader2, 
  Download, 
  RefreshCw,
  Users,
  Filter,
  Eye,
  BarChart3,
  Landmark,
  Settings2,
  TrendingUp,
  Megaphone,
  Cpu,
  Scale,
  Truck,
  Briefcase,
  Send,
  Star,
  ClipboardCheck,
  PlusCircle
} from 'lucide-react';
import { foldersAPI, exportsAPI } from '../api';
import { useTaxonomy } from '../contexts/TaxonomyContext';
import { useAuth } from '../contexts/AuthContext';
import { toast } from 'sonner';

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

// Mapeo de colores para badges
const COLOR_MAP = {
  'emerald': 'bg-emerald-100 text-emerald-800 border-emerald-200',
  'blue': 'bg-blue-100 text-blue-800 border-blue-200',
  'orange': 'bg-orange-100 text-orange-800 border-orange-200',
  'pink': 'bg-pink-100 text-pink-800 border-pink-200',
  'purple': 'bg-purple-100 text-purple-800 border-purple-200',
  'cyan': 'bg-cyan-100 text-cyan-800 border-cyan-200',
  'slate': 'bg-slate-100 text-slate-800 border-slate-200',
  'amber': 'bg-amber-100 text-amber-800 border-amber-200',
  'indigo': 'bg-indigo-100 text-indigo-800 border-indigo-200',
  'green': 'bg-green-100 text-green-800 border-green-200',
  'yellow': 'bg-yellow-100 text-yellow-800 border-yellow-200',
  'teal': 'bg-teal-100 text-teal-800 border-teal-200'
};

const SENIORITY_LABELS = {
  'intern': 'Pasante',
  'junior': 'Junior',
  'mid': 'Mid-Level',
  'senior': 'Senior',
  'manager': 'Manager',
  'senior_manager': 'Sr. Manager',
  'director': 'Director',
  'vp': 'VP',
  'c_level': 'C-Level',
  'ceo': 'CEO'
};

export default function FolderViewPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { getIndustryName, getFunctionalAreaName } = useTaxonomy();
  const { user } = useAuth();
  
  const [folder, setFolder] = useState(null);
  const [candidates, setCandidates] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [sortBy, setSortBy] = useState('match_score');
  const [selectedCandidates, setSelectedCandidates] = useState([]);
  const [exporting, setExporting] = useState(false);
  const [analytics, setAnalytics] = useState(null);
  
  const ITEMS_PER_PAGE = 50;

  useEffect(() => {
    loadFolderData();
    loadAnalytics();
  }, [id, sortBy]);

  const loadFolderData = async () => {
    try {
      setLoading(true);
      const response = await foldersAPI.getCandidates(id, 0, ITEMS_PER_PAGE, sortBy);
      setFolder(response.data.folder);
      setCandidates(response.data.candidates);
      setTotal(response.data.total);
    } catch (error) {
      console.error('Error loading folder:', error);
      toast.error('Error cargando folder');
      if (error.response?.status === 404) {
        navigate('/dashboard');
      }
    } finally {
      setLoading(false);
    }
  };

  const loadAnalytics = async () => {
    try {
      const response = await foldersAPI.getAnalytics(id);
      setAnalytics(response.data);
    } catch (error) {
      console.error('Error loading analytics:', error);
    }
  };

  const loadMore = async () => {
    if (loadingMore || candidates.length >= total) return;
    
    setLoadingMore(true);
    try {
      const response = await foldersAPI.getCandidates(id, candidates.length, ITEMS_PER_PAGE, sortBy);
      setCandidates([...candidates, ...response.data.candidates]);
    } catch (error) {
      console.error('Error loading more:', error);
    } finally {
      setLoadingMore(false);
    }
  };

  const handleSelectAll = () => {
    if (selectedCandidates.length === candidates.length) {
      setSelectedCandidates([]);
    } else {
      setSelectedCandidates(candidates.map(c => c.id));
    }
  };

  const handleSelectCandidate = (candidateId) => {
    setSelectedCandidates(prev => 
      prev.includes(candidateId)
        ? prev.filter(id => id !== candidateId)
        : [...prev, candidateId]
    );
  };

  const handleExport = async () => {
    if (selectedCandidates.length === 0) {
      toast.error('Selecciona al menos un candidato');
      return;
    }
    
    setExporting(true);
    try {
      const response = await exportsAPI.exportCandidates(selectedCandidates, {
        format: 'pdf',
        includeRisks: true,
        clientName: folder?.name
      });
      
      // Descargar archivo
      const downloadUrl = `${process.env.REACT_APP_BACKEND_URL}${response.data.download_url}`;
      const token = localStorage.getItem('token');
      
      const fileResponse = await fetch(downloadUrl, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      if (fileResponse.ok) {
        const blob = await fileResponse.blob();
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = response.data.filename;
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.URL.revokeObjectURL(url);
        
        toast.success(`Exportados ${response.data.candidate_count} candidatos`);
      }
    } catch (error) {
      console.error('Export error:', error);
      toast.error('Error exportando candidatos');
    } finally {
      setExporting(false);
    }
  };

  const FolderIcon = folder ? (ICON_MAP[folder.icon] || Briefcase) : Briefcase;
  const folderColorClass = folder ? (COLOR_MAP[folder.color] || COLOR_MAP.slate) : '';

  if (loading) {
    return (
      <Layout>
        <div className="flex items-center justify-center h-64">
          <Loader2 className="w-8 h-8 animate-spin text-cyan-600" />
        </div>
      </Layout>
    );
  }

  if (!folder) {
    return (
      <Layout>
        <div className="text-center py-12">
          <p className="text-slate-500">Folder no encontrado</p>
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <Button variant="ghost" size="sm" onClick={() => navigate(-1)}>
                <ArrowLeft className="w-4 h-4" />
              </Button>
              <div className={`p-2 rounded-lg ${folderColorClass.replace('text-', 'bg-').replace('800', '100')}`}>
                <FolderIcon className={`w-6 h-6 ${folderColorClass.split(' ')[1]}`} />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-slate-900">{folder.name}</h1>
                {folder.description && (
                  <p className="text-slate-500 text-sm">{folder.description}</p>
                )}
              </div>
            </div>
            <div className="flex items-center gap-3 ml-12">
              <Badge variant="outline" className={folderColorClass}>
                {total} candidatos
              </Badge>
              {folder.folder_type === 'system' && (
                <Badge variant="outline" className="bg-slate-50 text-slate-600">
                  Folder del Sistema
                </Badge>
              )}
              {analytics && analytics.total_views > 0 && (
                <span className="text-xs text-slate-400 flex items-center gap-1">
                  <Eye className="w-3 h-3" />
                  {analytics.total_views} vistas
                </span>
              )}
            </div>
          </div>
          
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={loadFolderData}>
              <RefreshCw className="w-4 h-4 mr-2" />
              Actualizar
            </Button>
            {selectedCandidates.length > 0 && (
              <Button 
                onClick={handleExport} 
                disabled={exporting}
                className="bg-indigo-600 hover:bg-indigo-700"
              >
                {exporting ? (
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                ) : (
                  <Download className="w-4 h-4 mr-2" />
                )}
                Exportar ({selectedCandidates.length})
              </Button>
            )}
          </div>
        </div>

        {/* Criterios activos */}
        {folder.criteria && Object.keys(folder.criteria).length > 0 && (
          <Card className="bg-slate-50 border-slate-200">
            <CardContent className="py-3">
              <div className="flex items-center gap-2 flex-wrap">
                <Filter className="w-4 h-4 text-slate-400" />
                <span className="text-sm text-slate-500">Filtros activos:</span>
                {folder.criteria.functional_area?.length > 0 && (
                  <Badge variant="outline" className="bg-white">
                    Área: {folder.criteria.functional_area.map(f => getFunctionalAreaName(f)).join(', ')}
                  </Badge>
                )}
                {folder.criteria.seniority && (
                  <Badge variant="outline" className="bg-white">
                    Seniority: {folder.criteria.seniority.min_level || 'Todos'} - {folder.criteria.seniority.max_level || 'Todos'}
                  </Badge>
                )}
                {folder.criteria.last_activity_days && (
                  <Badge variant="outline" className="bg-white">
                    Últimos {folder.criteria.last_activity_days} días
                  </Badge>
                )}
                {folder.criteria.min_match_score && (
                  <Badge variant="outline" className="bg-white">
                    Score mín: {folder.criteria.min_match_score}%
                  </Badge>
                )}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Controles */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Checkbox 
              checked={selectedCandidates.length === candidates.length && candidates.length > 0}
              onCheckedChange={handleSelectAll}
            />
            <span className="text-sm text-slate-500">
              {selectedCandidates.length > 0 
                ? `${selectedCandidates.length} seleccionados`
                : 'Seleccionar todos'}
            </span>
          </div>
          <Select value={sortBy} onValueChange={setSortBy}>
            <SelectTrigger className="w-48">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="match_score">Ordenar por Match</SelectItem>
              <SelectItem value="name">Ordenar por Nombre</SelectItem>
              <SelectItem value="updated">Más Recientes</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Tabla de candidatos */}
        <Card>
          <Table>
            <TableHeader>
              <TableRow className="bg-slate-50">
                <TableHead className="w-12"></TableHead>
                <TableHead>Candidato</TableHead>
                <TableHead>Puesto Actual</TableHead>
                <TableHead>Área</TableHead>
                <TableHead>Seniority</TableHead>
                <TableHead className="text-right">Acciones</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {candidates.map((candidate) => (
                <TableRow 
                  key={candidate.id}
                  className={selectedCandidates.includes(candidate.id) ? 'bg-cyan-50' : ''}
                >
                  <TableCell>
                    <Checkbox
                      checked={selectedCandidates.includes(candidate.id)}
                      onCheckedChange={() => handleSelectCandidate(candidate.id)}
                    />
                  </TableCell>
                  <TableCell>
                    <div>
                      <p className="font-medium text-slate-900">{candidate.full_name}</p>
                      <p className="text-sm text-slate-500">{candidate.current_company || '-'}</p>
                    </div>
                  </TableCell>
                  <TableCell>
                    <span className="text-sm">{candidate.current_title || '-'}</span>
                  </TableCell>
                  <TableCell>
                    <span className="text-sm text-slate-600">
                      {getFunctionalAreaName(candidate.functional_area) || '-'}
                    </span>
                  </TableCell>
                  <TableCell>
                    {candidate.seniority && (
                      <Badge variant="outline" className="bg-slate-50">
                        {SENIORITY_LABELS[candidate.seniority] || candidate.seniority}
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => navigate(`/candidates/${candidate.id}`)}
                    >
                      <Eye className="w-4 h-4 mr-1" />
                      Ver
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
              {candidates.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-12 text-slate-500">
                    <Users className="w-12 h-12 mx-auto mb-3 text-slate-300" />
                    No hay candidatos que coincidan con estos criterios
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </Card>

        {/* Load More */}
        {candidates.length < total && (
          <div className="text-center">
            <Button 
              variant="outline" 
              onClick={loadMore}
              disabled={loadingMore}
            >
              {loadingMore && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              Cargar más ({candidates.length} de {total})
            </Button>
          </div>
        )}
      </div>
    </Layout>
  );
}
