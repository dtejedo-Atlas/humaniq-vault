import React, { useState } from 'react';
import axios from 'axios';
import Layout from '../components/Layout';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { KeyRound, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

const API = process.env.REACT_APP_BACKEND_URL;

export default function ChangePasswordPage() {
  const [current, setCurrent] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [saving, setSaving] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (newPassword.length < 8) {
      toast.error('La nueva contraseña debe tener al menos 8 caracteres');
      return;
    }
    if (newPassword !== confirm) {
      toast.error('Las contraseñas no coinciden');
      return;
    }
    try {
      setSaving(true);
      await axios.post(`${API}/api/auth/change-password`, {
        current_password: current,
        new_password: newPassword
      });
      toast.success('Contraseña actualizada correctamente');
      setCurrent('');
      setNewPassword('');
      setConfirm('');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error al cambiar la contraseña');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Layout title="Cambiar Contraseña" subtitle="Actualiza tu contraseña de acceso">
      <div className="max-w-md" data-testid="change-password-page">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <KeyRound className="w-5 h-5 text-cyan-600" />
              Cambiar contraseña
            </CardTitle>
            <CardDescription>
              Ingresa tu contraseña actual y define una nueva (mínimo 8 caracteres).
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <Label htmlFor="current-password">Contraseña actual</Label>
                <Input
                  id="current-password"
                  data-testid="change-password-current-input"
                  type="password"
                  value={current}
                  onChange={(e) => setCurrent(e.target.value)}
                  required
                />
              </div>
              <div>
                <Label htmlFor="new-password">Nueva contraseña</Label>
                <Input
                  id="new-password"
                  data-testid="change-password-new-input"
                  type="password"
                  placeholder="Mínimo 8 caracteres"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  required
                />
              </div>
              <div>
                <Label htmlFor="confirm-password">Confirmar nueva contraseña</Label>
                <Input
                  id="confirm-password"
                  data-testid="change-password-confirm-input"
                  type="password"
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  required
                />
              </div>
              <Button type="submit" data-testid="change-password-submit" disabled={saving}>
                {saving ? (
                  <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Guardando...</>
                ) : 'Actualizar contraseña'}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </Layout>
  );
}
