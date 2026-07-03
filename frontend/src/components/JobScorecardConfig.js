import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Input } from './ui/input';
import { Label } from './ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from './ui/select';
import { Loader2, Plus, X, Save, SlidersHorizontal } from 'lucide-react';
import { toast } from 'sonner';
import { jobsAPI } from '../api';

const PROCESS_OPTIONS = [
  { value: 'c_level', label: 'C-Level / Dirección General' },
  { value: 'executive', label: 'Ejecutivo / Director' },
  { value: 'managerial', label: 'Gerencial' },
  { value: 'operational', label: 'Operativo' },
];

const CALIBER_OPTIONS = [
  { value: 'none', label: 'Sin preferencia' },
  { value: 'multinacional_global', label: 'Multinacional Global' },
  { value: 'corporativo_nacional', label: 'Corporativo Nacional' },
  { value: 'mediana', label: 'Empresa Mediana' },
  { value: 'pyme', label: 'PyME' },
  { value: 'startup', label: 'Startup' },
];

const KNOCKOUT_TYPES = [
  { value: 'language', label: 'Idioma' },
  { value: 'location', label: 'Ubicación' },
  { value: 'experience_min', label: 'Experiencia mínima' },
  { value: 'salary', label: 'Salario' },
  { value: 'certification', label: 'Certificación' },
  { value: 'custom', label: 'Otro' },
];

const SEVERITY_OPTIONS = [
  { value: 'fatal', label: 'Fatal' },
  { value: 'important', label: 'Importante' },
];

const JobScorecardConfig = ({ jobId }) => {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [baseScorecard, setBaseScorecard] = useState({});
  const [source, setSource] = useState(null);
  const [processType, setProcessType] = useState('managerial');
  const [targetCaliber, setTargetCaliber] = useState('none');
  const [languages, setLanguages] = useState([]);
  const [languageInput, setLanguageInput] = useState('');
  const [nonNegotiables, setNonNegotiables] = useState([]);

  const loadScorecard = useCallback(async () => {
    setLoading(true);
    try {
      const response = await jobsAPI.getScorecard(jobId);
      const sc = response.data.scorecard || {};
      setBaseScorecard(sc);
      setSource(response.data.source);
      setProcessType(sc.process_type || 'managerial');
      setTargetCaliber(sc.target_company_caliber || 'none');
      setLanguages(sc.required_languages || []);
      setNonNegotiables(sc.non_negotiables || []);
    } catch (error) {
      console.error('Error loading scorecard:', error);
      toast.error('Error al cargar la configuración de matching');
    } finally {
      setLoading(false);
    }
  }, [jobId]);

  useEffect(() => {
    loadScorecard();
  }, [loadScorecard]);

  const addLanguage = () => {
    const value = languageInput.trim();
    if (!value) return;
    if (languages.includes(value)) {
      toast.error('Ese idioma ya está agregado');
      return;
    }
    setLanguages([...languages, value]);
    setLanguageInput('');
  };

  const removeLanguage = (lang) => {
    setLanguages(languages.filter((l) => l !== lang));
  };

  const addKnockoutRow = () => {
    setNonNegotiables([
      ...nonNegotiables,
      { criterion: '', type: 'custom', severity: 'important', expected_value: null },
    ]);
  };

  const updateKnockoutRow = (index, field, value) => {
    const updated = [...nonNegotiables];
    updated[index] = { ...updated[index], [field]: value };
    setNonNegotiables(updated);
  };

  const removeKnockoutRow = (index) => {
    setNonNegotiables(nonNegotiables.filter((_, i) => i !== index));
  };

  const handleSave = async () => {
    const emptyCriterion = nonNegotiables.some((k) => !String(k.criterion || '').trim());
    if (emptyCriterion) {
      toast.error('Hay requisitos no negociables sin criterio. Complétalos o elimínalos.');
      return;
    }
    setSaving(true);
    try {
      const payload = {
        ...baseScorecard,
        process_type: processType,
        target_company_caliber: targetCaliber === 'none' ? null : targetCaliber,
        required_languages: languages,
        non_negotiables: nonNegotiables,
      };
      const response = await jobsAPI.saveScorecard(jobId, payload);
      setBaseScorecard(response.data.scorecard || payload);
      setSource('saved');
      toast.success('Configuración de matching guardada');
    } catch (error) {
      console.error('Error saving scorecard:', error);
      toast.error(error.response?.data?.detail || 'Error al guardar la configuración de matching');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card data-testid="scorecard-config-card">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <SlidersHorizontal className="w-5 h-5" />
          Configuración de Matching (v3)
        </CardTitle>
        <CardDescription>
          Define el scorecard que usa el motor de scoring v3 para esta vacante
          {source === 'derived' && ' — mostrando valores derivados (aún no guardados)'}
        </CardDescription>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="flex items-center justify-center py-6">
            <Loader2 className="w-5 h-5 animate-spin text-blue-600" />
            <span className="ml-2 text-slate-600 text-sm">Cargando configuración...</span>
          </div>
        ) : (
          <div className="space-y-5">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <Label className="text-sm">Tipo de proceso</Label>
                <Select value={processType} onValueChange={setProcessType}>
                  <SelectTrigger className="mt-1" data-testid="scorecard-process-type-select">
                    <SelectValue placeholder="Selecciona tipo de proceso" />
                  </SelectTrigger>
                  <SelectContent>
                    {PROCESS_OPTIONS.map((opt) => (
                      <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-sm">Calibre de empresa objetivo</Label>
                <Select value={targetCaliber} onValueChange={setTargetCaliber}>
                  <SelectTrigger className="mt-1" data-testid="scorecard-caliber-select">
                    <SelectValue placeholder="Selecciona calibre objetivo" />
                  </SelectTrigger>
                  <SelectContent>
                    {CALIBER_OPTIONS.map((opt) => (
                      <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div>
              <Label className="text-sm">Idiomas requeridos</Label>
              <div className="flex gap-2 mt-1">
                <Input
                  value={languageInput}
                  onChange={(e) => setLanguageInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      addLanguage();
                    }
                  }}
                  placeholder='Ej: english:advanced'
                  data-testid="scorecard-language-input"
                />
                <Button type="button" variant="outline" onClick={addLanguage} data-testid="scorecard-add-language-btn">
                  <Plus className="w-4 h-4" />
                </Button>
              </div>
              {languages.length > 0 && (
                <div className="flex flex-wrap gap-2 mt-2">
                  {languages.map((lang) => (
                    <Badge key={lang} variant="secondary" className="pr-1" data-testid="scorecard-language-tag">
                      {lang}
                      <button
                        type="button"
                        onClick={() => removeLanguage(lang)}
                        className="ml-1 rounded-full hover:bg-slate-300 p-0.5"
                        data-testid="scorecard-remove-language-btn"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    </Badge>
                  ))}
                </div>
              )}
            </div>

            <div>
              <div className="flex items-center justify-between">
                <Label className="text-sm">Requisitos no negociables</Label>
                <Button type="button" variant="outline" size="sm" onClick={addKnockoutRow} data-testid="scorecard-add-knockout-btn">
                  <Plus className="w-4 h-4 mr-1" />
                  Agregar
                </Button>
              </div>
              {nonNegotiables.length === 0 ? (
                <p className="text-xs text-slate-500 mt-2">Sin requisitos no negociables definidos</p>
              ) : (
                <div className="space-y-2 mt-2">
                  {nonNegotiables.map((ko, index) => (
                    <div key={index} className="flex flex-col md:flex-row gap-2 items-stretch md:items-center" data-testid="scorecard-knockout-row">
                      <Input
                        value={ko.criterion || ''}
                        onChange={(e) => updateKnockoutRow(index, 'criterion', e.target.value)}
                        placeholder="Criterio (ej: Inglés avanzado indispensable)"
                        className="flex-1"
                        data-testid="scorecard-knockout-criterion-input"
                      />
                      <Select value={ko.type || 'custom'} onValueChange={(v) => updateKnockoutRow(index, 'type', v)}>
                        <SelectTrigger className="md:w-44" data-testid="scorecard-knockout-type-select">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {KNOCKOUT_TYPES.map((opt) => (
                            <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <Select value={ko.severity || 'important'} onValueChange={(v) => updateKnockoutRow(index, 'severity', v)}>
                        <SelectTrigger className="md:w-36" data-testid="scorecard-knockout-severity-select">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {SEVERITY_OPTIONS.map((opt) => (
                            <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => removeKnockoutRow(index)}
                        className="text-red-600 hover:text-red-700 hover:bg-red-50"
                        data-testid="scorecard-remove-knockout-btn"
                      >
                        <X className="w-4 h-4" />
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="flex justify-end border-t pt-4">
              <Button onClick={handleSave} disabled={saving} data-testid="scorecard-save-btn">
                {saving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Save className="w-4 h-4 mr-2" />}
                Guardar configuración
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default JobScorecardConfig;
