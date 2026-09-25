import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Check, RefreshCw, Loader2, ExternalLink } from 'lucide-react';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Checkbox } from '../ui/checkbox';
import { ReviewField } from './ReviewField';
import { reviewAPI } from '../../api';

const YEARS = Array.from({ length: 101 }, (_, key) => ({ key, label: `${key} ${key === 1 ? 'año' : 'años'}` }));
export const ReviewCandidateCard = ({ candidate, selected, toggle, taxonomy, onSaved, onApprove, onRecheck, busy, onSaving, canManage, canEdit }) => {
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const values = { ...candidate.current_classification, ...Object.fromEntries(Object.entries(candidate.proposed_classification || {}).filter(([, v]) => v != null)) };
  const fields = [...taxonomy.getClassificationFields(values), ['years_experience', 'Años de experiencia', YEARS]];
  const valid = fields.slice(0, 2).every(([key, , options]) => options.some(o => o.key === values[key]))
    && fields[3][2].some(o => o.key === values.presentation_seniority);
  const save = async (field, value) => {
    setSaving(true); onSaving(candidate.id, true); setError(''); setMessage('Guardando…');
    try {
      const payload = field === 'presentation_area' ? { presentation_area: value, presentation_subarea: null } : { [field]: value };
      const response = await reviewAPI.saveField(candidate.id, payload);
      onSaved(candidate.id, response.data); setMessage('Guardado · pendiente de aprobación');
    } catch (e) {
      setMessage(''); setError(e.response?.data?.detail || 'No se guardó el cambio. Inténtalo de nuevo.');
    } finally { setSaving(false); onSaving(candidate.id, false); }
  };
  return (
    <article data-testid={`review-candidate-${candidate.id}`} className={`min-w-0 rounded-md border p-4 sm:p-5 transition-colors ${selected ? 'border-cyan-400 bg-cyan-50/30' : 'border-slate-200 bg-white'}`}>
      <div className="flex items-start gap-3">
        {canManage && <Checkbox data-testid={`review-select-${candidate.id}`} aria-label={`Seleccionar ${candidate.full_name}`} checked={selected} disabled={busy || saving} onCheckedChange={toggle} className="mt-1" />}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <Link data-testid={`review-profile-${candidate.id}`} to={`/candidates/${candidate.id}`} className="font-semibold text-slate-900 hover:text-cyan-700 break-words">{candidate.full_name}<ExternalLink className="inline ml-1 h-3 w-3" /></Link>
            <Badge data-testid={`review-confidence-${candidate.id}`} variant="outline" className="border-amber-200 bg-amber-50 text-amber-800">{Math.round((candidate.confidence_score || 0) * 100)}% confianza IA</Badge>
          </div>
          <p data-testid={`review-title-${candidate.id}`} className="mt-1 text-sm text-slate-500 break-words">{[candidate.current_title, candidate.current_company].filter(Boolean).join(' · ') || 'Sin puesto extraído'}</p>
        </div>
      </div>
      <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-5">
        {fields.map(([field, label, options]) => <ReviewField key={field} candidateId={candidate.id} field={field} label={label} value={values[field]} options={options} disabled={saving || busy || !canEdit || (field === 'presentation_subarea' && !values.presentation_area)} onChange={save} />)}
      </div>
      {candidate.review_status === 'manual_capture' && <p data-testid={`review-manual-capture-${candidate.id}`} role="alert" className="mt-3 text-sm font-medium text-amber-800">Requiere captura manual. {candidate.review_message}</p>}
      {candidate.review_status !== 'manual_capture' && candidate.review_message && <p data-testid={`review-inference-message-${candidate.id}`} className="mt-3 text-xs text-amber-800">{candidate.review_message}</p>}
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <span data-testid={`review-save-status-${candidate.id}`} role="status" className="text-xs text-slate-500">{saving && <Loader2 className="mr-1 inline h-3 w-3 animate-spin" />}{message || (candidate.manually_edited ? 'Ajustado manualmente · pendiente de aprobación' : 'Pendiente de aprobación')}</span>
        {canManage && <div className="flex flex-wrap gap-2">
          <Button data-testid={`review-again-${candidate.id}`} variant="outline" size="sm" disabled={busy || saving} onClick={() => onRecheck(candidate.id)}><RefreshCw className="mr-1 h-4 w-4" />Revisar de nuevo</Button>
          <Button data-testid={`approve-${candidate.id}`} size="sm" disabled={busy || saving || !valid} title={!valid ? 'Completa los tres campos de clasificación con valores válidos' : 'Aprobar clasificación'} onClick={() => onApprove(candidate.id)} className="bg-green-700 hover:bg-green-800"><Check className="mr-1 h-4 w-4" />Aprobar</Button>
        </div>}
      </div>
      {error && <p data-testid={`review-save-error-${candidate.id}`} role="alert" className="mt-3 text-sm text-red-700">{typeof error === 'string' ? error : 'Valor no válido; el cambio no fue guardado.'}</p>}
    </article>
  );
};