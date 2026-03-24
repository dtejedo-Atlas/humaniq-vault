import React, { useEffect, useState } from 'react';
import Layout from '../components/Layout';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Search, Filter, Eye, Mail, Phone, MapPin, Building2, Briefcase } from 'lucide-react';
import { candidatesAPI } from '../api';
import { useTaxonomy } from '../contexts/TaxonomyContext';
import { toast } from 'sonner';
import { useNavigate } from 'react-router-dom';
import { getStatusColor, getStatusLabel, getSeniorityLabel, formatDate } from '../utils/helpers';

const CandidatesPage = () => {
  const navigate = useNavigate();
  const { getIndustryOptions, getFunctionalAreaOptions, getIndustryName, getFunctionalAreaName } = useTaxonomy();
  const [candidates, setCandidates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [filters, setFilters] = useState({
    status: '',
    industry: '',
    functional_area: '',
    seniority: ''
  });

  // Obtener opciones de taxonomía desde el contexto
  const industries = getIndustryOptions();
  const functionalAreas = getFunctionalAreaOptions();

  useEffect(() => {
    fetchCandidates();
  }, []);

  useEffect(() => {
    const delayDebounce = setTimeout(() => {
      fetchCandidates();
    }, 500);

    return () => clearTimeout(delayDebounce);
  }, [search, filters]);

  const fetchCandidates = async () => {
    setLoading(true);
    try {
      const params = { search, ...filters };
      // Remove empty filters
      Object.keys(params).forEach(key => !params[key] && delete params[key]);
      
      const response = await candidatesAPI.getAll(params);
      setCandidates(response.data);
    } catch (error) {
      console.error('Error fetching candidates:', error);
      toast.error('Error cargando candidatos');
    } finally {
      setLoading(false);
    }
  };

  const handleViewCandidate = (candidateId) => {
    navigate(`/candidates/${candidateId}`);
  };

  return (
    <Layout title="Base de Candidatos" subtitle="Explora y gestiona tu base de talento">
      <div className="space-y-6">
        {/* Search and Filters */}
        <Card>
          <CardContent className="p-6">
            <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
              <div className="md:col-span-2 relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-slate-400" />
                <Input
                  placeholder="Buscar por nombre, email, empresa..."
                  data-testid="candidates-search-input"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="pl-10"
                />
              </div>

              <Select value={filters.status} onValueChange={(value) => setFilters({ ...filters, status: value })}>
                <SelectTrigger data-testid="filter-status">
                  <SelectValue placeholder="Estado" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value=" ">Todos los estados</SelectItem>
                  <SelectItem value="new">Nuevo</SelectItem>
                  <SelectItem value="reviewed">Revisado</SelectItem>
                  <SelectItem value="contacted">Contactado</SelectItem>
                  <SelectItem value="in_process">En Proceso</SelectItem>
                  <SelectItem value="placed">Colocado</SelectItem>
                  <SelectItem value="archived">Archivado</SelectItem>
                </SelectContent>
              </Select>

              <Select value={filters.industry} onValueChange={(value) => setFilters({ ...filters, industry: value })}>
                <SelectTrigger data-testid="filter-industry">
                  <SelectValue placeholder="Industria" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value=" ">Todas las industrias</SelectItem>
                  {industries.map((ind) => (
                    <SelectItem key={ind.value} value={ind.value}>
                      {ind.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              <Select value={filters.seniority} onValueChange={(value) => setFilters({ ...filters, seniority: value })}>
                <SelectTrigger data-testid="filter-seniority">
                  <SelectValue placeholder="Seniority" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value=" ">Todos los niveles</SelectItem>
                  <SelectItem value="entry">Inicial</SelectItem>
                  <SelectItem value="junior">Junior</SelectItem>
                  <SelectItem value="mid">Mid</SelectItem>
                  <SelectItem value="senior">Senior</SelectItem>
                  <SelectItem value="lead">Lead</SelectItem>
                  <SelectItem value="manager">Manager</SelectItem>
                  <SelectItem value="director">Director</SelectItem>
                  <SelectItem value="vp">VP</SelectItem>
                  <SelectItem value="c_level">C-Level</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {(search || filters.status || filters.industry || filters.seniority) && (
              <div className="mt-4 flex items-center gap-2">
                <span className="text-sm text-slate-600">Filtros activos:</span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setSearch('');
                    setFilters({ status: '', industry: '', functional_area: '', seniority: '' });
                  }}
                >
                  Limpiar Filtros
                </Button>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Candidates Table */}
        <Card>
          <CardContent className="p-0">
            {loading ? (
              <div className="flex items-center justify-center h-64">
                <div className="spinner w-8 h-8 border-4 border-slate-300 border-t-cyan-500 rounded-full"></div>
              </div>
            ) : candidates.length === 0 ? (
              <div className="text-center py-12">
                <p className="text-slate-600">No se encontraron candidatos</p>
                <Button
                  variant="outline"
                  className="mt-4"
                  onClick={() => navigate('/upload')}
                >
                  Subir Candidatos
                </Button>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <Table className="table-atlas">
                  <TableHeader>
                    <TableRow>
                      <TableHead>Nombre</TableHead>
                      <TableHead>Contacto</TableHead>
                      <TableHead>Puesto Actual</TableHead>
                      <TableHead>Industria / Área</TableHead>
                      <TableHead>Seniority</TableHead>
                      <TableHead>Estado</TableHead>
                      <TableHead>Fecha</TableHead>
                      <TableHead className="text-right">Acciones</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {candidates.map((candidate) => (
                      <TableRow key={candidate.id} data-testid={`candidate-row-${candidate.id}`}>
                        <TableCell>
                          <div>
                            <p className="font-medium text-slate-900">{candidate.full_name}</p>
                            {candidate.city && (
                              <p className="text-xs text-slate-500 flex items-center gap-1 mt-1">
                                <MapPin className="w-3 h-3" />
                                {candidate.city}{candidate.state ? `, ${candidate.state}` : ''}
                              </p>
                            )}
                          </div>
                        </TableCell>
                        <TableCell>
                          <div className="space-y-1">
                            {candidate.email && (
                              <p className="text-xs text-slate-600 flex items-center gap-1">
                                <Mail className="w-3 h-3" />
                                {candidate.email}
                              </p>
                            )}
                            {candidate.phone && (
                              <p className="text-xs text-slate-600 flex items-center gap-1">
                                <Phone className="w-3 h-3" />
                                {candidate.phone}
                              </p>
                            )}
                          </div>
                        </TableCell>
                        <TableCell>
                          <div>
                            {candidate.current_title && (
                              <p className="text-sm font-medium text-slate-900">{candidate.current_title}</p>
                            )}
                            {candidate.current_company && (
                              <p className="text-xs text-slate-600 flex items-center gap-1 mt-1">
                                <Building2 className="w-3 h-3" />
                                {candidate.current_company}
                              </p>
                            )}
                          </div>
                        </TableCell>
                        <TableCell>
                          <div className="space-y-1">
                            {candidate.industry && (
                              <Badge variant="outline" className="text-xs">
                                {getIndustryName(candidate.industry)}
                              </Badge>
                            )}
                            {candidate.functional_area && (
                              <p className="text-xs text-slate-600 flex items-center gap-1">
                                <Briefcase className="w-3 h-3" />
                                {getFunctionalAreaName(candidate.functional_area)}
                              </p>
                            )}
                          </div>
                        </TableCell>
                        <TableCell>
                          {candidate.seniority && (
                            <Badge variant="secondary" className="text-xs">
                              {getSeniorityLabel(candidate.seniority)}
                            </Badge>
                          )}
                        </TableCell>
                        <TableCell>
                          <Badge className={`${getStatusColor(candidate.status)} text-xs`}>
                            {getStatusLabel(candidate.status)}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <p className="text-xs text-slate-600">{formatDate(candidate.created_at)}</p>
                        </TableCell>
                        <TableCell className="text-right">
                          <Button
                            variant="ghost"
                            size="sm"
                            data-testid={`view-candidate-${candidate.id}`}
                            onClick={() => handleViewCandidate(candidate.id)}
                          >
                            <Eye className="w-4 h-4 mr-1" />
                            Ver
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Summary */}
        {!loading && candidates.length > 0 && (
          <div className="text-sm text-slate-600 text-center">
            Mostrando {candidates.length} candidatos
          </div>
        )}
      </div>
    </Layout>
  );
};

export default CandidatesPage;
