import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Checkbox } from './ui/checkbox';
import { Alert, AlertDescription } from './ui/alert';
import { Loader2, Trash2, CheckCircle2, AlertTriangle, Merge, FileCheck, ExternalLink } from 'lucide-react';import { toast } from 'sonner';
import axios from 'axios';

const API_BASE = process.env.REACT_APP_BACKEND_URL || '';

const STATUS_META = {
  safe: { label: 'Listo para eliminar sobrantes', className: 'bg-emerald-50 text-emerald-700 border-emerald-300' },
  merge_required: { label: 'Requiere fusión N-a-1', className: 'bg-amber-50 text-amber-700 border-amber-300' },
  manual_review: { label: 'Revisar manual', className: 'bg-rose-50 text-rose-700 border-rose-300' },
};

const formatDate = (value) => {
  if (!value) return 'Sin fecha';
  return new Date(value).toLocaleDateString('es-MX', { year: 'numeric', month: 'short', day: 'numeric' });
};

const MemberRow = ({ member, isKeep, onDelete, canDelete, working }) => (
  <div className={`p-3 rounded-lg border text-sm ${isKeep ? 'border-emerald-300 bg-emerald-50/60' : 'border-slate-200'}`}>
    <div className="flex items-start justify-between gap-3">
      <div className="min-w-0">
        <p className="font-medium text-slate-900 truncate">{member.name || 'Sin nombre'}</p>
        <p className="text-xs text-slate-500 mt-0.5">
          Cargado {formatDate(member.upload_date || member.created_at)} · por {member.uploaded_by || 'desconocido'}
        </p>
        <p className="text-xs text-slate-400 truncate">{(member.file_names || []).join(', ')}</p>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        {isKeep ? (
          <Badge className="bg-emerald-600">Se conserva</Badge>
        ) : (
          <Badge variant="outline" className="text-slate-500">Sobrante</Badge>
        )}
        {!isKeep && onDelete && (
          <Button
            size="sm"
            variant="ghost"
            disabled={!canDelete || working}
            title={canDelete ? 'Eliminar esta ficha' : 'Solo administradores pueden eliminar'}
            className="h-7 px-2 text-red-600 hover:text-red-700 hover:bg-red-50"
            onClick={() => onDelete(member)}
            data-testid={`identical-cv-delete-member-${member.candidate_id}`}
          >
            <Trash2 className="w-4 h-4" />
          </Button>
        )}
        <a
          href={`/candidates/${member.candidate_id}`}
          target="_blank"
          rel="noreferrer"
          className="text-slate-400 hover:text-slate-700"
          data-testid={`identical-cv-open-${member.candidate_id}`}
        >
          <ExternalLink className="w-4 h-4" />
        </a>
      </div>
    </div>
    {(member.notes > 0 || member.assignments > 0 || member.cv_versions > 0) && (
      <p className="text-xs text-amber-700 mt-2">
        {member.notes} notas · {member.assignments} asignaciones · {member.cv_versions} versiones de CV
      </p>
    )}
  </div>
);

export const IdenticalCVTab = () => {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const [selected, setSelected] = useState([]);
  const [working, setWorking] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API_BASE}/api/duplicates/identical-cv`);
      setData(res.data);
      setSelected([]);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error cargando CVs idénticos');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const safeGroups = (data?.groups || []).filter((g) => g.status === 'safe');

  const toggle = (key) => {
    setSelected((prev) => (prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]));
  };

  const selectAll = () => {
    setSelected(selected.length === safeGroups.length ? [] : safeGroups.map((g) => g.group_key));
  };

  const deleteExtras = async (groupKeys) => {
    if (!groupKeys.length) return;
    const total = (data?.groups || [])
      .filter((g) => groupKeys.includes(g.group_key))
      .reduce((sum, g) => sum + g.extras.length, 0);
    if (!window.confirm(`Se eliminarán ${total} fichas sobrantes (recuperables). ¿Continuar?`)) return;
    setWorking(true);
    try {
      const res = await axios.post(`${API_BASE}/api/duplicates/identical-cv/delete-extras`, { group_keys: groupKeys });
      if (res.data.deleted_count === 0) {
        toast.warning(`No se eliminó ninguna ficha (${res.data.skipped?.length || 0} grupos omitidos)`);
      } else {
        toast.success(res.data.message);
      }
      if (res.data.skipped?.length) {
        toast.warning(`${res.data.skipped.length} grupos omitidos por seguridad`);
      }
      await load();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error eliminando sobrantes');
    } finally {
      setWorking(false);
    }
  };

  const deleteMember = async (member) => {
    if (!window.confirm(`¿Eliminar la ficha de ${member.name}? Es recuperable desde Papelera.`)) return;
    setWorking(true);
    try {
      const res = await axios.post(`${API_BASE}/api/duplicates/delete-candidates`, { candidate_ids: [member.candidate_id] });
      if (res.data.deleted_count > 0) {
        toast.success(res.data.message);
      }
      if (res.data.blocked?.length > 0) {
        toast.warning('La ficha tiene notas, asignaciones o historial: fusiónala en lugar de eliminarla', { duration: 8000 });
      }
      await load();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error al eliminar la ficha');
    } finally {
      setWorking(false);
    }
  };

  const mergeGroup = async (group) => {    if (!window.confirm(`Se fusionarán ${group.extras.length} fichas en ${group.keep.name}. Los CVs se conservan como versiones. ¿Continuar?`)) return;
    setWorking(true);
    try {
      const res = await axios.post(`${API_BASE}/api/candidates/merge-multiple`, {
        primary_candidate_id: group.keep.candidate_id,
        secondary_candidate_ids: group.extras.map((m) => m.candidate_id),
        merge_experience: true,
        merge_education: true,
        merge_skills: true,
        merge_notes: true,
        keep_all_cvs: true,
      });
      toast.success(res.data.message);
      await load();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error al fusionar');
    } finally {
      setWorking(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="w-8 h-8 animate-spin text-cyan-600" />
      </div>
    );
  }

  const summary = data?.summary || {};

  return (
    <div className="space-y-6" data-testid="identical-cv-tab">
      <div className="grid grid-cols-4 gap-4">
        {[
          { icon: FileCheck, value: data?.total_groups || 0, label: 'Grupos con CV idéntico', color: 'text-slate-700 bg-slate-100' },
          { icon: CheckCircle2, value: summary.safe || 0, label: 'Listos para eliminar', color: 'text-emerald-700 bg-emerald-100' },
          { icon: Merge, value: summary.merge_required || 0, label: 'Requieren fusión', color: 'text-amber-700 bg-amber-100' },
          { icon: AlertTriangle, value: summary.manual_review || 0, label: 'Revisión manual', color: 'text-rose-700 bg-rose-100' },
        ].map(({ icon: Icon, value, label, color }) => (
          <Card key={label}>
            <CardContent className="pt-6">
              <div className="flex items-center gap-3">
                <div className={`p-2 rounded-lg ${color}`}>
                  <Icon className="w-5 h-5" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-slate-900">{value}</p>
                  <p className="text-sm text-slate-500">{label}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Alert className="bg-slate-50">
        <AlertDescription className="text-slate-600 text-sm">
          Idéntico = mismo hash SHA-256 del archivo o del texto extraído normalizado. Un CV distinto de la misma
          persona es una <strong>versión</strong> y nunca aparece aquí. Se conserva la ficha con clasificación
          aprobada y, si ninguna la tiene, la más antigua. Eliminar es reversible (soft delete).
        </AlertDescription>
      </Alert>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <div>
            <CardTitle>CV idénticos</CardTitle>
            <CardDescription>{summary.extras || 0} fichas sobrantes en total</CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={selectAll} data-testid="identical-cv-select-all">
              {selected.length === safeGroups.length && safeGroups.length > 0 ? 'Quitar selección' : 'Seleccionar todos'}
            </Button>
            <Button
              variant="destructive"
              size="sm"
              disabled={working || selected.length === 0 || !data?.can_delete}
              onClick={() => deleteExtras(selected)}
              data-testid="identical-cv-delete-batch"
            >
              {working ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Trash2 className="w-4 h-4 mr-2" />}
              Eliminar sobrantes ({selected.length})
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {(data?.groups || []).length === 0 ? (
            <div className="text-center py-12 text-slate-500">
              <CheckCircle2 className="w-12 h-12 mx-auto mb-3 text-emerald-500" />
              <p>No hay CVs idénticos</p>
            </div>
          ) : (
            <div className="space-y-4 max-h-[620px] overflow-y-auto pr-1">
              {data.groups.map((group) => {
                const meta = STATUS_META[group.status];
                return (
                  <div
                    key={group.group_key}
                    className="border border-slate-200 rounded-xl p-4 space-y-3"
                    data-testid={`identical-cv-group-${group.keep.candidate_id}`}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex items-center gap-3">
                        {group.status === 'safe' && data?.can_delete && (
                          <Checkbox
                            checked={selected.includes(group.group_key)}
                            onCheckedChange={() => toggle(group.group_key)}
                            data-testid={`identical-cv-check-${group.keep.candidate_id}`}
                          />
                        )}
                        <Badge variant="outline" className={meta.className}>{meta.label}</Badge>
                        <Badge variant="outline" className="text-slate-500">
                          {group.extras.length + 1} fichas · match {group.match === 'file' ? 'archivo' : 'texto'}
                        </Badge>
                      </div>
                      <div className="flex gap-2">
                        {group.status === 'safe' && (
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={working || !data?.can_delete}
                            onClick={() => deleteExtras([group.group_key])}
                            data-testid={`identical-cv-delete-${group.keep.candidate_id}`}
                          >
                            <Trash2 className="w-4 h-4 mr-2" />
                            Eliminar sobrantes
                          </Button>
                        )}
                        {group.status === 'merge_required' && (
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={working}
                            onClick={() => mergeGroup(group)}
                            data-testid={`identical-cv-merge-${group.keep.candidate_id}`}
                          >
                            <Merge className="w-4 h-4 mr-2" />
                            Fusionar N-a-1
                          </Button>
                        )}
                      </div>
                    </div>
                    <div className="grid gap-2">
                      <MemberRow member={group.keep} isKeep />
                      {group.extras.map((member) => (
                        <MemberRow
                          key={member.candidate_id}
                          member={member}
                          isKeep={false}
                          canDelete={data?.can_delete}
                          working={working}
                          onDelete={deleteMember}
                        />
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default IdenticalCVTab;
