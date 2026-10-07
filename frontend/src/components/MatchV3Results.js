import React, { useState, useEffect } from 'react';
import CandidateQuickActions from './CandidateQuickActions';
import AIRefinePanel from './AIRefinePanel';
import { loadViewState, saveViewState } from '../utils/navigation';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Progress } from './ui/progress';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Checkbox } from './ui/checkbox';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from './ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from './ui/select';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from './ui/collapsible';
import { Loader2, Zap, ChevronDown, ChevronUp, Download, FileText, FileSpreadsheet, Info } from 'lucide-react';
import { PlacedBadge, NotesBadge } from './CandidateBadges';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from './ui/tooltip';
import { toast } from 'sonner';
import { jobsAPI, exportsAPI } from '../api';

const COMPONENT_LABELS = {
  SK: 'Skills',
  ER: 'Relevancia de experiencia',
  FA: 'Afinidad funcional',
  SA: 'Alineación de seniority',
  IA: 'Afinidad de industria',
  ED: 'Profundidad ejecutiva',
  TR: 'Trayectoria',
  LO: 'Ubicación',
  SM: 'Similitud semántica',
  CQ: 'Calidad del CV',
  CC: 'Calibre de empresa',
};

const COMPONENT_ORDER = ['SK', 'ER', 'FA', 'SA', 'IA', 'ED', 'TR', 'LO', 'SM', 'CQ', 'CC'];

// Acciones RELATIVAS a la lista: Entrevistar = top 5 que pasan knockouts con HMS ≥55; Backup = siguientes 10 con HMS ≥55
export const ACTION_CONFIG = {
  interview: { label: 'Entrevistar', color: 'bg-green-100 text-green-800' },
  backup: { label: 'Backup', color: 'bg-orange-100 text-orange-800' },
  low_priority: { label: 'Prioridad baja', color: 'bg-gray-100 text-gray-800' },
  do_not_advance_knockout: { label: 'No avanza (knockout)', color: 'bg-red-100 text-red-800' },
};

// Calidad absoluta del HMS
const QUALITY_CONFIG = {
  excelente: { label: 'Excelente', color: 'text-emerald-700' },
  bueno: { label: 'Bueno', color: 'text-blue-700' },
  aceptable: { label: 'Aceptable', color: 'text-amber-700' },
  debil: { label: 'Débil', color: 'text-slate-400' },
};

const KO_STATUS = {
  cumple: { icon: '✓', cls: 'bg-emerald-50 border-emerald-200 text-emerald-800' },
  parcial: { icon: '~', cls: 'bg-amber-50 border-amber-200 text-amber-800' },
  no_cumple: { icon: '✕', cls: 'bg-red-50 border-red-200 text-red-800' },
  no_evaluado: { icon: '·', cls: 'bg-white border-dashed border-slate-200 text-slate-400' },
};

const getNeutralHint = (code, comp) => {
  if (!comp || comp.confidence > 0) return null;
  if (code === 'CC') {
    const ev = comp.evidence || {};
    if (!ev.target_caliber) {
      return 'CC neutral: define un calibre de empresa objetivo en la Configuración de Matching (v3) para activar este componente.';
    }
    return 'CC neutral: el candidato no tiene calibre de empresa inferido en su historial.';
  }
  const explanation = comp.evidence?.explanation;
  return explanation
    ? `Componente neutral: ${explanation}`
    : 'Componente neutral por falta de evidencia — no penaliza al candidato.';
};

const CRITERION_STATUS = {
  cumple: { label: 'Cumple', icon: '✓', cls: 'bg-emerald-50 border-emerald-200 text-emerald-800' },
  parcial: { label: 'Parcial', icon: '~', cls: 'bg-amber-50 border-amber-200 text-amber-800' },
  no_cumple: { label: 'No cumple', icon: '✕', cls: 'bg-slate-50 border-slate-200 text-slate-500' },
  error: { label: 'Error al evaluar', icon: '!', cls: 'bg-red-50 border-red-200 text-red-700' },
  pending: { label: 'No evaluado', icon: '·', cls: 'bg-white border-dashed border-slate-200 text-slate-400' },
};

const INDUSTRY_LABELS = {
  telecommunications: 'Telecomunicaciones', technology: 'Tecnología', fintech: 'Fintech', financial_services: 'Servicios Financieros',
  manufacturing: 'Manufactura', consumer_goods: 'Bienes de Consumo', retail: 'Retail', pharmaceutical: 'Farmacéutica', automotive: 'Automotriz',
  agriculture: 'Agricultura', energy: 'Energía', construction: 'Construcción', healthcare: 'Salud', education: 'Educación',
  logistics_supply_chain: 'Logística', transportation: 'Transporte', real_estate: 'Bienes Raíces', hospitality: 'Hospitalidad',
  industrial_services: 'Servicios Industriales', food_beverage: 'Alimentos y Bebidas', professional_services: 'Servicios Profesionales',
  mining: 'Minería', media_entertainment: 'Medios',
};

const KNOCKOUT_STATUS_CONFIG = {
  cumple: { color: 'bg-green-500', label: 'Cumple' },
  no_aplica: { color: 'bg-gray-400', label: 'No aplica' },
  evidencia_insuficiente: { color: 'bg-yellow-500', label: 'Evidencia insuficiente' },
  parcial: { color: 'bg-yellow-500', label: 'Parcial' },
  no_cumple_importante: { color: 'bg-orange-500', label: 'No cumple (importante)' },
  no_cumple_fatal: { color: 'bg-red-500', label: 'No cumple (fatal)' },
};

const MatchV3Results = ({ jobId, jobTitle, technical = true, onResultsChange }) => {
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [criteria, setCriteria] = useState([]);
  const [coverage, setCoverage] = useState(null);
  const [weakGroup, setWeakGroup] = useState(false);
  const [strongCount, setStrongCount] = useState(0);
  const [topN, setTopN] = useState(30);
  const [snapshotAt, setSnapshotAt] = useState(null);
  const [processType, setProcessType] = useState(null);
  const [expanded, setExpanded] = useState(() => loadViewState(`v3:${jobId}`)?.expanded || {});
  const [showExportDialog, setShowExportDialog] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [exportOptions, setExportOptions] = useState({
    format: 'pdf',
    limit: 10,
    includeContact: false,
    clientName: '',
  });

  useEffect(() => {
    saveViewState(`v3:${jobId}`, { expanded });
  }, [expanded, jobId]);

  const applyUnified = (data) => {
    setResults(data.results || []);
    setCriteria(data.criteria || []);
    if (data.coverage) setCoverage(data.coverage);
    setWeakGroup(Boolean(data.weak_group));
    setStrongCount(data.strong_count || 0);
    setSnapshotAt(data.snapshot_at || null);
    if (data.results?.length > 0) setProcessType(data.results[0].process_type);
    if (onResultsChange) onResultsChange((data.results || []).length);
  };

  // Una sola lista: último v3 guardado + criterios de IA acumulados (no recalcula al volver)
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    jobsAPI.getUnifiedMatches(jobId)
      .then((res) => { if (!cancelled) applyUnified(res.data); })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId]);

  const handleExport = async () => {
    setExporting(true);
    try {
      const response = await exportsAPI.exportJobShortlist(jobId, {
        format: exportOptions.format,
        limit: exportOptions.limit,
        includeContact: exportOptions.includeContact,
        clientName: exportOptions.clientName || null,
        engine: 'v3',
      });

      const downloadUrl = `${process.env.REACT_APP_BACKEND_URL}${response.data.download_url}`;
      const token = localStorage.getItem('atlas_token');
      const fileResponse = await fetch(downloadUrl, {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!fileResponse.ok) {
        throw new Error('Error descargando archivo');
      }
      const blob = await fileResponse.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = response.data.filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);

      toast.success(`Shortlist v3 exportada: ${response.data.candidate_count} candidatos`);
      setShowExportDialog(false);
    } catch (error) {
      console.error('Export v3 error:', error);
      toast.error(error.response?.data?.detail || error.message || 'Error exportando shortlist v3');
    } finally {
      setExporting(false);
    }
  };

  const runMatchV3 = async () => {
    setLoading(true);
    try {
      await jobsAPI.matchV3(jobId, 50);
      const unified = await jobsAPI.getUnifiedMatches(jobId);
      applyUnified(unified.data);
      toast.success(`Matching actualizado: ${(unified.data.results || []).length} candidatos en la lista`);
    } catch (error) {
      console.error('Error running match v3:', error);
      if (error.response?.status === 403) {
        toast.error('Motor v3 deshabilitado. Configura MATCHING_ENGINE_VERSION=v3 o compare.');
      } else {
        toast.error(error.response?.data?.detail || 'Error al ejecutar el matching v3');
      }
    } finally {
      setLoading(false);
    }
  };

  const refineCriteria = criteria.filter((c) => c.kind !== 'knockout');

  const toggleExpanded = (candidateId) => {
    setExpanded((prev) => ({ ...prev, [candidateId]: !prev[candidateId] }));
  };

  return (
    <Card data-testid="match-v3-card">
      <CardHeader>
        <div className="flex justify-between items-center">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Zap className="w-5 h-5" />
              Matching de la vacante
            </CardTitle>
            <CardDescription>
              Capa 1: ranking v3 (HMS) · Capa 2: criterios de IA sobre el CV completo — una sola lista
              {processType && ` — proceso: ${processType}`}
              {snapshotAt && (
                <span className="block text-xs text-slate-400 mt-0.5" data-testid="v3-snapshot-date">
                  Último cálculo: {new Date(snapshotAt).toLocaleString('es-MX')}
                </span>
              )}
            </CardDescription>
          </div>
          <div className="flex gap-2">
            {results?.length > 0 && (
              <Button
                onClick={() => setShowExportDialog(true)}
                variant="outline"
                size="sm"
                className="border-indigo-200 text-indigo-700 hover:bg-indigo-50"
                data-testid="export-shortlist-v3-button"
              >
                <Download className="w-4 h-4 mr-2" />
                Exportar Shortlist
              </Button>
            )}
            <Button onClick={runMatchV3} disabled={loading} variant="outline" size="sm" data-testid="run-match-v3-btn">
              {loading && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              {results ? 'Actualizar matching' : 'Ejecutar matching'}
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {coverage?.targets?.length > 0 && coverage.low_coverage && (
          <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900" data-testid="coverage-banner">
            <p className="font-medium">
              {coverage.any === 0 ? 'No hay candidatos' : `Solo hay ${coverage.any} candidato(s)`} con experiencia en {coverage.targets.map((t) => INDUSTRY_LABELS[t] || t).join(', ')} en la base.
              Mostrando los más cercanos por: función → seniority → experiencia relevante.
            </p>
            <p className="text-xs mt-1">
              {Object.entries(coverage.per_industry || {}).map(([k, v]) => `${INDUSTRY_LABELS[k] || k}: ${v}`).join(' · ')} (de {coverage.total_candidates} candidatos activos)
            </p>
          </div>
        )}
        {coverage?.targets?.length > 0 && !coverage.low_coverage && (
          <p className="text-xs text-slate-500" data-testid="coverage-summary">
            Cobertura por industria objetivo: {Object.entries(coverage.per_industry || {}).map(([k, v]) => `${INDUSTRY_LABELS[k] || k}: ${v}`).join(' · ')} · requisito: {coverage.requirement}
          </p>
        )}
        {results && weakGroup && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-900" data-testid="weak-group-banner">
            <p className="font-medium">Grupo débil para esta vacante: considera búsqueda externa.</p>
            <p className="text-xs mt-1">Solo {strongCount} candidato(s) alcanzan HMS ≥ 55 (Aceptable). Entrevistar y Backup requieren al menos 55.</p>
          </div>
        )}
        {results && (
          <AIRefinePanel jobId={jobId} criteria={criteria} topN={topN} onTopNChange={setTopN} onUpdated={applyUnified} disabled={loading} />
        )}
        {refineCriteria.length > 0 && results?.length > 0 && !results.some((r) => r.ai_met > 0 || r.ai_partial > 0) && (
          <p className="text-sm text-amber-700" data-testid="ai-none-met">Ningún candidato de la lista cumple los criterios de IA; el orden sigue siendo el del motor.</p>
        )}
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
            <span className="ml-2 text-slate-600">Calculando HMS de los candidatos...</span>
          </div>
        ) : !results ? (
          <div className="text-center py-6 text-slate-500 text-sm" data-testid="match-v3-empty-state">
            Ejecuta el matching v3 para ver el HMS y el desglose de cada candidato
          </div>
        ) : results.length === 0 ? (
          <div className="text-center py-6 text-slate-500 text-sm">
            No se evaluaron candidatos
          </div>
        ) : (
          <div className="space-y-3" data-testid="match-v3-results">
            {results.map((r, index) => {
              const action = ACTION_CONFIG[r.action] || ACTION_CONFIG.low_priority;
              const quality = QUALITY_CONFIG[r.quality] || QUALITY_CONFIG.debil;
              const isOpen = expanded[r.candidate_id];
              const hecPct = Math.round((r.confidence_score || 0) * 100);
              return (
                <Card key={r.candidate_id} className="border" data-testid={`match-v3-result-card-${r.candidate_id}`}>
                  <Collapsible open={isOpen} onOpenChange={() => toggleExpanded(r.candidate_id)}>
                    <div className="p-4">
                      <div className="flex items-center justify-between gap-4">
                        <div className="flex items-center gap-4 flex-1 min-w-0">
                          <div className="flex-shrink-0 w-8 h-8 rounded-full bg-slate-100 flex flex-col items-center justify-center font-bold text-slate-600 leading-none">
                            {index + 1}
                            {r.v3_rank && r.v3_rank !== index + 1 && <span className="text-[9px] font-normal text-slate-400">v3 #{r.v3_rank}</span>}
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                              <h4 className="font-semibold text-slate-900 truncate">{r.candidate_name}</h4>
                              {r.is_placed && <PlacedBadge />}
                              <NotesBadge count={r.notes_count} />
                              <Badge className={`${action.color} border-0`} data-testid="match-v3-action-badge">
                                {action.label}
                              </Badge>
                            </div>
                            {r.current_title && (
                              <p className="text-sm text-slate-600 truncate">
                                {r.current_title}{r.current_company ? ` @ ${r.current_company}` : ''}
                              </p>
                            )}
                            {refineCriteria.length > 0 && (
                              <div className="flex flex-wrap gap-1 mt-1.5" data-testid={`ai-criteria-${r.candidate_id}`}>
                                {refineCriteria.map((c) => {
                                  const st = r.ai_criteria?.[c.id];
                                  const cfg = CRITERION_STATUS[st?.status] || CRITERION_STATUS.pending;
                                  return (
                                    <TooltipProvider key={c.id}>
                                      <Tooltip>
                                        <TooltipTrigger asChild>
                                          <span className={`inline-flex items-center rounded px-1.5 py-0.5 text-[11px] border ${cfg.cls}`}>
                                            {cfg.icon} {c.text.length > 36 ? `${c.text.slice(0, 36)}…` : c.text}{st?.no_evidence && st?.status === 'no_cumple' ? ' (sin evidencia)' : ''}
                                          </span>
                                        </TooltipTrigger>
                                        <TooltipContent className="max-w-sm text-xs">
                                          <p className="font-medium">{cfg.label}</p>
                                          {st?.quote && <p className="mt-1 italic">"{st.quote}"</p>}
                                          {(st?.company || st?.period) && <p className="mt-1 text-slate-300">{[st.company, st.period].filter(Boolean).join(' · ')}</p>}
                                          {!st && <p className="mt-1">No evaluado para este candidato (fuera del alcance de la consulta)</p>}
                                        </TooltipContent>
                                      </Tooltip>
                                    </TooltipProvider>
                                  );
                                })}
                              </div>
                            )}
                            {r.custom_knockouts?.length > 0 && (
                              <div className="flex flex-wrap gap-1 mt-1.5" data-testid={`custom-ko-${r.candidate_id}`}>
                                {r.custom_knockouts.map((k) => {
                                  const cfg = KO_STATUS[k.status] || KO_STATUS.no_evaluado;
                                  return (
                                    <TooltipProvider key={k.id}>
                                      <Tooltip>
                                        <TooltipTrigger asChild>
                                          <span className={`inline-flex items-center rounded px-1.5 py-0.5 text-[11px] border ${cfg.cls}`}>
                                            🔒 {cfg.icon} {k.criterion.length > 36 ? `${k.criterion.slice(0, 36)}…` : k.criterion}{k.status !== 'no_evaluado' && k.k < 1 ? ` (K×${k.k})` : ''}
                                          </span>
                                        </TooltipTrigger>
                                        <TooltipContent className="max-w-sm text-xs">
                                          <p className="font-medium">No negociable ({k.severity || 'important'}): {k.status.replace('_', ' ')}</p>
                                          {k.quote && <p className="mt-1 italic">"{k.quote}"</p>}
                                          {(k.company || k.period) && <p className="mt-1 text-slate-300">{[k.company, k.period].filter(Boolean).join(' · ')}</p>}
                                          {k.status === 'no_evaluado' && <p className="mt-1">Fuera del top 30: no evaluado (neutral)</p>}
                                        </TooltipContent>
                                      </Tooltip>
                                    </TooltipProvider>
                                  );
                                })}
                              </div>
                            )}
                            {r.moved_up_by && (
                              <p className="text-xs text-violet-700 mt-1" data-testid={`moved-up-${r.candidate_id}`}>↑ {r.moved_up_by}</p>
                            )}
                            <div className="mt-2">
                              <CandidateQuickActions candidate={r} originLabel={`vacante: ${jobTitle || ''}`} compact />
                            </div>
                          </div>
                        </div>
                        <div className="flex items-center gap-4 flex-shrink-0">
                          <div className="text-right">
                            <div className="text-3xl font-bold text-slate-900" data-testid="match-v3-hms">
                              {r.match_score_v3}
                            </div>
                            <div className={`text-xs font-medium ${quality.color}`} data-testid="match-v3-quality">{quality.label}</div>
                            {r.hms_engine != null && r.hms_engine !== r.match_score_v3 && (
                              <div className="text-[10px] text-slate-400">motor {r.hms_engine} × K {r.k_custom}</div>
                            )}
                          </div>
                          {technical && <CollapsibleTrigger asChild>
                            <Button variant="outline" size="sm" data-testid="match-v3-breakdown-toggle">
                              {isOpen ? <ChevronUp className="w-4 h-4 mr-1" /> : <ChevronDown className="w-4 h-4 mr-1" />}
                              Ver desglose
                            </Button>
                          </CollapsibleTrigger>}
                        </div>
                      </div>

                      <CollapsibleContent>
                        <div className="mt-4 border-t pt-4 space-y-4" data-testid="match-v3-breakdown-panel">
                          <div>
                            <h5 className="text-sm font-semibold text-slate-700 mb-2">Componentes (11)</h5>
                            <div className="overflow-x-auto">
                              <table className="w-full text-sm">
                                <thead>
                                  <tr className="text-left text-xs text-slate-500 border-b">
                                    <th className="py-1 pr-2">Componente</th>
                                    <th className="py-1 pr-2 text-right">Raw</th>
                                    <th className="py-1 pr-2 text-right">Ajustado</th>
                                    <th className="py-1 text-right">Peso</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {COMPONENT_ORDER.map((code) => {
                                    const comp = r.component_breakdown?.[code];
                                    if (!comp) return null;
                                    const weight = r.weights_used?.[code];
                                    const neutralHint = getNeutralHint(code, comp);
                                    return (
                                      <tr key={code} className="border-b border-slate-100" data-testid={`match-v3-component-${code}`}>
                                        <td className="py-1.5 pr-2">
                                          <span className="font-mono text-xs text-slate-500 mr-2">{code}</span>
                                          {COMPONENT_LABELS[code] || code}
                                          {neutralHint && (
                                            <TooltipProvider delayDuration={150}>
                                              <Tooltip>
                                                <TooltipTrigger asChild>
                                                  <span className="inline-flex align-middle ml-1.5 cursor-help" data-testid={`match-v3-neutral-hint-${code}`}>
                                                    <Info className="w-3.5 h-3.5 text-amber-500" />
                                                  </span>
                                                </TooltipTrigger>
                                                <TooltipContent className="max-w-xs text-xs">
                                                  {neutralHint}
                                                </TooltipContent>
                                              </Tooltip>
                                            </TooltipProvider>
                                          )}
                                        </td>
                                        <td className="py-1.5 pr-2 text-right font-mono">{Number(comp.raw).toFixed(2)}</td>
                                        <td className="py-1.5 pr-2 text-right font-mono">{Number(comp.adjusted).toFixed(2)}</td>
                                        <td className="py-1.5 text-right font-mono">{weight != null ? weight.toFixed(2) : '—'}</td>
                                      </tr>
                                    );
                                  })}
                                </tbody>
                              </table>
                            </div>
                          </div>

                          <div data-testid="match-v3-hec-bar">
                            <div className="flex justify-between items-center mb-1">
                              <h5 className="text-sm font-semibold text-slate-700">Confianza (HEC)</h5>
                              <span className="text-sm font-mono text-slate-600">{hecPct}%</span>
                            </div>
                            <Progress value={hecPct} className="h-2" />
                          </div>

                          {r.knockout_results?.results?.length > 0 && (
                            <div>
                              <h5 className="text-sm font-semibold text-slate-700 mb-2">
                                Knockouts (K = {Number(r.knockout_results.K).toFixed(2)})
                              </h5>
                              <div className="space-y-1.5">
                                {r.knockout_results.results.map((ko, koIndex) => {
                                  const statusCfg = KNOCKOUT_STATUS_CONFIG[ko.status] || { color: 'bg-gray-400', label: ko.status };
                                  return (
                                    <div key={koIndex} className="flex items-center gap-2 text-sm" data-testid="match-v3-knockout-item">
                                      <span className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${statusCfg.color}`} />
                                      <span className="font-medium text-slate-700">{ko.criterion}</span>
                                      <span className="text-slate-500">— {statusCfg.label}</span>
                                      {ko.note && <span className="text-xs text-slate-400 truncate">({ko.note})</span>}
                                    </div>
                                  );
                                })}
                              </div>
                            </div>
                          )}
                        </div>
                      </CollapsibleContent>
                    </div>
                  </Collapsible>
                </Card>
              );
            })}
          </div>
        )}
      </CardContent>

      <Dialog open={showExportDialog} onOpenChange={setShowExportDialog}>
        <DialogContent className="sm:max-w-md" data-testid="export-v3-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Download className="w-5 h-5 text-indigo-600" />
              Exportar Shortlist v3
            </DialogTitle>
            <DialogDescription>
              Genera un documento con el ranking v3 (HMS y acción recomendada)
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Formato</Label>
              <div className="flex gap-3">
                <Button
                  variant={exportOptions.format === 'pdf' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setExportOptions({ ...exportOptions, format: 'pdf' })}
                  className={exportOptions.format === 'pdf' ? 'bg-indigo-600' : ''}
                  data-testid="export-v3-format-pdf"
                >
                  <FileText className="w-4 h-4 mr-2" />
                  PDF
                </Button>
                <Button
                  variant={exportOptions.format === 'docx' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setExportOptions({ ...exportOptions, format: 'docx' })}
                  className={exportOptions.format === 'docx' ? 'bg-indigo-600' : ''}
                  data-testid="export-v3-format-docx"
                >
                  <FileSpreadsheet className="w-4 h-4 mr-2" />
                  DOCX
                </Button>
              </div>
            </div>

            <div className="space-y-2">
              <Label>Número de candidatos</Label>
              <Select
                value={exportOptions.limit.toString()}
                onValueChange={(v) => setExportOptions({ ...exportOptions, limit: parseInt(v) })}
              >
                <SelectTrigger data-testid="export-v3-limit-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="5">Top 5 candidatos</SelectItem>
                  <SelectItem value="10">Top 10 candidatos</SelectItem>
                  <SelectItem value="15">Top 15 candidatos</SelectItem>
                  <SelectItem value="20">Top 20 candidatos</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>Nombre del cliente (opcional)</Label>
              <Input
                value={exportOptions.clientName}
                onChange={(e) => setExportOptions({ ...exportOptions, clientName: e.target.value })}
                placeholder="Ej: Grupo Industrial XYZ"
                data-testid="export-v3-client-input"
              />
            </div>

            <div className="flex items-center gap-2">
              <Checkbox
                id="export-v3-contact"
                checked={exportOptions.includeContact}
                onCheckedChange={(checked) => setExportOptions({ ...exportOptions, includeContact: !!checked })}
                data-testid="export-v3-contact-checkbox"
              />
              <Label htmlFor="export-v3-contact" className="text-sm font-normal">
                Incluir información de contacto (solo admin)
              </Label>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowExportDialog(false)}>
              Cancelar
            </Button>
            <Button onClick={handleExport} disabled={exporting} className="bg-indigo-600 hover:bg-indigo-700" data-testid="export-v3-confirm-btn">
              {exporting ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Download className="w-4 h-4 mr-2" />}
              Exportar
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
};

export default MatchV3Results;
