import React, { useState } from 'react';
import Layout from '../components/Layout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Switch } from '../components/ui/switch';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import { Search, Sparkles, Loader2, Eye } from 'lucide-react';
import { searchAPI } from '../api';
import { useTaxonomy } from '../contexts/TaxonomyContext';
import { toast } from 'sonner';
import { useNavigate } from 'react-router-dom';
import { getStatusColor, getStatusLabel, getSeniorityLabel } from '../utils/helpers';

const SearchPage = () => {
  const navigate = useNavigate();
  const { getIndustryOptions, getFunctionalAreaOptions, getIndustryName, getFunctionalAreaName } = useTaxonomy();
  const [loading, setLoading] = useState(false);
  const [query, setQuery] = useState('');
  const [filters, setFilters] = useState({});
  const [useSemanticSearch, setUseSemanticSearch] = useState(true);
  const [results, setResults] = useState([]);

  // Obtener opciones de taxonomía desde el contexto
  const industries = getIndustryOptions();
  const functionalAreas = getFunctionalAreaOptions();

  const handleSearch = async () => {
    setLoading(true);
    try {
      const response = await searchAPI.hybrid({
        query: query || undefined,
        use_semantic: useSemanticSearch,
        ...filters
      });
      
      // El backend devuelve { results: [], total, search_metadata }
      const data = response.data;
      const candidates = data.results || data || [];
      const total = data.total ?? candidates.length;
      
      setResults(candidates);
      
      if (total === 0) {
        toast.info('No se encontraron resultados');
      } else {
        toast.success(`${total} candidatos encontrados`);
      }
    } catch (error) {
      console.error('Error searching:', error);
      toast.error('Error en la búsqueda');
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Layout title="Búsqueda Avanzada" subtitle="Encuentra candidatos con búsqueda híbrida e IA">
      <div className="space-y-6">
        {/* Search Input */}
        <Card>
          <CardHeader>
            <CardTitle>Búsqueda Inteligente</CardTitle>
            <CardDescription>
              Usa lenguaje natural para buscar candidatos. Atlas IA encontrará perfiles relevantes incluso si no usan las mismas palabras.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-slate-400" />
              <Input
                placeholder="Ej: Director de operaciones con experiencia en manufactura automotriz"
                data-testid="hybrid-search-input"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
                className="pl-11 text-base h-12"
              />
            </div>

            <div className="flex items-center space-x-2">
              <Switch
                id="semantic-search"
                checked={useSemanticSearch}
                onCheckedChange={setUseSemanticSearch}
              />
              <Label htmlFor="semantic-search" className="flex items-center gap-2 cursor-pointer">
                <Sparkles className="w-4 h-4 text-cyan-500" />
                <span>Búsqueda semántica con IA</span>
                {useSemanticSearch && (
                  <Badge variant="secondary" className="text-xs">Activado</Badge>
                )}
              </Label>
            </div>

            {/* Filters */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 pt-4 border-t">
              <div>
                <Label>Industria</Label>
                <Select value={filters.industry || ''} onValueChange={(value) => setFilters({ ...filters, industry: value || undefined })}>
                  <SelectTrigger>
                    <SelectValue placeholder="Todas" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value=" ">Todas</SelectItem>
                    {industries.map((ind) => (
                      <SelectItem key={ind.value} value={ind.value}>
                        {ind.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div>
                <Label>Área Funcional</Label>
                <Select value={filters.functional_area || ''} onValueChange={(value) => setFilters({ ...filters, functional_area: value || undefined })}>
                  <SelectTrigger>
                    <SelectValue placeholder="Todas" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value=" ">Todas</SelectItem>
                    {functionalAreas.map((area) => (
                      <SelectItem key={area.value} value={area.value}>
                        {area.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div>
                <Label>Seniority</Label>
                <Select value={filters.seniority || ''} onValueChange={(value) => setFilters({ ...filters, seniority: value || undefined })}>
                  <SelectTrigger>
                    <SelectValue placeholder="Todos" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value=" ">Todos</SelectItem>
                    <SelectItem value="senior">Senior</SelectItem>
                    <SelectItem value="manager">Manager</SelectItem>
                    <SelectItem value="director">Director</SelectItem>
                    <SelectItem value="vp">VP</SelectItem>
                    <SelectItem value="c_level">C-Level</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="flex items-end">
                <Button
                  onClick={handleSearch}
                  disabled={loading}
                  className="w-full"
                  data-testid="search-button"
                >
                  {loading ? (
                    <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Buscando...</>
                  ) : (
                    <><Search className="w-4 h-4 mr-2" /> Buscar</>
                  )}
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Results */}
        {results.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Resultados ({results.length})</CardTitle>
              <CardDescription>
                Los resultados están ordenados por relevancia
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {results.map((candidate) => (
                  <div
                    key={candidate.id}
                    className="p-4 border border-slate-200 rounded-sm hover:bg-slate-50 transition-colors"
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-2">
                          <h3 className="font-semibold text-lg text-slate-900">
                            {candidate.full_name}
                          </h3>
                          {candidate.match_score && (
                            <Badge variant="secondary" className="bg-cyan-100 text-cyan-800">
                              Match: {candidate.match_score}%
                            </Badge>
                          )}
                          <Badge className={getStatusColor(candidate.status)}>
                            {getStatusLabel(candidate.status)}
                          </Badge>
                        </div>

                        <p className="text-sm text-slate-600 mb-2">
                          {candidate.current_title && <span className="font-medium">{candidate.current_title}</span>}
                          {candidate.current_company && <span> @ {candidate.current_company}</span>}
                        </p>

                        {candidate.ai_summary && (
                          <p className="text-sm text-slate-700 mb-3 line-clamp-2">
                            {candidate.ai_summary}
                          </p>
                        )}

                        <div className="flex flex-wrap gap-2">
                          {candidate.industry && (
                            <Badge variant="outline">{getIndustryName(candidate.industry)}</Badge>
                          )}
                          {candidate.functional_area && (
                            <Badge variant="outline">{getFunctionalAreaName(candidate.functional_area)}</Badge>
                          )}
                          {candidate.seniority && (
                            <Badge variant="outline">{getSeniorityLabel(candidate.seniority)}</Badge>
                          )}
                        </div>
                      </div>

                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => navigate(`/candidates/${candidate.id}`)}
                      >
                        <Eye className="w-4 h-4 mr-1" />
                        Ver Perfil
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </Layout>
  );
};

export default SearchPage;
