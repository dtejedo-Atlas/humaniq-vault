import React, { useState, useEffect } from 'react';
import Layout from '../components/Layout';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '../components/ui/dialog';
import { Checkbox } from '../components/ui/checkbox';
import { Label } from '../components/ui/label';
import { Alert, AlertDescription } from '../components/ui/alert';
import { 
  Users, 
  AlertTriangle, 
  Merge, 
  Eye, 
  Loader2,
  CheckCircle2,
  Calendar,
  Briefcase,
  Mail,
  ArrowRight,
  RefreshCw
} from 'lucide-react';
import { toast } from 'sonner';
import axios from 'axios';

const API_BASE = process.env.REACT_APP_BACKEND_URL || '';

const DuplicatesPage = () => {
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState(null);
  const [duplicateGroups, setDuplicateGroups] = useState([]);
  const [selectedGroup, setSelectedGroup] = useState(null);
  const [mergePreview, setMergePreview] = useState(null);
  const [merging, setMerging] = useState(false);
  const [mergeDialogOpen, setMergeDialogOpen] = useState(false);
  const [mergeOptions, setMergeOptions] = useState({
    merge_experience: true,
    merge_education: true,
    merge_skills: true,
    merge_notes: true,
    keep_all_cvs: true,
    use_secondary_contact: false
  });
  const [primaryCandidate, setPrimaryCandidate] = useState(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [statsRes, groupsRes] = await Promise.all([
        axios.get(`${API_BASE}/api/duplicates/stats`),
        axios.get(`${API_BASE}/api/duplicates/review`)
      ]);
      setStats(statsRes.data);
      setDuplicateGroups(groupsRes.data.duplicate_groups || []);
    } catch (error) {
      console.error('Error loading duplicates:', error);
      toast.error('Error cargando datos de duplicados');
    } finally {
      setLoading(false);
    }
  };

  const handleSelectGroup = async (group) => {
    setSelectedGroup(group);
    if (group.candidates.length === 2) {
      try {
        const res = await axios.get(
          `${API_BASE}/api/candidates/${group.candidates[0].id}/merge-preview/${group.candidates[1].id}`
        );
        setMergePreview(res.data);
        setPrimaryCandidate(res.data.recommendation);
      } catch (error) {
        console.error('Error loading merge preview:', error);
      }
    }
  };

  const handleMerge = async () => {
    if (!selectedGroup || !primaryCandidate) return;
    
    const candidates = selectedGroup.candidates;
    const primary = candidates.find(c => 
      (primaryCandidate === 'candidate_1' && c.id === mergePreview?.candidate_1?.id) ||
      (primaryCandidate === 'candidate_2' && c.id === mergePreview?.candidate_2?.id)
    );
    const secondary = candidates.find(c => c.id !== primary.id);

    if (!primary || !secondary) {
      toast.error('Error identificando candidatos para merge');
      return;
    }

    setMerging(true);
    try {
      await axios.post(`${API_BASE}/api/candidates/merge`, {
        primary_candidate_id: primary.id,
        secondary_candidate_id: secondary.id,
        ...mergeOptions
      });
      
      toast.success('Candidatos fusionados exitosamente');
      setMergeDialogOpen(false);
      setSelectedGroup(null);
      setMergePreview(null);
      loadData();
    } catch (error) {
      console.error('Error merging:', error);
      toast.error(error.response?.data?.detail || 'Error al fusionar candidatos');
    } finally {
      setMerging(false);
    }
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return 'N/A';
    return new Date(dateStr).toLocaleDateString('es-MX', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  };

  if (loading) {
    return (
      <Layout>
        <div className="flex items-center justify-center h-64">
          <Loader2 className="w-8 h-8 animate-spin text-cyan-600" />
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold text-slate-900">Gestión de Duplicados</h1>
            <p className="text-slate-600 mt-1">Revisa y fusiona candidatos duplicados</p>
          </div>
          <Button variant="outline" onClick={loadData}>
            <RefreshCw className="w-4 h-4 mr-2" />
            Actualizar
          </Button>
        </div>

        {/* Stats */}
        {stats && (
          <div className="grid grid-cols-4 gap-4">
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-amber-100 rounded-lg">
                    <AlertTriangle className="w-5 h-5 text-amber-600" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold text-slate-900">{stats.total_duplicate_groups}</p>
                    <p className="text-sm text-slate-500">Grupos duplicados</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-red-100 rounded-lg">
                    <Users className="w-5 h-5 text-red-600" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold text-slate-900">{stats.total_duplicate_records}</p>
                    <p className="text-sm text-slate-500">Registros afectados</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-blue-100 rounded-lg">
                    <Mail className="w-5 h-5 text-blue-600" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold text-slate-900">{stats.by_match_type?.email || 0}</p>
                    <p className="text-sm text-slate-500">Por email</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-green-100 rounded-lg">
                    <CheckCircle2 className="w-5 h-5 text-green-600" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold text-slate-900">{stats.total_merges_performed}</p>
                    <p className="text-sm text-slate-500">Merges realizados</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Duplicate Groups */}
        <div className="grid grid-cols-2 gap-6">
          {/* List */}
          <Card>
            <CardHeader>
              <CardTitle>Grupos de Duplicados</CardTitle>
              <CardDescription>
                Selecciona un grupo para ver el detalle y fusionar
              </CardDescription>
            </CardHeader>
            <CardContent>
              {duplicateGroups.length === 0 ? (
                <div className="text-center py-8 text-slate-500">
                  <CheckCircle2 className="w-12 h-12 mx-auto mb-3 text-green-500" />
                  <p>No hay duplicados detectados</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {duplicateGroups.map((group) => (
                    <div
                      key={group.group_id}
                      className={`p-4 border rounded-lg cursor-pointer transition-colors ${
                        selectedGroup?.group_id === group.group_id
                          ? 'border-cyan-500 bg-cyan-50'
                          : 'border-slate-200 hover:border-slate-300'
                      }`}
                      onClick={() => handleSelectGroup(group)}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <Badge variant="outline" className="text-amber-700 border-amber-300 bg-amber-50">
                          {group.match_type === 'email' ? 'Email' : group.match_type}
                        </Badge>
                        <span className="text-sm text-slate-500">
                          {group.count} registros
                        </span>
                      </div>
                      <p className="text-sm font-medium text-slate-900 truncate">
                        {group.match_value}
                      </p>
                      <p className="text-xs text-slate-500 mt-1">
                        {group.candidates[0]?.full_name}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Detail / Preview */}
          <Card>
            <CardHeader>
              <CardTitle>Detalle del Grupo</CardTitle>
              <CardDescription>
                Compara y decide cómo fusionar
              </CardDescription>
            </CardHeader>
            <CardContent>
              {!selectedGroup ? (
                <div className="text-center py-8 text-slate-500">
                  <Eye className="w-12 h-12 mx-auto mb-3 text-slate-300" />
                  <p>Selecciona un grupo para ver el detalle</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {/* Candidates comparison */}
                  {selectedGroup.candidates.map((candidate, idx) => (
                    <div
                      key={candidate.id}
                      className={`p-4 border rounded-lg ${
                        mergePreview?.recommendation === `candidate_${idx + 1}`
                          ? 'border-green-500 bg-green-50'
                          : 'border-slate-200'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-medium text-slate-900">
                          {candidate.full_name}
                        </span>
                        {mergePreview?.recommendation === `candidate_${idx + 1}` && (
                          <Badge className="bg-green-600">Recomendado</Badge>
                        )}
                      </div>
                      <div className="grid grid-cols-2 gap-2 text-sm text-slate-600">
                        <div className="flex items-center gap-1">
                          <Briefcase className="w-3 h-3" />
                          {candidate.current_title || 'Sin título'}
                        </div>
                        <div className="flex items-center gap-1">
                          <Calendar className="w-3 h-3" />
                          {formatDate(candidate.created_at)}
                        </div>
                      </div>
                      {mergePreview && (
                        <div className="mt-2 text-xs text-slate-500">
                          Score: {mergePreview[`candidate_${idx + 1}`]?.completeness_score} |
                          Exp: {mergePreview[`candidate_${idx + 1}`]?.experience_count} |
                          Skills: {mergePreview[`candidate_${idx + 1}`]?.skills_count}
                        </div>
                      )}
                    </div>
                  ))}

                  {/* Differences */}
                  {mergePreview?.differences?.length > 0 && (
                    <Alert>
                      <AlertTriangle className="w-4 h-4" />
                      <AlertDescription>
                        <strong>Diferencias detectadas:</strong>
                        <ul className="mt-1 list-disc list-inside">
                          {mergePreview.differences.map((diff, i) => (
                            <li key={i}>{diff}</li>
                          ))}
                        </ul>
                      </AlertDescription>
                    </Alert>
                  )}

                  {/* Merge Button */}
                  <Button 
                    className="w-full" 
                    onClick={() => setMergeDialogOpen(true)}
                  >
                    <Merge className="w-4 h-4 mr-2" />
                    Fusionar Candidatos
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Merge Dialog */}
        <Dialog open={mergeDialogOpen} onOpenChange={setMergeDialogOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Confirmar Fusión de Candidatos</DialogTitle>
              <DialogDescription>
                Selecciona el registro principal y las opciones de fusión
              </DialogDescription>
            </DialogHeader>

            {selectedGroup && mergePreview && (
              <div className="space-y-4">
                {/* Primary selection */}
                <div className="space-y-2">
                  <Label>Registro Principal (se conservará)</Label>
                  <div className="grid grid-cols-2 gap-2">
                    {['candidate_1', 'candidate_2'].map((opt) => (
                      <div
                        key={opt}
                        className={`p-3 border rounded-lg cursor-pointer ${
                          primaryCandidate === opt
                            ? 'border-cyan-500 bg-cyan-50'
                            : 'border-slate-200'
                        }`}
                        onClick={() => setPrimaryCandidate(opt)}
                      >
                        <p className="font-medium text-sm">
                          {mergePreview[opt]?.full_name}
                        </p>
                        <p className="text-xs text-slate-500">
                          Creado: {formatDate(mergePreview[opt]?.created_at)}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Merge options */}
                <div className="space-y-3">
                  <Label>Opciones de Fusión</Label>
                  {[
                    { key: 'merge_experience', label: 'Combinar experiencia laboral' },
                    { key: 'merge_education', label: 'Combinar educación' },
                    { key: 'merge_skills', label: 'Combinar skills' },
                    { key: 'merge_notes', label: 'Combinar notas' },
                    { key: 'keep_all_cvs', label: 'Conservar todos los CVs como versiones' },
                  ].map(({ key, label }) => (
                    <div key={key} className="flex items-center space-x-2">
                      <Checkbox
                        id={key}
                        checked={mergeOptions[key]}
                        onCheckedChange={(checked) => 
                          setMergeOptions(prev => ({ ...prev, [key]: checked }))
                        }
                      />
                      <Label htmlFor={key} className="text-sm cursor-pointer">
                        {label}
                      </Label>
                    </div>
                  ))}
                </div>

                {/* Preview */}
                <Alert className="bg-slate-50">
                  <ArrowRight className="w-4 h-4" />
                  <AlertDescription>
                    <strong>{mergePreview[primaryCandidate]?.full_name}</strong> será el registro principal.
                    El otro registro será marcado como fusionado y no aparecerá en búsquedas.
                  </AlertDescription>
                </Alert>
              </div>
            )}

            <DialogFooter>
              <Button variant="outline" onClick={() => setMergeDialogOpen(false)}>
                Cancelar
              </Button>
              <Button onClick={handleMerge} disabled={merging || !primaryCandidate}>
                {merging ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Fusionando...
                  </>
                ) : (
                  <>
                    <Merge className="w-4 h-4 mr-2" />
                    Confirmar Fusión
                  </>
                )}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </Layout>
  );
};

export default DuplicatesPage;
