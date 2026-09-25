import React, { useRef, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { ReviewField } from './review/ReviewField';
import { reviewAPI } from '../api';
import { useTaxonomy } from '../contexts/TaxonomyContext';

const YEARS = Array.from({ length: 101 }, (_, key) => ({ key, label: `${key} ${key === 1 ? 'año' : 'años'}` }));

export const CandidateClassificationFields = ({ candidate, canEdit, busy, onSaving, onSaved }) => {
  const taxonomy = useTaxonomy();
  const savingRef = useRef(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [permissionDenied, setPermissionDenied] = useState(false);
  const approved = candidate.ai_classification?.approved_by_recruiter === true;
  const disabled = !canEdit || permissionDenied || approved || busy || saving || taxonomy.loading;
  const values = {
    industry: candidate.ai_classification?.industry ?? candidate.industry ?? null,
    presentation_area: candidate.ai_classification?.presentation_area ?? candidate.presentation_area ?? null,
    presentation_subarea: candidate.ai_classification?.presentation_subarea ?? candidate.presentation_subarea ?? null,
    presentation_seniority: candidate.ai_classification?.presentation_seniority ?? candidate.presentation_seniority ?? null,
    years_experience: candidate.ai_classification?.years_experience ?? candidate.years_experience ?? null,
  };
  const fields = [...taxonomy.getClassificationFields(values), ['years_experience', 'Años de experiencia', YEARS]];
  const save = async (field, value) => {
    if (disabled || savingRef.current) return;
    savingRef.current = true;
    setSaving(true); onSaving(true); setError(''); setMessage('Guardando…');
    try {
      const payload = field === 'presentation_area' ? { presentation_area: value, presentation_subarea: null } : { [field]: value };
      const { data } = await reviewAPI.saveField(candidate.id, payload);
      onSaved(candidate.id, data);
      setMessage('Guardado · pendiente de aprobación');
      window.dispatchEvent(new Event('classification-review-updated'));
    } catch (e) {
      setMessage('');
      const detail = e.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'No se guardó el cambio. Inténtalo de nuevo.');
      if ([403, 409].includes(e.response?.status)) setPermissionDenied(true);
    } finally {
      savingRef.current = false;
      setSaving(false); onSaving(false);
    }
  };
  return (
    <div data-testid="candidate-classification-fields" className="min-w-0 space-y-3">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-5">
        {fields.map(([field, label, options]) => (
          <ReviewField key={field} candidateId={candidate.id} field={field} label={label}
            value={values[field]}
            options={options} disabled={disabled || (field === 'presentation_subarea' && !values.presentation_area)} onChange={save} />
        ))}
      </div>
      <p data-testid="candidate-classification-save-status" role="status" className="text-xs text-slate-500">
        {saving && <Loader2 className="mr-1 inline h-3 w-3 animate-spin" />}
        {approved ? 'Clasificación aprobada · solo lectura' : !canEdit ? 'Clasificación en modo solo lectura' : message}
      </p>
      {error && <p data-testid="candidate-classification-save-error" role="alert" className="text-sm text-red-700">{error}</p>}
    </div>
  );
};