import React, { useState, useEffect, useRef } from 'react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '../components/ui/tooltip';
import { Badge } from '../components/ui/badge';
import { Alert, AlertDescription } from '../components/ui/alert';
import { 
  ChevronLeft, 
  ChevronRight, 
  Check, 
  HelpCircle, 
  Briefcase, 
  Building2, 
  MapPin, 
  DollarSign,
  Home,
  Building,
  Loader2,
  Eye,
  Upload,
  FileText,
  Sparkles,
  AlertCircle,
  CheckCircle2
} from 'lucide-react';
import { useTaxonomy } from '../contexts/TaxonomyContext';
import { jobsAPI } from '../api';
import { toast } from 'sonner';
import { 
  MEXICO_STATES, 
  COUNTRIES, 
  WORK_SCHEMES, 
  SENIORITY_OPTIONS,
  getStateLabel,
  getWorkSchemeLabel,
  getSeniorityLabel
} from '../constants/mexicoStates';

const STEPS = [
  { id: 1, title: 'Información Básica', icon: Briefcase },
  { id: 2, title: 'Contexto y Responsabilidades', icon: Building2 },
  { id: 3, title: 'Requisitos y Ubicación', icon: MapPin },
  { id: 4, title: 'Preview', icon: Eye },
];

const initialFormData = {
  // Paso 1
  title: '',
  company: '',
  industry: '',
  functional_area: '',
  seniority: 'manager',
  min_experience: 5,
  max_experience: '',
  // Paso 2
  job_objective: '',
  role_context: '',
  responsibilities: '',
  // Paso 3
  required_experience: '',
  non_negotiables: '',
  location_country: 'México',
  location_state: '',
  location_city: '',
  salary_min: '',
  salary_max: '',
  work_scheme: 'on_site',
  schedule: '',
};

const FieldTooltip = ({ content }) => (
  <TooltipProvider>
    <Tooltip>
      <TooltipTrigger asChild>
        <HelpCircle className="w-4 h-4 text-slate-400 cursor-help ml-1" />
      </TooltipTrigger>
      <TooltipContent className="max-w-xs">
        <p className="text-sm">{content}</p>
      </TooltipContent>
    </Tooltip>
  </TooltipProvider>
);

const JobFormWizard = ({ onSubmit, onCancel, initialData = null, loading = false }) => {
  const [currentStep, setCurrentStep] = useState(1);
  const [formData, setFormData] = useState(initialData || initialFormData);
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState(null);
  const fileInputRef = useRef(null);
  const { getIndustryOptions, getFunctionalAreaOptions, getIndustryName, getFunctionalAreaName } = useTaxonomy();

  const industries = getIndustryOptions();
  const functionalAreas = getFunctionalAreaOptions();

  const updateField = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const handleFileUpload = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    // Validar extensión
    const ext = file.name.split('.').pop()?.toLowerCase();
    if (!['pdf', 'docx'].includes(ext)) {
      toast.error('Solo se permiten archivos PDF o DOCX');
      return;
    }

    // Validar tamaño (10MB)
    if (file.size > 10 * 1024 * 1024) {
      toast.error('El archivo excede el límite de 10MB');
      return;
    }

    setUploading(true);
    setUploadResult(null);

    try {
      const response = await jobsAPI.parseJD(file);
      const { data } = response.data;

      // Validar industria y área funcional contra la taxonomía ANTES de setearlas
      const validIndustryKeys = new Set(industries.map(i => i.value));
      const validAreaKeys = new Set(functionalAreas.map(a => a.value));
      const parsedIndustry = data.industry && (industries.length === 0 || validIndustryKeys.has(data.industry)) ? data.industry : '';
      const parsedArea = data.functional_area && (functionalAreas.length === 0 || validAreaKeys.has(data.functional_area)) ? data.functional_area : '';
      const discarded = [];
      if (data.industry && !parsedIndustry) discarded.push(`industria "${data.industry}"`);
      if (data.functional_area && !parsedArea) discarded.push(`área funcional "${data.functional_area}"`);

      // Pre-llenar el formulario con los datos extraídos
      setFormData(prev => ({
        ...prev,
        title: data.title || prev.title,
        company: data.company || prev.company,
        industry: parsedIndustry || prev.industry,
        functional_area: parsedArea || prev.functional_area,
        seniority: data.seniority || prev.seniority,
        min_experience: data.min_experience ?? prev.min_experience,
        max_experience: data.max_experience ?? prev.max_experience,
        job_objective: data.job_objective || prev.job_objective,
        role_context: data.role_context || prev.role_context,
        responsibilities: data.responsibilities || prev.responsibilities,
        required_experience: data.required_experience || prev.required_experience,
        non_negotiables: data.non_negotiables || prev.non_negotiables,
        location_country: data.location_country || prev.location_country,
        location_state: data.location_state || prev.location_state,
        location_city: data.location_city || prev.location_city,
        salary_min: data.salary_min ?? prev.salary_min,
        salary_max: data.salary_max ?? prev.salary_max,
        work_scheme: data.work_scheme || prev.work_scheme,
        schedule: data.schedule || prev.schedule,
      }));

      setUploadResult({
        success: true,
        confidence: data.confidence_score,
        notes: data.extraction_notes,
        filename: file.name
      });

      toast.success('Documento procesado correctamente. Revisa la información extraída.');
      if (discarded.length > 0) {
        toast.warning(`Valores fuera de la taxonomía: ${discarded.join(', ')}. Selecciónalos manualmente.`);
      }
    } catch (error) {
      console.error('Error uploading JD:', error);
      const errorMsg = error.response?.data?.detail || 'Error procesando el documento';
      toast.error(errorMsg);
      setUploadResult({
        success: false,
        error: errorMsg
      });
    } finally {
      setUploading(false);
      // Reset file input
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const isStep1Valid = () => {
    return formData.title && formData.industry && formData.functional_area;
  };

  const isStep2Valid = () => {
    return formData.job_objective || formData.responsibilities;
  };

  const isStep3Valid = () => {
    return formData.location_country;
  };

  const canProceed = () => {
    switch (currentStep) {
      case 1: return isStep1Valid();
      case 2: return true; // Step 2 is optional
      case 3: return isStep3Valid();
      default: return true;
    }
  };

  const handleNext = () => {
    if (currentStep < 4 && canProceed()) {
      setCurrentStep(prev => prev + 1);
    }
  };

  const handleBack = () => {
    if (currentStep > 1) {
      setCurrentStep(prev => prev - 1);
    }
  };

  const handleSubmit = () => {
    const jobData = {
      ...formData,
      min_experience: parseInt(formData.min_experience) || 0,
      max_experience: formData.max_experience ? parseInt(formData.max_experience) : null,
      salary_min: formData.salary_min ? parseInt(formData.salary_min) : null,
      salary_max: formData.salary_max ? parseInt(formData.salary_max) : null,
    };
    onSubmit(jobData);
  };

  // Upload Section Component
  const renderUploadSection = () => (
    <div className="mb-6 p-4 border-2 border-dashed border-slate-200 rounded-lg bg-slate-50 hover:bg-slate-100 transition-colors">
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.docx"
        onChange={handleFileUpload}
        className="hidden"
        id="jd-upload"
      />
      
      <div className="text-center">
        {uploading ? (
          <div className="py-4">
            <Loader2 className="w-8 h-8 animate-spin text-cyan-600 mx-auto mb-2" />
            <p className="text-sm text-slate-600">Procesando documento con IA...</p>
            <p className="text-xs text-slate-400 mt-1">Esto puede tomar unos segundos</p>
          </div>
        ) : (
          <>
            <div className="flex items-center justify-center gap-2 mb-2">
              <Sparkles className="w-5 h-5 text-cyan-600" />
              <span className="font-medium text-slate-700">Ingesta Inteligente</span>
            </div>
            <p className="text-sm text-slate-500 mb-3">
              Sube un PDF o Word con la descripción de la vacante y extraeremos la información automáticamente
            </p>
            <Button
              type="button"
              variant="outline"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              className="gap-2"
            >
              <Upload className="w-4 h-4" />
              Cargar Job Description
            </Button>
            <p className="text-xs text-slate-400 mt-2">PDF o DOCX, máximo 10MB</p>
          </>
        )}
      </div>

      {uploadResult && (
        <div className="mt-4">
          {uploadResult.success ? (
            <Alert className="bg-green-50 border-green-200">
              <CheckCircle2 className="w-4 h-4 text-green-600" />
              <AlertDescription className="text-green-800">
                <div className="font-medium">Documento procesado: {uploadResult.filename}</div>
                <div className="text-sm mt-1">
                  Confianza: {Math.round((uploadResult.confidence || 0) * 100)}%
                  {uploadResult.notes && (
                    <span className="block text-green-600 mt-1">{uploadResult.notes}</span>
                  )}
                </div>
              </AlertDescription>
            </Alert>
          ) : (
            <Alert className="bg-red-50 border-red-200">
              <AlertCircle className="w-4 h-4 text-red-600" />
              <AlertDescription className="text-red-800">
                {uploadResult.error}
              </AlertDescription>
            </Alert>
          )}
        </div>
      )}
    </div>
  );

  // Step 1: Información Básica
  const renderStep1 = () => (
    <div className="space-y-5">
      {/* Upload Section */}
      {renderUploadSection()}

      <div className="relative">
        <div className="absolute inset-0 flex items-center">
          <span className="w-full border-t" />
        </div>
        <div className="relative flex justify-center text-xs uppercase">
          <span className="bg-white px-2 text-slate-500">o completa manualmente</span>
        </div>
      </div>

      {/* Título y Empresa */}
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label className="flex items-center">
            Título del Puesto <span className="text-red-500 ml-1">*</span>
            <FieldTooltip content="Nombre del puesto tal como aparecerá en las búsquedas. Ej: Gerente de Operaciones, Director Comercial" />
          </Label>
          <Input
            placeholder="Ej: Gerente de Operaciones"
            value={formData.title}
            onChange={(e) => updateField('title', e.target.value)}
            data-testid="job-title-input"
          />
        </div>
        <div className="space-y-2">
          <Label className="flex items-center">
            Empresa
            <FieldTooltip content="Nombre de la empresa cliente. Opcional si es confidencial." />
          </Label>
          <Input
            placeholder="Nombre de la empresa (opcional)"
            value={formData.company}
            onChange={(e) => updateField('company', e.target.value)}
          />
        </div>
      </div>

      {/* Área Funcional e Industria */}
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label className="flex items-center">
            Área Funcional <span className="text-red-500 ml-1">*</span>
            <FieldTooltip content="El área de expertise principal del puesto: Finanzas, Operaciones, Comercial, etc." />
          </Label>
          <Select
            value={formData.functional_area}
            onValueChange={(v) => updateField('functional_area', v)}
          >
            <SelectTrigger data-testid="job-area-select">
              <SelectValue placeholder="Seleccionar área" />
            </SelectTrigger>
            <SelectContent>
              {functionalAreas.map(area => (
                <SelectItem key={area.value} value={area.value}>
                  {area.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <Label className="flex items-center">
            Industria <span className="text-red-500 ml-1">*</span>
            <FieldTooltip content="Sector de la empresa: Manufactura, Retail, Fintech, etc." />
          </Label>
          <Select
            value={formData.industry}
            onValueChange={(v) => updateField('industry', v)}
          >
            <SelectTrigger data-testid="job-industry-select">
              <SelectValue placeholder="Seleccionar industria" />
            </SelectTrigger>
            <SelectContent>
              {industries.map(ind => (
                <SelectItem key={ind.value} value={ind.value}>
                  {ind.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Seniority y Experiencia */}
      <div className="grid grid-cols-3 gap-4">
        <div className="space-y-2">
          <Label className="flex items-center">
            Nivel de Seniority
            <FieldTooltip content="Nivel jerárquico esperado del candidato" />
          </Label>
          <Select
            value={formData.seniority}
            onValueChange={(v) => updateField('seniority', v)}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {SENIORITY_OPTIONS.map(opt => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <Label className="flex items-center">
            Experiencia Mínima (años)
            <FieldTooltip content="Años mínimos de experiencia requeridos" />
          </Label>
          <Input
            type="number"
            min="0"
            value={formData.min_experience}
            onChange={(e) => updateField('min_experience', e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label className="flex items-center">
            Experiencia Máxima (años)
            <FieldTooltip content="Años máximos deseables. Dejar vacío si no hay límite." />
          </Label>
          <Input
            type="number"
            min="0"
            placeholder="Sin límite"
            value={formData.max_experience}
            onChange={(e) => updateField('max_experience', e.target.value)}
          />
        </div>
      </div>
    </div>
  );

  // Step 2: Contexto y Responsabilidades
  const renderStep2 = () => (
    <div className="space-y-5">
      <div className="space-y-2">
        <Label className="flex items-center">
          Objetivo del Puesto
          <FieldTooltip content="¿Cuál es el objetivo principal de esta posición? ¿Qué se espera lograr?" />
        </Label>
        <Textarea
          placeholder="Ej: Liderar la operación de manufactura de la planta Guadalajara, asegurando el cumplimiento de metas de producción, calidad y seguridad..."
          value={formData.job_objective}
          onChange={(e) => updateField('job_objective', e.target.value)}
          className="min-h-[100px]"
        />
      </div>

      <div className="space-y-2">
        <Label className="flex items-center">
          Contexto del Rol
          <FieldTooltip content="Información relevante sobre la empresa, el equipo, la industria o el momento de la organización." />
        </Label>
        <Textarea
          placeholder="Ej: Empresa multinacional de consumo masivo con operaciones en 5 países. El equipo reporta directamente al VP de Operaciones LATAM..."
          value={formData.role_context}
          onChange={(e) => updateField('role_context', e.target.value)}
          className="min-h-[80px]"
        />
      </div>

      <div className="space-y-2">
        <Label className="flex items-center">
          Responsabilidades Principales
          <FieldTooltip content="Lista las principales responsabilidades del puesto, una por línea." />
        </Label>
        <Textarea
          placeholder="• Supervisar el equipo de producción (50+ personas)&#10;• Gestionar presupuesto operativo&#10;• Implementar mejoras de eficiencia&#10;• Reportar KPIs semanales a dirección"
          value={formData.responsibilities}
          onChange={(e) => updateField('responsibilities', e.target.value)}
          className="min-h-[120px]"
        />
      </div>
    </div>
  );

  // Step 3: Requisitos, Ubicación y Salario
  const renderStep3 = () => (
    <div className="space-y-5">
      {/* Requisitos */}
      <div className="space-y-2">
        <Label className="flex items-center">
          Experiencia Requerida
          <FieldTooltip content="Describe la experiencia profesional que debe tener el candidato." />
        </Label>
        <Textarea
          placeholder="Ej: 8+ años en posiciones de liderazgo en manufactura, preferentemente en industria de consumo masivo o automotriz..."
          value={formData.required_experience}
          onChange={(e) => updateField('required_experience', e.target.value)}
          className="min-h-[80px]"
        />
      </div>

      <div className="space-y-2">
        <Label className="flex items-center">
          Requisitos No Negociables
          <FieldTooltip content="Requisitos indispensables que el candidato DEBE cumplir. Sin estos, no debe considerarse." />
        </Label>
        <Textarea
          placeholder="• Inglés avanzado (negociación con corporativo)&#10;• Experiencia en plantas de más de 200 empleados&#10;• Disponibilidad para radicar en Guadalajara"
          value={formData.non_negotiables}
          onChange={(e) => updateField('non_negotiables', e.target.value)}
          className="min-h-[80px]"
        />
      </div>

      {/* Ubicación */}
      <div className="border-t pt-4">
        <h4 className="text-sm font-medium text-slate-700 mb-3 flex items-center">
          <MapPin className="w-4 h-4 mr-2" /> Ubicación
        </h4>
        <div className="grid grid-cols-3 gap-4">
          <div className="space-y-2">
            <Label>País</Label>
            <Select
              value={formData.location_country}
              onValueChange={(v) => {
                updateField('location_country', v);
                if (v !== 'México') updateField('location_state', '');
              }}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {COUNTRIES.map(c => (
                  <SelectItem key={c.value} value={c.value}>{c.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>Estado / Región</Label>
            {formData.location_country === 'México' ? (
              <Select
                value={formData.location_state}
                onValueChange={(v) => updateField('location_state', v)}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Seleccionar estado" />
                </SelectTrigger>
                <SelectContent>
                  {MEXICO_STATES.map(s => (
                    <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            ) : (
              <Input
                placeholder="Estado / Provincia"
                value={formData.location_state}
                onChange={(e) => updateField('location_state', e.target.value)}
              />
            )}
          </div>
          <div className="space-y-2">
            <Label>Ciudad</Label>
            <Input
              placeholder="Ciudad"
              value={formData.location_city}
              onChange={(e) => updateField('location_city', e.target.value)}
            />
          </div>
        </div>
      </div>

      {/* Esquema Laboral */}
      <div className="border-t pt-4">
        <h4 className="text-sm font-medium text-slate-700 mb-3 flex items-center">
          <Building2 className="w-4 h-4 mr-2" /> Esquema Laboral
        </h4>
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label>Modalidad de Trabajo</Label>
            <div className="flex gap-2">
              {WORK_SCHEMES.map(ws => {
                const Icon = ws.value === 'remote' ? Home : ws.value === 'hybrid' ? Building : Building2;
                return (
                  <Button
                    key={ws.value}
                    type="button"
                    variant={formData.work_scheme === ws.value ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => updateField('work_scheme', ws.value)}
                    className="flex-1"
                  >
                    <Icon className="w-4 h-4 mr-1" />
                    {ws.label}
                  </Button>
                );
              })}
            </div>
          </div>
          <div className="space-y-2">
            <Label className="flex items-center">
              Jornada / Horario
              <FieldTooltip content="Ej: Lunes a Viernes 9-6, horario flexible, etc." />
            </Label>
            <Input
              placeholder="Ej: L-V 9:00 - 18:00"
              value={formData.schedule}
              onChange={(e) => updateField('schedule', e.target.value)}
            />
          </div>
        </div>
      </div>

      {/* Salario */}
      <div className="border-t pt-4">
        <h4 className="text-sm font-medium text-slate-700 mb-3 flex items-center">
          <DollarSign className="w-4 h-4 mr-2" /> Compensación
        </h4>
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label>Salario Mínimo (MXN mensual bruto)</Label>
            <Input
              type="number"
              min="0"
              step="1000"
              placeholder="Ej: 80000"
              value={formData.salary_min}
              onChange={(e) => updateField('salary_min', e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label>Salario Máximo (MXN mensual bruto)</Label>
            <Input
              type="number"
              min="0"
              step="1000"
              placeholder="Ej: 120000"
              value={formData.salary_max}
              onChange={(e) => updateField('salary_max', e.target.value)}
            />
          </div>
        </div>
      </div>
    </div>
  );

  // Step 4: Preview
  const renderStep4 = () => {
    const formatSalary = (min, max) => {
      if (!min && !max) return 'No especificado';
      const formatter = new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN', maximumFractionDigits: 0 });
      if (min && max) return `${formatter.format(min)} - ${formatter.format(max)}`;
      if (min) return `Desde ${formatter.format(min)}`;
      return `Hasta ${formatter.format(max)}`;
    };

    const formatLocation = () => {
      const parts = [];
      if (formData.location_city) parts.push(formData.location_city);
      if (formData.location_state) {
        const stateLabel = formData.location_country === 'México' 
          ? getStateLabel(formData.location_state) 
          : formData.location_state;
        parts.push(stateLabel);
      }
      if (formData.location_country) parts.push(formData.location_country);
      return parts.join(', ') || 'No especificada';
    };

    return (
      <div className="space-y-4">
        <div className="bg-slate-50 rounded-lg p-4 border">
          <div className="flex justify-between items-start mb-4">
            <div>
              <h3 className="text-xl font-semibold text-slate-900">{formData.title || 'Sin título'}</h3>
              {formData.company && <p className="text-slate-600">{formData.company}</p>}
            </div>
            <Badge variant="outline" className="text-cyan-700 border-cyan-300 bg-cyan-50">
              {getWorkSchemeLabel(formData.work_scheme)}
            </Badge>
          </div>

          <div className="grid grid-cols-2 gap-4 text-sm mb-4">
            <div>
              <span className="text-slate-500">Área:</span>{' '}
              <span className="font-medium">{getFunctionalAreaName(formData.functional_area) || '-'}</span>
            </div>
            <div>
              <span className="text-slate-500">Industria:</span>{' '}
              <span className="font-medium">{getIndustryName(formData.industry) || '-'}</span>
            </div>
            <div>
              <span className="text-slate-500">Seniority:</span>{' '}
              <span className="font-medium">{getSeniorityLabel(formData.seniority)}</span>
            </div>
            <div>
              <span className="text-slate-500">Experiencia:</span>{' '}
              <span className="font-medium">
                {formData.min_experience || 0}
                {formData.max_experience ? ` - ${formData.max_experience}` : '+'} años
              </span>
            </div>
            <div>
              <span className="text-slate-500">Ubicación:</span>{' '}
              <span className="font-medium">{formatLocation()}</span>
            </div>
            <div>
              <span className="text-slate-500">Salario:</span>{' '}
              <span className="font-medium">{formatSalary(formData.salary_min, formData.salary_max)}</span>
            </div>
          </div>

          {formData.schedule && (
            <div className="text-sm mb-4">
              <span className="text-slate-500">Horario:</span>{' '}
              <span className="font-medium">{formData.schedule}</span>
            </div>
          )}
        </div>

        {formData.job_objective && (
          <div>
            <h4 className="text-sm font-semibold text-slate-700 mb-1">Objetivo del Puesto</h4>
            <p className="text-sm text-slate-600 whitespace-pre-line">{formData.job_objective}</p>
          </div>
        )}

        {formData.role_context && (
          <div>
            <h4 className="text-sm font-semibold text-slate-700 mb-1">Contexto del Rol</h4>
            <p className="text-sm text-slate-600 whitespace-pre-line">{formData.role_context}</p>
          </div>
        )}

        {formData.responsibilities && (
          <div>
            <h4 className="text-sm font-semibold text-slate-700 mb-1">Responsabilidades</h4>
            <p className="text-sm text-slate-600 whitespace-pre-line">{formData.responsibilities}</p>
          </div>
        )}

        {formData.required_experience && (
          <div>
            <h4 className="text-sm font-semibold text-slate-700 mb-1">Experiencia Requerida</h4>
            <p className="text-sm text-slate-600 whitespace-pre-line">{formData.required_experience}</p>
          </div>
        )}

        {formData.non_negotiables && (
          <div>
            <h4 className="text-sm font-semibold text-slate-700 mb-1">Requisitos No Negociables</h4>
            <p className="text-sm text-slate-600 whitespace-pre-line">{formData.non_negotiables}</p>
          </div>
        )}
      </div>
    );
  };

  const renderStepContent = () => {
    switch (currentStep) {
      case 1: return renderStep1();
      case 2: return renderStep2();
      case 3: return renderStep3();
      case 4: return renderStep4();
      default: return null;
    }
  };

  return (
    <div className="space-y-6">
      {/* Progress Steps */}
      <div className="flex items-center justify-between mb-6">
        {STEPS.map((step, index) => {
          const Icon = step.icon;
          const isActive = currentStep === step.id;
          const isCompleted = currentStep > step.id;
          
          return (
            <React.Fragment key={step.id}>
              <div className="flex items-center">
                <div
                  className={`
                    w-10 h-10 rounded-full flex items-center justify-center
                    transition-colors duration-200
                    ${isCompleted ? 'bg-cyan-600 text-white' : ''}
                    ${isActive ? 'bg-cyan-600 text-white ring-4 ring-cyan-100' : ''}
                    ${!isActive && !isCompleted ? 'bg-slate-100 text-slate-400' : ''}
                  `}
                >
                  {isCompleted ? <Check className="w-5 h-5" /> : <Icon className="w-5 h-5" />}
                </div>
                <span className={`ml-2 text-sm font-medium hidden sm:block ${isActive ? 'text-cyan-700' : 'text-slate-500'}`}>
                  {step.title}
                </span>
              </div>
              {index < STEPS.length - 1 && (
                <div className={`flex-1 h-0.5 mx-4 ${currentStep > step.id ? 'bg-cyan-500' : 'bg-slate-200'}`} />
              )}
            </React.Fragment>
          );
        })}
      </div>

      {/* Step Content */}
      <Card>
        <CardHeader>
          <CardTitle>{STEPS[currentStep - 1].title}</CardTitle>
          <CardDescription>
            {currentStep === 1 && 'Carga un documento o completa la información básica del puesto'}
            {currentStep === 2 && 'Describe el objetivo, contexto y responsabilidades'}
            {currentStep === 3 && 'Especifica requisitos, ubicación y compensación'}
            {currentStep === 4 && 'Revisa la información antes de guardar'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {renderStepContent()}
        </CardContent>
      </Card>

      {/* Navigation Buttons */}
      <div className="flex justify-between pt-4">
        <Button
          variant="outline"
          onClick={currentStep === 1 ? onCancel : handleBack}
        >
          <ChevronLeft className="w-4 h-4 mr-1" />
          {currentStep === 1 ? 'Cancelar' : 'Anterior'}
        </Button>

        {currentStep < 4 ? (
          <Button onClick={handleNext} disabled={!canProceed()}>
            Siguiente
            <ChevronRight className="w-4 h-4 ml-1" />
          </Button>
        ) : (
          <Button onClick={handleSubmit} disabled={loading} data-testid="submit-job-button">
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Guardando...
              </>
            ) : (
              <>
                <Check className="w-4 h-4 mr-2" />
                Crear Vacante
              </>
            )}
          </Button>
        )}
      </div>
    </div>
  );
};

export default JobFormWizard;
