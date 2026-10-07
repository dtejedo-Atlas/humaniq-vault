import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Loader2, Sparkles, AlertTriangle, CheckCircle2, HelpCircle, RefreshCw } from 'lucide-react';
import { toast } from 'sonner';
import { aiAPI } from '../api';
import CandidateQuickActions from './CandidateQuickActions';

const FIT_STYLES = {
  alto: 'bg-emerald-100 text-emerald-800 border-emerald-300',
  medio: 'bg-amber-100 text-amber-800 border-amber-300',
  bajo: 'bg-rose-100 text-rose-800 border-rose-300',
};

const Bullets = ({ icon: Icon, title, items, tone }) => {
  if (!items || items.length === 0) return null;
  return (
    <div>
      <p className={`text-xs font-semibold flex items-center gap-1 ${tone}`}>
        <Icon className="w-3.5 h-3.5" />
        {title}
      </p>
      <ul className="mt-1 space-y-1">
        {items.map((item, index) => (
          <li key={index} className="text-sm text-slate-600 pl-4 relative">
            <span className="absolute left-0 top-1.5 w-1.5 h-1.5 rounded-full bg-slate-300" />
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
};

export const AIMatchReview = ({ jobId, hasMatches }) => {
  const [review, setReview] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    aiAPI.getMatchReview(jobId)
      .then((res) => { if (res.data.exists) setReview(res.data); })
      .catch(() => {});
  }, [jobId]);

  const run = async () => {
    setLoading(true);
    try {
      const res = await aiAPI.createMatchReview(jobId, 5, 50);
      setReview(res.data);
      if (res.data.total_reviewed === 0) {
        toast.info('El motor no devolvió candidatos para analizar');
      } else {
        toast.success(`Análisis listo: ${res.data.total_reviewed} finalistas revisados`);
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || 'El análisis de IA no se pudo completar');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card className="border-violet-200" data-testid="ai-match-review">
      <CardHeader>
        <div className="flex justify-between items-start gap-4">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-violet-600" />
              Análisis IA del match
            </CardTitle>
            <CardDescription>
              Claude revisa la terna del motor y da criterio de reclutador. No cambia los scores ni el orden.
              {review?.model && <span className="ml-1 text-slate-400">Modelo: {review.model}</span>}
            </CardDescription>
          </div>
          <Button
            onClick={run}
            disabled={loading || !hasMatches}
            className="bg-violet-600 hover:bg-violet-700"
            size="sm"
            data-testid="run-ai-match-review"
          >
            {loading
              ? <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              : review ? <RefreshCw className="w-4 h-4 mr-2" /> : <Sparkles className="w-4 h-4 mr-2" />}
            {loading ? 'Analizando…' : review ? 'Volver a analizar' : 'Analizar terna'}
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {loading && (
          <div className="flex items-center justify-center py-10 text-slate-500">
            <Loader2 className="w-6 h-6 animate-spin text-violet-600" />
            <span className="ml-2">Claude está evaluando a los finalistas…</span>
          </div>
        )}

        {!loading && !review && (
          <p className="text-sm text-slate-500 py-6 text-center">
            {hasMatches
              ? 'Pulsa "Analizar terna" para obtener fortalezas, brechas y preguntas de entrevista por candidato.'
              : 'Primero necesitas candidatos compatibles para esta vacante.'}
          </p>
        )}

        {!loading && review && (
          <div className="space-y-4">
            {review.summary && (
              <div className="bg-violet-50 border border-violet-200 rounded-lg p-3" data-testid="ai-review-summary">
                <p className="text-sm text-violet-900">{review.summary}</p>
                {review.search_advice && (
                  <p className="text-xs text-violet-700 mt-2">Siguiente paso: {review.search_advice}</p>
                )}
              </div>
            )}

            {review.shortlist?.map((item) => (
              <div
                key={item.candidate_id}
                className="border border-slate-200 rounded-xl p-4 space-y-3"
                data-testid={`ai-review-candidate-${item.candidate_id}`}
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <p className="font-semibold text-slate-900 truncate">
                      #{item.rank} {item.name}
                    </p>
                    <p className="text-xs text-slate-500 truncate">{item.current_title || 'Sin puesto'}</p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <Badge variant="outline" className="text-slate-600">{item.match_score}% motor</Badge>
                    {item.fit && (
                      <Badge variant="outline" className={FIT_STYLES[item.fit] || 'text-slate-600'}>
                        Fit {item.fit}
                      </Badge>
                    )}
                  </div>
                </div>

                {item.verdict && <p className="text-sm text-slate-700">{item.verdict}</p>}

                <CandidateQuickActions candidate={item} originLabel="terna IA" compact idPrefix="review-" />

                <div className="grid md:grid-cols-2 gap-4">
                  <Bullets icon={CheckCircle2} title="Fortalezas" items={item.strengths} tone="text-emerald-700" />
                  <Bullets icon={AlertTriangle} title="Brechas" items={item.gaps} tone="text-amber-700" />
                  <Bullets icon={HelpCircle} title="Preguntas de entrevista" items={item.interview_questions} tone="text-cyan-700" />
                  <Bullets icon={AlertTriangle} title="Riesgos" items={item.risk_flags} tone="text-rose-700" />
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default AIMatchReview;
