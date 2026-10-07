import React, { useState } from 'react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Badge } from './ui/badge';
import { Loader2, Sparkles, X, Bookmark, Database, AlertTriangle } from 'lucide-react';
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from './ui/dialog';
import { toast } from 'sonner';
import { jobsAPI } from '../api';

const EXAMPLES = ['que tenga experiencia en telecomunicaciones', 'que haya vendido producto fintech', 'que haya manejado equipos de más de 20 vendedores'];

export const AIRefinePanel = ({ jobId, criteria, topN, onTopNChange, onUpdated, disabled }) => {
  const [text, setText] = useState('');
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState(null); // { evaluated, total, criterion }
  const [pending, setPending] = useState(null); // { criterion, estimate }
  const [savingId, setSavingId] = useState(null);

  const refresh = async () => {
    const res = await jobsAPI.getUnifiedMatches(jobId);
    onUpdated(res.data);
    return res.data;
  };

  const poll = (criterionId, criterion) => new Promise((resolve, reject) => {
    const tick = async () => {
      try {
        const st = (await jobsAPI.aiRefineStatus(jobId, criterionId)).data;
        setProgress({ evaluated: st.evaluated || 0, total: st.total || 0, criterion });
        if (st.status === 'done') return resolve(st);
        if (st.status === 'error') return reject(new Error(st.error || 'Error al evaluar'));
        setTimeout(tick, 2500);
      } catch (e) {
        reject(e);
      }
    };
    tick();
  });

  const run = async (criterion, scope) => {
    setRunning(true);
    try {
      const started = (await jobsAPI.aiRefine(jobId, criterion, scope, topN)).data;
      setProgress({ evaluated: 0, total: started.criterion.total, criterion });
      await refresh();
      const c = await poll(started.criterion.id, criterion);
      await refresh();
      toast.success(`"${criterion}": ${c.met} cumplen · ${c.partial} parcial · ${c.evaluated} evaluados (${c.from_cache} en caché) · costo ≈ US$${c.cost_usd}`);
      if (c.none_met && scope !== 'all' && c.all_base_estimate) {
        setPending({ criterion, estimate: c.all_base_estimate });
      }
      setText('');
    } catch (e) {
      toast.error(e.response?.data?.detail || e.message || 'No se pudo afinar con IA');
    } finally {
      setRunning(false);
      setProgress(null);
    }
  };

  // Si al cargar hay un criterio en curso (p. ej. tras recargar), retomar el seguimiento
  const runningCriterion = criteria.find((c) => c.status === 'running');
  React.useEffect(() => {
    if (!runningCriterion || running) return;
    setRunning(true);
    poll(runningCriterion.id, runningCriterion.text).then(refresh).catch(() => {}).finally(() => { setRunning(false); setProgress(null); });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runningCriterion?.id]);

  const remove = async (criterionId) => {
    try {
      const res = await jobsAPI.deleteAiRefine(jobId, criterionId);
      onUpdated(res.data);
    } catch (_) {
      toast.error('No se pudo quitar el criterio');
    }
  };

  const saveAs = async (criterionId, asType) => {
    setSavingId(criterionId);
    try {
      await jobsAPI.saveCriterionAsRequirement(jobId, criterionId, asType);
      toast.success(asType === 'skill' ? 'Guardado como skill requerido del scorecard' : 'Guardado como requisito no negociable');
    } catch (_) {
      toast.error('No se pudo guardar en el scorecard');
    } finally {
      setSavingId(null);
    }
  };

  return (
    <div className="rounded-lg border border-violet-200 bg-violet-50/40 p-4 space-y-3" data-testid="ai-refine-panel">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2 text-violet-900 font-medium">
          <Sparkles className="w-4 h-4" /> Afinar con IA
          <span className="text-xs font-normal text-slate-500">Capa 2: lee el CV completo de los primeros</span>
          <Input type="number" min={5} max={200} value={topN} onChange={(e) => onTopNChange(Number(e.target.value) || 30)}
            className="h-7 w-16 text-xs" data-testid="ai-refine-topn" />
          <span className="text-xs font-normal text-slate-500">del ranking</span>
        </div>
      </div>
      <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); if (text.trim().length >= 4) run(text.trim(), 'top'); }}>
        <Input value={text} onChange={(e) => setText(e.target.value)} placeholder={`Ej.: ${EXAMPLES[criteria.length % EXAMPLES.length]}`}
          disabled={running || disabled} data-testid="ai-refine-input" />
        <Button type="submit" disabled={running || disabled || text.trim().length < 4} className="bg-violet-600 hover:bg-violet-700" data-testid="ai-refine-run">
          {running ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <Sparkles className="w-4 h-4 mr-1" />}
          {running ? (progress ? `Leyendo CVs… ${progress.evaluated}/${progress.total}` : 'Leyendo CVs…') : 'Afinar'}
        </Button>
      </form>
      {progress && (
        <div className="h-1.5 w-full rounded bg-violet-100 overflow-hidden" data-testid="ai-refine-progress">
          <div className="h-full bg-violet-500 transition-all" style={{ width: `${progress.total ? Math.round((progress.evaluated / progress.total) * 100) : 5}%` }} />
        </div>
      )}
      {criteria.length > 0 && (
        <div className="flex flex-wrap gap-2" data-testid="ai-refine-tags">
          {criteria.map((c) => (
            <Badge key={c.id} variant="secondary" className="gap-1 bg-white border border-violet-200 text-slate-800 py-1" data-testid={`ai-criterion-${c.id}`}>
              <span className="max-w-[320px] truncate">{c.text}</span>
              <span className="text-[10px] text-emerald-700">{c.met} ✓</span>
              {c.partial > 0 && <span className="text-[10px] text-amber-700">{c.partial} ~</span>}
              <span className="text-[10px] text-slate-400">· {c.status === 'running' ? `evaluando ${c.evaluated}/${c.total}` : c.scope === 'all' ? 'toda la base' : `top ${c.evaluated}`} · US${c.cost_usd}</span>
              <button type="button" title="Guardar como skill del scorecard" onClick={() => saveAs(c.id, 'skill')} disabled={savingId === c.id}
                className="ml-1 rounded p-0.5 hover:bg-violet-100" data-testid={`ai-criterion-save-skill-${c.id}`}>
                <Bookmark className="w-3 h-3 text-violet-700" />
              </button>
              <button type="button" title="Quitar criterio" onClick={() => remove(c.id)} className="rounded p-0.5 hover:bg-red-50" data-testid={`ai-criterion-remove-${c.id}`}>
                <X className="w-3 h-3 text-slate-500" />
              </button>
            </Badge>
          ))}
        </div>
      )}
      <p className="text-[11px] text-slate-500">
        Cumple / Parcial / No cumple con cita textual del CV. Sin evidencia en el CV = "No cumple (sin evidencia)". Nunca infiere. Resultados en caché por candidato, criterio y versión de CV.
      </p>

      <Dialog open={Boolean(pending)} onOpenChange={(o) => !o && setPending(null)}>
        <DialogContent data-testid="ai-refine-all-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2"><AlertTriangle className="w-5 h-5 text-amber-500" /> Nadie del top {topN} cumple</DialogTitle>
            <DialogDescription>
              Ningún candidato del ranking cumple "{pending?.criterion}". Puedes buscar en toda la base de candidatos.
            </DialogDescription>
          </DialogHeader>
          {pending?.estimate && (
            <div className="rounded-md bg-slate-50 border p-3 text-sm space-y-1" data-testid="ai-refine-all-estimate">
              <p><Database className="w-4 h-4 inline mr-1" /> {pending.estimate.candidates} candidatos · modelo {pending.estimate.model}</p>
              <p>Costo estimado: <strong>US${pending.estimate.estimated_cost_usd}</strong> · tiempo ≈ {pending.estimate.estimated_minutes} min</p>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setPending(null)} data-testid="ai-refine-all-cancel">Cancelar</Button>
            <Button className="bg-violet-600 hover:bg-violet-700" disabled={running} data-testid="ai-refine-all-confirm"
              onClick={() => { const c = pending.criterion; setPending(null); run(c, 'all'); }}>
              Buscar en toda la base
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default AIRefinePanel;
