import React, { useState, useEffect } from 'react';
import Layout from '../components/Layout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../components/ui/select';
import { Loader2, Sparkles, RotateCcw, Save } from 'lucide-react';
import { toast } from 'sonner';
import { aiAPI } from '../api';

const AdminPage = () => {
  const [config, setConfig] = useState(null);
  const [selection, setSelection] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    aiAPI.getModels()
      .then((res) => {
        setConfig(res.data);
        setSelection(res.data.current);
      })
      .catch((error) => toast.error(error.response?.data?.detail || 'Error cargando la configuración de IA'))
      .finally(() => setLoading(false));
  }, []);

  const dirty = config && Object.keys(selection).some((task) => selection[task] !== config.current[task]);

  const save = async () => {
    setSaving(true);
    try {
      const res = await aiAPI.updateModels(selection);
      setConfig((prev) => ({ ...prev, current: res.data.current }));
      setSelection(res.data.current);
      toast.success('Modelos actualizados: aplican en las próximas cargas y análisis');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'No se pudieron guardar los modelos');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Layout title="Panel de Administración" subtitle="Configuración de los modelos de IA del sistema">
      <Card data-testid="admin-ai-models">
        <CardHeader>
          <div className="flex items-start justify-between gap-4">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-violet-600" />
                Modelos de Claude por tarea
              </CardTitle>
              <CardDescription>
                Elige qué modelo usa cada proceso. Los modelos potentes dan mejor criterio; los rápidos cuestan menos
                en tareas de alto volumen.
              </CardDescription>
            </div>
            <div className="flex gap-2 shrink-0">
              <Button
                variant="outline"
                size="sm"
                disabled={!config || saving}
                onClick={() => setSelection(config.defaults)}
                data-testid="ai-models-reset"
              >
                <RotateCcw className="w-4 h-4 mr-2" />
                Valores recomendados
              </Button>
              <Button
                size="sm"
                disabled={!dirty || saving || !config?.can_edit}
                onClick={save}
                data-testid="ai-models-save"
              >
                {saving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Save className="w-4 h-4 mr-2" />}
                Guardar
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex justify-center py-12">
              <Loader2 className="w-8 h-8 animate-spin text-violet-600" />
            </div>
          ) : (
            <div className="divide-y divide-slate-200">
              {config.tasks.map((task) => (
                <div
                  key={task.key}
                  className="py-4 flex items-center justify-between gap-6"
                  data-testid={`ai-task-${task.key}`}
                >
                  <div className="min-w-0">
                    <p className="font-medium text-slate-900">{task.label}</p>
                    <p className="text-xs text-slate-500">{task.description}</p>
                  </div>
                  <div className="w-72 shrink-0">
                    <Select
                      value={selection[task.key]}
                      onValueChange={(value) => setSelection((prev) => ({ ...prev, [task.key]: value }))}
                      disabled={!config.can_edit}
                    >
                      <SelectTrigger data-testid={`ai-model-select-${task.key}`}>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {config.available_models.map((model) => (
                          <SelectItem key={model.id} value={model.id}>
                            {model.label} · {model.tier}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    {selection[task.key] !== config.current[task.key] && (
                      <Badge variant="outline" className="mt-2 text-amber-700 border-amber-300">
                        Sin guardar
                      </Badge>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </Layout>
  );
};

export default AdminPage;
