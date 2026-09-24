import React, { useState, useEffect, useCallback, useRef } from 'react';
import Layout from '../components/Layout';
import { Button } from '../components/ui/button';
import { Alert, AlertDescription } from '../components/ui/alert';
import { CheckCircle2, Loader2, RefreshCw, ChevronLeft, ChevronRight, ListChecks } from 'lucide-react';
import { toast } from 'sonner';
import { useTaxonomy } from '../contexts/TaxonomyContext';
import { reviewAPI } from '../api';
import { ReviewCandidateCard } from '../components/review/ReviewCandidateCard';
import { ReviewRecheckProgress } from '../components/review/ReviewRecheckProgress';
import { useAuth } from '../contexts/AuthContext';

export default function ClassificationReviewPage() {
  const taxonomy = useTaxonomy();
  const { user } = useAuth();
  const canManage = ['admin', 'super_admin'].includes(user?.role);
  const [recheckBatch, setRecheckBatch] = useState(null);
  const [rechecking, setRechecking] = useState(false);
  const { refetch: refetchTaxonomy } = taxonomy;
  const [candidates, setCandidates] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [selected, setSelected] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [savingIds, setSavingIds] = useState([]);
  const [error, setError] = useState('');
  const [bulkErrors, setBulkErrors] = useState([]);
  const requestSequence = useRef(0);
  const load = useCallback(async () => {
    const sequence = ++requestSequence.current;
    setLoading(true); setError('');
    try {
      const { data } = await reviewAPI.getPending(page);
      if (sequence !== requestSequence.current) return;
      const lastPage = Math.max(1, data.pages);
      setTotal(data.total); setPages(lastPage);
      if (page > lastPage) { setPage(lastPage); return; }
      setCandidates(data.candidates);
    } catch (e) { if (sequence === requestSequence.current) setError('No se pudo cargar la bandeja. Vuelve a intentarlo.'); }
    finally { if (sequence === requestSequence.current) setLoading(false); }
  }, [page]);
  useEffect(() => { load(); return () => { requestSequence.current += 1; }; }, [load]);
  // The existing taxonomy provider may still be loading when this route is opened.
  useEffect(() => { refetchTaxonomy(); }, [refetchTaxonomy]);
  const blocked = busy || loading || rechecking || savingIds.length > 0;
  useEffect(() => {
    let live = true;
    if (!canManage) { setSelected([]); setRecheckBatch(null); setRechecking(false); return; }
    reviewAPI.latestRecheck().then(({ data }) => {
      if (live && data.batch_id && localStorage.getItem(`review-dismissed-${user?.id}`) !== data.batch_id) setRecheckBatch(data.batch_id);
    }).catch(() => {});
    return () => { live = false; };
  }, [user?.id, canManage]);
  const recheck = async ids => {
    if (!canManage) return;
    if (ids.length > 50) { toast.error('Máximo 50 CVs por lote de revisión. Tu selección se conserva.'); return; }
    setBusy(true);
    try { const { data } = await reviewAPI.recheck(ids); setRecheckBatch(data.batch_id); setRechecking(true); }
    catch (e) { toast.error(typeof e.response?.data?.detail === 'string' ? e.response.data.detail : 'No se pudo iniciar la revisión. Tu selección se conserva.'); }
    finally { setBusy(false); }
  };
  const recheckComplete = response => {
    const resolved = new Set(response.jobs.filter(job => job.review_status === 'classified').map(job => job.candidate_id));
    setSelected(previous => previous.filter(id => !resolved.has(id)));
    window.dispatchEvent(new Event('classification-review-updated')); load();
  };
  const dismissRecheck = () => {
    try { localStorage.setItem(`review-dismissed-${user?.id}`, recheckBatch); } catch { /* Dismiss still works when browser storage is unavailable. */ }
    setRecheckBatch(null); setRechecking(false);
  };
  const onSaving = useCallback((id, value) => setSavingIds(prev => value ? [...new Set([...prev, id])] : prev.filter(x => x !== id)), []);
  const onSaved = (id, fields) => setCandidates(prev => prev.map(c => c.id !== id ? c : {
    ...c, manually_edited: true,
    current_classification: { ...c.current_classification, ...fields },
    proposed_classification: { ...c.proposed_classification, ...fields },
  }));
  const selectAll = async () => {
    setBusy(true); setError('');
    try { const { data } = await reviewAPI.getPendingIds(); setSelected(data.candidate_ids); }
    catch (e) { setError('No se pudo seleccionar toda la bandeja. Tu selección anterior se conserva.'); }
    finally { setBusy(false); }
  };
  const approve = async (ids, individual = false) => {
    if (!canManage) return;
    setBusy(true); setBulkErrors([]);
    try {
      const { data } = individual ? await reviewAPI.approve(ids[0]) : await reviewAPI.bulkApprove(ids);
      const failures = data.errors || [];
      setBulkErrors(failures);
      const failedIds = new Set(failures.map(e => e.id));
      setSelected(prev => prev.filter(id => !ids.includes(id) || failedIds.has(id)));
      const count = individual ? 1 : data.approved_count;
      if (count) toast.success(`${count} ${count === 1 ? 'clasificación aprobada' : 'clasificaciones aprobadas'}`);
      if (failures.length) toast.warning(`${failures.length} fichas siguen pendientes`);
      window.dispatchEvent(new Event('classification-review-updated'));
      await load();
    } catch (e) { toast.error(e.response?.data?.detail || 'No se pudo aprobar. La selección se conserva.'); }
    finally { setBusy(false); }
  };
  return (
    <Layout title="Clasificaciones por revisar">
      <div className="min-w-0 space-y-6" data-testid="classification-review-page">
        <div className="flex flex-wrap items-end justify-between gap-4 border-b pb-5">
          <div className="flex flex-wrap gap-6 sm:gap-10">
            <div><p data-testid="review-pending-total" className="text-3xl font-semibold text-slate-900">{total}</p><p className="text-xs text-slate-500">Pendientes</p></div>
            <div><p data-testid="review-selected-total" className="text-3xl font-semibold text-cyan-700">{selected.length}</p><p className="text-xs text-slate-500">Seleccionados</p></div>
            <div><p data-testid="review-confidence-threshold" className="text-3xl font-semibold text-amber-700">&lt;75%</p><p className="text-xs text-slate-500">Confianza IA</p></div>
          </div>
          <Button data-testid="review-refresh" variant="outline" onClick={load} disabled={blocked}><RefreshCw className={`mr-2 h-4 w-4 ${loading ? 'animate-spin' : ''}`} />Actualizar</Button>
        </div>
        {canManage && <div className="flex flex-wrap items-center gap-2">
          <Button data-testid="review-select-all" variant="outline" onClick={selectAll} disabled={blocked || !total}><ListChecks className="mr-2 h-4 w-4" />Seleccionar todos ({total})</Button>
          {!!selected.length && <Button data-testid="review-clear-selection" variant="ghost" onClick={() => setSelected([])} disabled={blocked}>Deseleccionar todos</Button>}
          <Button data-testid="review-bulk-approve" className="bg-green-700 hover:bg-green-800" onClick={() => approve(selected)} disabled={blocked || !selected.length}><CheckCircle2 className="mr-2 h-4 w-4" />Aprobar seleccionados ({selected.length})</Button>
          <Button data-testid="review-bulk-recheck" variant="outline" disabled={blocked || !selected.length} onClick={() => recheck(selected)}><RefreshCw className="mr-2 h-4 w-4" />Volver a revisar seleccionados</Button>
        </div>}
        {!canManage && <p data-testid="review-permissions-notice" className="text-sm text-slate-600">Aprobación y revisión IA: solo administración.</p>}
        {recheckBatch && <ReviewRecheckProgress batchId={recheckBatch} onComplete={recheckComplete} onBusy={setRechecking} onClose={dismissRecheck} />}
        {error && <Alert data-testid="review-load-error" variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}
        {bulkErrors.length > 0 && <Alert data-testid="review-bulk-errors" variant="destructive"><AlertDescription><p>{bulkErrors.length} fichas no se aprobaron:</p><ul className="mt-2 space-y-1">{bulkErrors.map(e => <li data-testid={`review-bulk-error-${e.id}`} key={e.id} className="break-words">{candidates.find(c => c.id === e.id)?.full_name || e.id}: {e.error}</li>)}</ul></AlertDescription></Alert>}
        {loading && !candidates.length ? <div data-testid="review-loading" role="status" className="py-16 text-center"><Loader2 className="mx-auto h-7 w-7 animate-spin text-cyan-600" /></div> : !error && !candidates.length ? <div data-testid="review-empty" className="py-16 text-center text-slate-500"><CheckCircle2 className="mx-auto mb-3 h-10 w-10 text-green-600" />No hay clasificaciones pendientes.</div> : (
          <div className="space-y-4">{candidates.map(c => <ReviewCandidateCard key={c.id} candidate={c} canManage={canManage} canEdit={canManage || c.can_edit === true} selected={selected.includes(c.id)} toggle={() => setSelected(prev => prev.includes(c.id) ? prev.filter(id => id !== c.id) : [...prev, c.id])} taxonomy={taxonomy} onSaved={onSaved} onSaving={onSaving} onApprove={id => approve([id], true)} onRecheck={id => recheck([id])} busy={busy || loading || rechecking} />)}</div>
        )}
        {pages > 1 && <div className="flex flex-wrap items-center justify-between gap-3 border-t pt-4"><p data-testid="review-pagination-status" className="text-sm text-slate-500">Página {page} de {pages} · {total} pendientes</p><div className="flex gap-2"><Button data-testid="review-previous-page" variant="outline" disabled={blocked || page === 1} onClick={() => setPage(p => p - 1)}><ChevronLeft className="mr-1 h-4 w-4" />Anterior</Button><Button data-testid="review-next-page" variant="outline" disabled={blocked || page === pages} onClick={() => setPage(p => p + 1)}>Siguiente<ChevronRight className="ml-1 h-4 w-4" /></Button></div></div>}
      </div>
    </Layout>
  );
}