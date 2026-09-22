import React, { useEffect, useRef, useState } from 'react';
import { Loader2, RefreshCw, X } from 'lucide-react';
import { Button } from '../ui/button';
import { Progress } from '../ui/progress';
import { reviewAPI } from '../../api';

export const ReviewRecheckProgress = ({ batchId, onComplete, onClose, onBusy }) => {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  const callbacks = useRef({ onComplete, onBusy });
  callbacks.current = { onComplete, onBusy };
  useEffect(() => {
    let disposed = false, timer, running = false, notified = false;
    setData(null); setError(''); callbacks.current.onBusy(true);
    const poll = async () => {
      if (disposed || running) return;
      running = true; clearTimeout(timer);
      let done = false;
      try {
        const { data: response } = await reviewAPI.recheckStatus(batchId);
        if (disposed) return;
        setData(response); setError(''); done = response.is_complete;
        callbacks.current.onBusy(!done);
        if (done && !notified) { notified = true; callbacks.current.onComplete(response); }
      } catch (e) {
        if (disposed) return;
        setError('No se pudo actualizar el progreso. La revisión continúa en el servidor.');
        if ([403, 404].includes(e.response?.status)) { done = true; callbacks.current.onBusy(false); }
      } finally {
        running = false;
        if (!disposed && !done) timer = setTimeout(poll, 2500);
      }
    };
    const resume = () => { if (!notified && document.visibilityState !== 'hidden') poll(); };
    poll(); window.addEventListener('focus', resume); window.addEventListener('online', resume); document.addEventListener('visibilitychange', resume);
    return () => { disposed = true; clearTimeout(timer); window.removeEventListener('focus', resume); window.removeEventListener('online', resume); document.removeEventListener('visibilitychange', resume); };
  }, [batchId, retry]);
  return (
    <section data-testid="review-recheck-progress" className="space-y-3 border-y border-cyan-200 py-4">
      <div className="flex flex-wrap items-center justify-between gap-2"><h2 className="text-base font-semibold">Segunda pasada</h2><Button data-testid="review-recheck-dismiss" variant="ghost" size="icon" aria-label="Cerrar seguimiento de revisión" onClick={onClose}><X className="h-4 w-4" /></Button></div>
      {data ? <><p data-testid="review-recheck-count" role="status" className="text-sm">{data.completed + data.failed} de {data.total} revisados{data.failed > 0 ? ` · ${data.failed} sin completar` : ''}</p><Progress data-testid="review-recheck-bar" value={100 * (data.completed + data.failed) / data.total} /><ul className="max-h-52 space-y-2 overflow-y-auto text-sm">{data.jobs.map(job => <li data-testid={`review-recheck-result-${job.candidate_id}`} key={job.candidate_id} className="break-words"><span className="font-medium">{job.name || job.candidate_id}</span>: {job.status === 'failed' ? job.message : job.review_status === 'manual_capture' ? 'Requiere captura manual' : job.review_status === 'classified' ? `Clasificado · ${Math.round(job.confidence_score * 100)}%` : job.status === 'completed' ? 'Sigue pendiente de revisión' : 'En proceso'}{job.cache_hit && ' · Resultado guardado'}{job.status === 'completed' && job.message && <p className="text-xs text-amber-800">{job.message}</p>}</li>)}</ul></> : <Loader2 data-testid="review-recheck-loading" className="h-5 w-5 animate-spin" />}
      {error && <div data-testid="review-recheck-error" role="alert" className="text-sm text-amber-800">{error}<Button data-testid="review-recheck-reconnect" variant="ghost" size="sm" onClick={() => setRetry(n => n + 1)}><RefreshCw className="mr-1 h-4 w-4" />Actualizar</Button></div>}
    </section>
  );
};