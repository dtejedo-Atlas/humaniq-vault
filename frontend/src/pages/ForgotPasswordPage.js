import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Loader2, MailCheck, ArrowLeft } from 'lucide-react';

const API_BASE = `${process.env.REACT_APP_BACKEND_URL}/api`;

const ForgotPasswordPage = () => {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [message, setMessage] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const { data } = await axios.post(`${API_BASE}/auth/forgot-password`, {
        email,
        origin: window.location.origin,
      });
      setMessage(data.message);
    } catch (error) {
      // La respuesta es genérica a propósito: nunca revelamos si el correo existe
      setMessage(
        'Si el correo está registrado, en unos minutos recibirás un enlace para restablecer tu contraseña. Revisa también tu carpeta de spam.'
      );
    } finally {
      setSent(true);
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <img src="/humaniq-logo.png" alt="Humaniq" className="h-12 w-auto mx-auto mb-4" />
          <h1 className="text-3xl font-bold text-slate-900">Talent Vault</h1>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Restablecer contraseña</CardTitle>
            <CardDescription>
              Escribe tu correo y te enviamos un enlace para crear una nueva contraseña. El enlace
              sirve una sola vez y vence en 48 horas.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {sent ? (
              <div className="space-y-4" data-testid="forgot-password-sent">
                <div className="flex items-start gap-3 rounded-lg bg-emerald-50 p-4 text-sm text-emerald-900">
                  <MailCheck className="mt-0.5 h-5 w-5 shrink-0" />
                  <p>{message}</p>
                </div>
                <Link to="/login">
                  <Button variant="outline" className="w-full" data-testid="forgot-password-back-button">
                    <ArrowLeft className="mr-2 h-4 w-4" /> Volver a iniciar sesión
                  </Button>
                </Link>
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <Label htmlFor="email">Correo</Label>
                  <Input
                    id="email"
                    data-testid="forgot-password-email-input"
                    type="email"
                    placeholder="tu@email.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                  />
                </div>
                <Button
                  type="submit"
                  className="w-full"
                  disabled={loading}
                  data-testid="forgot-password-submit-button"
                >
                  {loading ? (
                    <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Enviando...</>
                  ) : (
                    'Enviar enlace'
                  )}
                </Button>
                <Link
                  to="/login"
                  className="block text-center text-sm text-slate-500 hover:text-slate-900"
                  data-testid="forgot-password-login-link"
                >
                  Volver a iniciar sesión
                </Link>
              </form>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default ForgotPasswordPage;
