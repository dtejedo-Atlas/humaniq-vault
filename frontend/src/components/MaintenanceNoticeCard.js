import React, { useEffect, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Switch } from './ui/switch';
import { Wrench, Save, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { systemAPI } from '../api';

const TEXTO_SUGERIDO =
  'Vamos a actualizar la plataforma. Evita subir CVs durante ese rato: una carga a medias se interrumpe.';

export const MaintenanceNoticeCard = () => {
  const [active, setActive] = useState(false);
  const [message, setMessage] = useState('');
  const [scheduledAt, setScheduledAt] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    systemAPI.getMaintenanceNotice()
      .then(({ data }) => {
        setActive(!!data.active);
        setMessage(data.message || '');
        setScheduledAt(data.scheduled_at ? data.scheduled_at.slice(0, 16) : '');
      })
      .catch(() => {});
  }, []);

  const save = async () => {
    setSaving(true);
    try {
      await systemAPI.setMaintenanceNotice({
        active,
        message: message || TEXTO_SUGERIDO,
        scheduled_at: scheduledAt ? new Date(scheduledAt).toISOString() : null,
      });
      toast.success(active ? 'Cartel de mantenimiento encendido' : 'Cartel de mantenimiento apagado');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'No se pudo guardar el aviso');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card data-testid="admin-maintenance-notice" className="mt-6">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Wrench className="h-4 w-4" /> Aviso de mantenimiento
        </CardTitle>
        <CardDescription>
          Enciéndelo antes de un despliegue: todas las consultoras verán un cartel pidiéndoles que no
          suban CVs mientras dure la actualización.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center justify-between rounded-sm border p-3">
          <Label htmlFor="maintenance-active">Mostrar el cartel ahora</Label>
          <Switch
            id="maintenance-active"
            checked={active}
            onCheckedChange={setActive}
            data-testid="maintenance-active-switch"
          />
        </div>
        <div>
          <Label htmlFor="maintenance-when">Fecha y hora prevista (opcional)</Label>
          <Input
            id="maintenance-when"
            type="datetime-local"
            value={scheduledAt}
            onChange={(e) => setScheduledAt(e.target.value)}
            data-testid="maintenance-datetime-input"
          />
        </div>
        <div>
          <Label htmlFor="maintenance-message">Mensaje</Label>
          <Input
            id="maintenance-message"
            placeholder={TEXTO_SUGERIDO}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            data-testid="maintenance-message-input"
          />
        </div>
        <Button onClick={save} disabled={saving} data-testid="maintenance-save-button">
          {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
          Guardar aviso
        </Button>
      </CardContent>
    </Card>
  );
};

export default MaintenanceNoticeCard;
