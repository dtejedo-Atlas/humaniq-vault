import React, { useState, useEffect } from 'react';
import Layout from '../components/Layout';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Loader2, Trash2, RotateCcw, Search } from 'lucide-react';
import { Input } from '../components/ui/input';
import { toast } from 'sonner';
import { trashAPI } from '../api';

const TYPE_LABELS = {
  identical_cv_cleanup: 'CV idéntico',
  duplicate_manual: 'Duplicado manual',
  orphan_cleanup: 'Registro huérfano',
  merged: 'Fusionada',
};

const formatDate = (value) => {
  if (!value) return 'Sin fecha';
  return new Date(value).toLocaleString('es-MX', { dateStyle: 'medium', timeStyle: 'short' });
};

export default function TrashPage() {
  const [loading, setLoading] = useState(true);
  const [items, setItems] = useState([]);
  const [query, setQuery] = useState('');
  const [restoring, setRestoring] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const res = await trashAPI.getDeleted();
      setItems(res.data.candidates || []);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error cargando la papelera');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const restore = async (item) => {
    if (!window.confirm(`¿Restaurar la ficha de ${item.full_name}?`)) return;
    setRestoring(item.candidate_id);
    try {
      await trashAPI.restore(item.candidate_id);
      toast.success(`${item.full_name} restaurada`);
      setItems((prev) => prev.filter((i) => i.candidate_id !== item.candidate_id));
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error al restaurar');
    } finally {
      setRestoring(null);
    }
  };

  const filtered = items.filter((i) =>
    !query.trim() || (i.full_name || '').toLowerCase().includes(query.trim().toLowerCase())
  );

  return (
    <Layout title="Papelera" subtitle="Fichas eliminadas, recuperables en un clic">
      <div className="space-y-6" data-testid="trash-page">
        <Card>
          <CardHeader className="flex flex-row items-start justify-between space-y-0 gap-4">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Trash2 className="w-5 h-5 text-slate-500" />
                {items.length} fichas eliminadas
              </CardTitle>
              <CardDescription>Nada se borra físicamente: puedes restaurar cualquier ficha</CardDescription>
            </div>
            <div className="relative w-64">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <Input
                className="pl-9"
                placeholder="Buscar por nombre"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                data-testid="trash-search"
              />
            </div>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="flex justify-center py-16">
                <Loader2 className="w-8 h-8 animate-spin text-cyan-600" />
              </div>
            ) : filtered.length === 0 ? (
              <div className="text-center py-12 text-slate-500" data-testid="trash-empty">
                <Trash2 className="w-12 h-12 mx-auto mb-3 text-slate-300" />
                <p>La papelera está vacía</p>
              </div>
            ) : (
              <div className="divide-y divide-slate-200">
                {filtered.map((item) => (
                  <div
                    key={item.candidate_id}
                    className="py-3 flex items-center justify-between gap-4"
                    data-testid={`trash-item-${item.candidate_id}`}
                  >
                    <div className="min-w-0">
                      <p className="font-medium text-slate-900 truncate">{item.full_name || 'Sin nombre'}</p>
                      <p className="text-xs text-slate-500 truncate">
                        {item.current_title || 'Sin puesto'}
                        {item.email ? ` · ${item.email}` : ''}
                      </p>
                      <p className="text-xs text-slate-400 mt-0.5">
                        Eliminada el {formatDate(item.deleted_at)} por {item.deleted_by}
                      </p>
                    </div>
                    <div className="flex items-center gap-3 shrink-0">
                      <div className="text-right">
                        {item.deletion_type && (
                          <Badge variant="outline" className="text-slate-600">
                            {TYPE_LABELS[item.deletion_type] || item.deletion_type}
                          </Badge>
                        )}
                        <p className="text-xs text-slate-400 mt-1 max-w-[260px] truncate">{item.reason}</p>
                      </div>
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={restoring === item.candidate_id}
                        onClick={() => restore(item)}
                        data-testid={`trash-restore-${item.candidate_id}`}
                      >
                        {restoring === item.candidate_id
                          ? <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                          : <RotateCcw className="w-4 h-4 mr-2" />}
                        Restaurar
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </Layout>
  );
}
