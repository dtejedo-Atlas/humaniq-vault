import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Layout from '../components/Layout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Textarea } from '../components/ui/textarea';
import { Separator } from '../components/ui/separator';
import {
  Mail,
  Phone,
  MapPin,
  Linkedin,
  Building2,
  Briefcase,
  Calendar,
  FileText,
  Sparkles,
  CheckCircle,
  Edit,
  ArrowLeft
} from 'lucide-react';
import { candidatesAPI, atlasAPI } from '../api';
import { useTaxonomy } from '../contexts/TaxonomyContext';
import { toast } from 'sonner';
import { getStatusColor, getStatusLabel, getSeniorityLabel, formatDate, formatDateTime } from '../utils/helpers';

const CandidateDetailPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const { getIndustryName, getFunctionalAreaName } = useTaxonomy();
  const [candidate, setCandidate] = useState(null);
  const [loading, setLoading] = useState(true);
  const [classifying, setClassifying] = useState(false);
  const [newNote, setNewNote] = useState('');
  const [addingNote, setAddingNote] = useState(false);

  useEffect(() => {
    fetchCandidate();
  }, [id]);

  const fetchCandidate = async () => {
    try {
      const response = await candidatesAPI.getById(id);
      setCandidate(response.data);
    } catch (error) {
      console.error('Error fetching candidate:', error);
      toast.error('Error cargando candidato');
    } finally {
      setLoading(false);
    }
  };

  const handleClassify = async () => {
    setClassifying(true);
    try {
      await atlasAPI.classify(id);
      toast.success('Candidato clasificado por Atlas');
      await fetchCandidate();
    } catch (error) {
      console.error('Error classifying:', error);
      toast.error('Error clasificando candidato');
    } finally {
      setClassifying(false);
    }
  };

  const handleApproveClassification = async () => {
    try {
      await atlasAPI.approveClassification(id);
      toast.success('Clasificación aprobada y aplicada');
      await fetchCandidate();
    } catch (error) {
      console.error('Error approving:', error);
      toast.error('Error aprobando clasificación');
    }
  };

  const handleAddNote = async () => {
    if (!newNote.trim()) return;

    setAddingNote(true);
    try {
      await candidatesAPI.addNote(id, newNote);
      toast.success('Nota agregada');
      setNewNote('');
      await fetchCandidate();
    } catch (error) {
      console.error('Error adding note:', error);
      toast.error('Error agregando nota');
    } finally {
      setAddingNote(false);
    }
  };

  if (loading) {
    return (
      <Layout title="Cargando..." subtitle="Cargando información del candidato">
        <div className="flex items-center justify-center h-64">
          <div className="spinner w-8 h-8 border-4 border-slate-300 border-t-cyan-500 rounded-full"></div>
        </div>
      </Layout>
    );
  }

  if (!candidate) {
    return (
      <Layout title="No encontrado" subtitle="Candidato no encontrado">
        <Card>
          <CardContent className="p-12 text-center">
            <p className="text-slate-600 mb-4">El candidato no existe</p>
            <Button onClick={() => navigate('/candidates')}>
              Volver a Candidatos
            </Button>
          </CardContent>
        </Card>
      </Layout>
    );
  }

  return (
    <Layout
      title={candidate.full_name}
      subtitle={candidate.current_title || 'Candidato'}
    >
      <div className="space-y-6">
        {/* Header Actions */}
        <div className="flex items-center justify-between">
          <Button variant="outline" onClick={() => navigate('/candidates')}>
            <ArrowLeft className="w-4 h-4 mr-2" />
            Volver
          </Button>
          <div className="flex gap-2">
            <Button variant="outline" data-testid="edit-candidate-button">
              <Edit className="w-4 h-4 mr-2" />
              Editar
            </Button>
            <Button onClick={handleClassify} disabled={classifying} data-testid="classify-button">
              <Sparkles className="w-4 h-4 mr-2" />
              {classifying ? 'Clasificando...' : 'Clasificar con Atlas'}
            </Button>
          </div>
        </div>

        {/* Main Info Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column - Main Info */}
          <div className="lg:col-span-2 space-y-6">
            {/* Basic Info */}
            <Card>
              <CardHeader>
                <div className="flex items-start justify-between">
                  <div>
                    <CardTitle className="text-2xl">{candidate.full_name}</CardTitle>
                    {candidate.current_title && (
                      <CardDescription className="text-base mt-2">
                        {candidate.current_title}
                        {candidate.current_company && ` @ ${candidate.current_company}`}
                      </CardDescription>
                    )}
                  </div>
                  <Badge className={getStatusColor(candidate.status)}>
                    {getStatusLabel(candidate.status)}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Contact Info */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {candidate.email && (
                    <div className="flex items-center gap-2 text-sm">
                      <Mail className="w-4 h-4 text-slate-400" />
                      <a href={`mailto:${candidate.email}`} className="text-cyan-600 hover:underline">
                        {candidate.email}
                      </a>
                    </div>
                  )}
                  {candidate.phone && (
                    <div className="flex items-center gap-2 text-sm">
                      <Phone className="w-4 h-4 text-slate-400" />
                      <span>{candidate.phone}</span>
                    </div>
                  )}
                  {candidate.city && (
                    <div className="flex items-center gap-2 text-sm">
                      <MapPin className="w-4 h-4 text-slate-400" />
                      <span>
                        {candidate.city}
                        {candidate.state && `, ${candidate.state}`}
                        {candidate.country && `, ${candidate.country}`}
                      </span>
                    </div>
                  )}
                  {candidate.linkedin_url && (
                    <div className="flex items-center gap-2 text-sm">
                      <Linkedin className="w-4 h-4 text-slate-400" />
                      <a
                        href={candidate.linkedin_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-cyan-600 hover:underline"
                      >
                        Ver LinkedIn
                      </a>
                    </div>
                  )}
                </div>

                <Separator />

                {/* Professional Info */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  {candidate.years_experience && (
                    <div>
                      <p className="text-xs text-slate-500 mb-1">Experiencia</p>
                      <p className="text-sm font-medium">{candidate.years_experience} años</p>
                    </div>
                  )}
                  {candidate.industry && (
                    <div>
                      <p className="text-xs text-slate-500 mb-1">Industria</p>
                      <p className="text-sm font-medium">{getIndustryName(candidate.industry)}</p>
                    </div>
                  )}
                  {candidate.functional_area && (
                    <div>
                      <p className="text-xs text-slate-500 mb-1">Área Funcional</p>
                      <p className="text-sm font-medium">{getFunctionalAreaName(candidate.functional_area)}</p>
                    </div>
                  )}
                  {candidate.seniority && (
                    <div>
                      <p className="text-xs text-slate-500 mb-1">Seniority</p>
                      <p className="text-sm font-medium">{getSeniorityLabel(candidate.seniority)}</p>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>

            {/* AI Summary */}
            {candidate.ai_summary && (
              <Card className="border-cyan-200 bg-cyan-50/50">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-cyan-900">
                    <Sparkles className="w-5 h-5 text-cyan-500" />
                    Resumen de Atlas IA
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-slate-700 leading-relaxed">{candidate.ai_summary}</p>
                </CardContent>
              </Card>
            )}

            {/* AI Classification */}
            {candidate.ai_classification && (
              <Card className="border-cyan-200">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="flex items-center gap-2">
                      <Sparkles className="w-5 h-5 text-cyan-500" />
                      Clasificación de Atlas
                    </CardTitle>
                    {!candidate.ai_classification.approved_by_recruiter && (
                      <Button
                        size="sm"
                        onClick={handleApproveClassification}
                        data-testid="approve-classification-button"
                      >
                        <CheckCircle className="w-4 h-4 mr-2" />
                        Aprobar y Aplicar
                      </Button>
                    )}
                  </div>
                  <CardDescription>
                    Confianza: {Math.round(candidate.ai_classification.confidence_score * 100)}%
                    {candidate.ai_classification.approved_by_recruiter && (
                      <Badge variant="outline" className="ml-2 bg-green-50 text-green-700 border-green-200">
                        Aprobado
                      </Badge>
                    )}
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="grid grid-cols-3 gap-4">
                    <div>
                      <p className="text-xs text-slate-500 mb-1">Industria</p>
                      <Badge variant="outline">{candidate.ai_classification.industry ? getIndustryName(candidate.ai_classification.industry) : 'N/A'}</Badge>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500 mb-1">Área Funcional</p>
                      <Badge variant="outline">{candidate.ai_classification.functional_area ? getFunctionalAreaName(candidate.ai_classification.functional_area) : 'N/A'}</Badge>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500 mb-1">Seniority</p>
                      <Badge variant="outline">
                        {candidate.ai_classification.seniority
                          ? getSeniorityLabel(candidate.ai_classification.seniority)
                          : 'N/A'}
                      </Badge>
                    </div>
                  </div>
                  {candidate.ai_classification.suggested_tags && candidate.ai_classification.suggested_tags.length > 0 && (
                    <div>
                      <p className="text-xs text-slate-500 mb-2">Tags Sugeridos</p>
                      <div className="flex flex-wrap gap-2">
                        {candidate.ai_classification.suggested_tags.map((tag, index) => (
                          <Badge key={index} variant="secondary" className="text-xs">
                            {tag}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            )}

            {/* Skills & Languages */}
            {(candidate.skills?.length > 0 || candidate.languages?.length > 0) && (
              <Card>
                <CardHeader>
                  <CardTitle>Habilidades e Idiomas</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {candidate.skills?.length > 0 && (
                    <div>
                      <p className="text-sm font-medium text-slate-700 mb-2">Habilidades</p>
                      <div className="flex flex-wrap gap-2">
                        {candidate.skills.map((skill, index) => (
                          <Badge key={index} variant="outline">
                            {skill}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                  {candidate.languages?.length > 0 && (
                    <div>
                      <p className="text-sm font-medium text-slate-700 mb-2">Idiomas</p>
                      <div className="flex flex-wrap gap-2">
                        {candidate.languages.map((lang, index) => (
                          <Badge key={index} variant="secondary">
                            {lang}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            )}

            {/* Work History */}
            {candidate.previous_companies?.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle>Experiencia Laboral</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    {candidate.previous_companies.map((company, index) => (
                      <div key={index} className="border-l-2 border-cyan-500 pl-4">
                        <h4 className="font-semibold text-slate-900">{company.title}</h4>
                        <p className="text-sm text-slate-600">{company.company_name}</p>
                        {(company.start_date || company.end_date) && (
                          <p className="text-xs text-slate-500 mt-1">
                            {company.start_date || 'N/A'} - {company.end_date || 'Presente'}
                          </p>
                        )}
                        {company.description && (
                          <p className="text-sm text-slate-700 mt-2">{company.description}</p>
                        )}
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}
          </div>

          {/* Right Column - Side Info */}
          <div className="space-y-6">
            {/* Resume Files */}
            {candidate.resume_files?.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Currículums</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    {candidate.resume_files.map((file, index) => (
                      <div
                        key={index}
                        className="flex items-center gap-2 p-3 bg-slate-50 rounded-sm"
                      >
                        <FileText className="w-4 h-4 text-slate-400" />
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-slate-900 truncate">
                            {file.file_name}
                          </p>
                          <p className="text-xs text-slate-500">
                            {formatDate(file.upload_date)}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Metadata */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Información del Sistema</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <div>
                  <p className="text-xs text-slate-500 mb-1">Fuente</p>
                  <p className="font-medium">{candidate.source || 'N/A'}</p>
                </div>
                <div>
                  <p className="text-xs text-slate-500 mb-1">Fecha de Creación</p>
                  <p className="font-medium">{formatDateTime(candidate.created_at)}</p>
                </div>
                <div>
                  <p className="text-xs text-slate-500 mb-1">Última Actualización</p>
                  <p className="font-medium">{formatDateTime(candidate.updated_at)}</p>
                </div>
              </CardContent>
            </Card>

            {/* Notes Section */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Notas del Reclutador</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <Textarea
                    placeholder="Agregar una nota..."
                    data-testid="note-textarea"
                    value={newNote}
                    onChange={(e) => setNewNote(e.target.value)}
                    rows={3}
                  />
                  <Button
                    className="mt-2 w-full"
                    size="sm"
                    onClick={handleAddNote}
                    disabled={addingNote || !newNote.trim()}
                    data-testid="add-note-button"
                  >
                    {addingNote ? 'Guardando...' : 'Agregar Nota'}
                  </Button>
                </div>

                {candidate.notes?.length > 0 && (
                  <div className="space-y-3 mt-4">
                    {candidate.notes.map((note, index) => (
                      <div key={index} className="p-3 bg-slate-50 rounded-sm">
                        <p className="text-sm text-slate-700">{note.note}</p>
                        <p className="text-xs text-slate-500 mt-2">
                          {note.created_by} - {formatDateTime(note.created_at)}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </Layout>
  );
};

export default CandidateDetailPage;
