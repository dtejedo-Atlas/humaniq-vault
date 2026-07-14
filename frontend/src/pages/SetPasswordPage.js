import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Sparkles, Loader2, AlertCircle, KeyRound } from 'lucide-react';
import { toast } from 'sonner';

const API = process.env.REACT_APP_BACKEND_URL;

export default function SetPasswordPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');

  const [validating, setValidating] = useState(true);
  const [tokenInfo, setTokenInfo] = useState(null);
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!token) {
      setValidating(false);
      return;
    }
    axios.post(`${API}/api/auth/validate-setup-token`, { token })
      .then((res) => setTokenInfo(res.data.valid ? res.data : null))
      .catch(() => setTokenInfo(null))
      .finally(() => setValidating(false));
  }, [token]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (password.length < 8) {
      toast.error('La contraseña debe tener al menos 8 caracteres');
      return;
    }
    if (password !== confirm) {
      toast.error('Las contraseñas no coinciden');
      return;
    }
    try {
      setSaving(true);
      await axios.post(`${API}/api/auth/set-password`, { token, password });
      toast.success('Contraseña establecida. Ya puedes iniciar sesión.');
      navigate('/login', { replace: true });
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error al establecer la contraseña');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-slate-900 rounded-sm mb-4">
            <Sparkles className="w-8 h-8 text-cyan-400" />
          </div>
          <h1 className="text-3xl font-bold text-slate-900">Humaniq Talent Vault</h1>
        </div>

        <Card>
          {validating ? (
            <CardContent className="py-12 flex flex-col items-center gap-3" data-testid="set-password-validating">
              <Loader2 className="w-8 h-8 animate-spin text-cyan-600" />
              <p className="text-sm text-slate-500">Validando enlace...</p>
            </CardContent>
          ) : !tokenInfo ? (
            <CardContent className="py-10 text-center space-y-3" data-testid="set-password-invalid">
              <AlertCircle className="w-10 h-10 text-red-500 mx-auto" />
              <h2 className="text-lg font-semibold text-slate-900">Enlace inválido o expirado</h2>
              <p className="text-sm text-slate-500">
                Este enlace ya fue usado o expiró (48h). Pide a un administrador que te reenvíe la invitación o el restablecimiento.
              </p>
              <Button variant="outline" onClick={() => navigate('/login')} data-testid="set-password-go-login">
                Ir al inicio de sesión
              </Button>
            </CardContent>
          ) : (
            <>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <KeyRound className="w-5 h-5 text-cyan-600" />
                  {tokenInfo.purpose === 'reset' ? 'Restablece tu contraseña' : 'Establece tu contraseña'}
                </CardTitle>
                <CardDescription>
                  Hola {tokenInfo.name} ({tokenInfo.email}). Define tu contraseña para acceder a la plataforma.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleSubmit} className="space-y-4">
                  <div>
                    <Label htmlFor="new-password">Nueva contraseña</Label>
                    <Input
                      id="new-password"
                      data-testid="set-password-input"
                      type="password"
                      placeholder="Mínimo 8 caracteres"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      required
                    />
                  </div>
                  <div>
                    <Label htmlFor="confirm-password">Confirmar contraseña</Label>
                    <Input
                      id="confirm-password"
                      data-testid="set-password-confirm-input"
                      type="password"
                      placeholder="Repite la contraseña"
                      value={confirm}
                      onChange={(e) => setConfirm(e.target.value)}
                      required
                    />
                  </div>
                  <Button type="submit" data-testid="set-password-submit" className="w-full" disabled={saving}>
                    {saving ? (
                      <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Guardando...</>
                    ) : 'Guardar contraseña'}
                  </Button>
                </form>
              </CardContent>
            </>
          )}
        </Card>
      </div>
    </div>
  );
}
