import React, { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Progress } from './ui/progress';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from './ui/collapsible';
import { Loader2, Zap, ChevronDown, ChevronUp } from 'lucide-react';
import { toast } from 'sonner';
import { jobsAPI } from '../api';

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

const ACTION_CONFIG = {
  advance_to_screening: { label: 'Avanzar a screening', color: 'bg-green-100 text-green-800' },
  review_manually: { label: 'Revisión manual', color: 'bg-yellow-100 text-yellow-800' },
  possible_backup: { label: 'Posible backup', color: 'bg-orange-100 text-orange-800' },
  low_priority: { label: 'Prioridad baja', color: 'bg-gray-100 text-gray-800' },
  do_not_advance_knockout: { label: 'No avanzar (knockout)', color: 'bg-red-100 text-red-800' },
  save_for_other_role: { label: 'Guardar para otro rol', color: 'bg-blue-100 text-blue-800' },
};

const KNOCKOUT_STATUS_CONFIG = {
  cumple: { color: 'bg-green-500', label: 'Cumple' },
  no_aplica: { color: 'bg-gray-400', label: 'No aplica' },
  evidencia_insuficiente: { color: 'bg-yellow-500', label: 'Evidencia insuficiente' },
  parcial: { color: 'bg-yellow-500', label: 'Parcial' },
  no_cumple_importante: { color: 'bg-orange-500', label: 'No cumple (importante)' },
  no_cumple_fatal: { color: 'bg-red-500', label: 'No cumple (fatal)' },
};

const MatchV3Results = ({ jobId }) => {
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [processType, setProcessType] = useState(null);
  const [expanded, setExpanded] = useState({});

  const runMatchV3 = async () => {
    setLoading(true);
    try {
      const response = await jobsAPI.matchV3(jobId, 50);
      const data = response.data;
      const v3Results = data.engine === 'compare' ? data.v3 : data.results;
      setResults(v3Results || []);
      if (v3Results?.length > 0) {
        setProcessType(v3Results[0].process_type);
      }
      toast.success(`Matching v3 completado: ${(v3Results || []).length} candidatos evaluados`);
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
              Resultados Matching v3
            </CardTitle>
            <CardDescription>
              Humaniq Match Score (HMS) con desglose de 11 componentes
              {processType && ` — proceso: ${processType}`}
            </CardDescription>
          </div>
          <Button onClick={runMatchV3} disabled={loading} variant="outline" size="sm" data-testid="run-match-v3-btn">
            {loading && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
            {results ? 'Re-ejecutar' : 'Ejecutar Matching v3'}
          </Button>
        </div>
      </CardHeader>
      <CardContent>
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
              const action = ACTION_CONFIG[r.recommended_action] || { label: r.recommended_action, color: 'bg-gray-100 text-gray-800' };
              const isOpen = expanded[r.candidate_id];
              const hecPct = Math.round((r.confidence_score || 0) * 100);
              return (
                <Card key={r.candidate_id} className="border" data-testid="match-v3-result-card">
                  <Collapsible open={isOpen} onOpenChange={() => toggleExpanded(r.candidate_id)}>
                    <div className="p-4">
                      <div className="flex items-center justify-between gap-4">
                        <div className="flex items-center gap-4 flex-1 min-w-0">
                          <div className="flex-shrink-0 w-8 h-8 rounded-full bg-slate-100 flex items-center justify-center font-bold text-slate-600">
                            {index + 1}
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                              <h4 className="font-semibold text-slate-900 truncate">{r.candidate_name}</h4>
                              <Badge className={`${action.color} border-0`} data-testid="match-v3-action-badge">
                                {action.label}
                              </Badge>
                            </div>
                            {r.current_title && (
                              <p className="text-sm text-slate-600 truncate">{r.current_title}</p>
                            )}
                          </div>
                        </div>
                        <div className="flex items-center gap-4 flex-shrink-0">
                          <div className="text-right">
                            <div className="text-3xl font-bold text-slate-900" data-testid="match-v3-hms">
                              {r.match_score_v3}
                            </div>
                            <div className="text-xs text-slate-500">HMS</div>
                          </div>
                          <CollapsibleTrigger asChild>
                            <Button variant="outline" size="sm" data-testid="match-v3-breakdown-toggle">
                              {isOpen ? <ChevronUp className="w-4 h-4 mr-1" /> : <ChevronDown className="w-4 h-4 mr-1" />}
                              Ver desglose
                            </Button>
                          </CollapsibleTrigger>
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
                                    return (
                                      <tr key={code} className="border-b border-slate-100" data-testid={`match-v3-component-${code}`}>
                                        <td className="py-1.5 pr-2">
                                          <span className="font-mono text-xs text-slate-500 mr-2">{code}</span>
                                          {COMPONENT_LABELS[code] || code}
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
    </Card>
  );
};

export default MatchV3Results;
