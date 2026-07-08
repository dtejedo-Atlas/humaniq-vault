import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Sparkles, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

const LoginPage = () => {
  const navigate = useNavigate();
  const { login, register } = useAuth();
  const [loading, setLoading] = useState(false);
  const [isRegister, setIsRegister] = useState(false);
  
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    name: ''
  });

  const handleGoogleLogin = () => {
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    const redirectUrl = window.location.origin + '/dashboard';
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      if (isRegister) {
        await register(formData.email, formData.password, formData.name);
        toast.success('¡Cuenta creada exitosamente!');
      } else {
        await login(formData.email, formData.password);
        toast.success('¡Bienvenido a Humaniq!');
      }
      navigate('/dashboard');
    } catch (error) {
      console.error('Auth error:', error);
      toast.error(error.response?.data?.detail || 'Error en la autenticación');
    } finally {
      setLoading(false);
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
          <p className="text-slate-600 mt-2">Plataforma de reclutamiento ejecutivo con IA</p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>{isRegister ? 'Crear Cuenta' : 'Iniciar Sesión'}</CardTitle>
            <CardDescription>
              {isRegister 
                ? 'Crea tu cuenta para comenzar a usar Humaniq' 
                : 'Ingresa tus credenciales para acceder'}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              {isRegister && (
                <div>
                  <Label htmlFor="name">Nombre Completo</Label>
                  <Input
                    id="name"
                    data-testid="register-name-input"
                    type="text"
                    placeholder="Juan Pérez"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    required={isRegister}
                  />
                </div>
              )}
              
              <div>
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  data-testid="login-email-input"
                  type="email"
                  placeholder="tu@email.com"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  required
                />
              </div>
              
              <div>
                <Label htmlFor="password">Contraseña</Label>
                <Input
                  id="password"
                  data-testid="login-password-input"
                  type="password"
                  placeholder="••••••••"
                  value={formData.password}
                  onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                  required
                />
              </div>

              <Button
                type="submit"
                data-testid="login-submit-button"
                className="w-full"
                disabled={loading}
              >
                {loading ? (
                  <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Procesando...</>
                ) : (
                  isRegister ? 'Crear Cuenta' : 'Iniciar Sesión'
                )}
              </Button>
            </form>

            <div className="relative my-5">
              <div className="absolute inset-0 flex items-center">
                <span className="w-full border-t border-slate-200" />
              </div>
              <div className="relative flex justify-center text-xs">
                <span className="bg-white px-3 text-slate-500">o continúa con</span>
              </div>
            </div>

            <Button
              type="button"
              variant="outline"
              data-testid="google-login-button"
              className="w-full"
              onClick={handleGoogleLogin}
            >
              <svg className="w-4 h-4 mr-2" viewBox="0 0 24 24" aria-hidden="true">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
              </svg>
              Iniciar sesión con Google
            </Button>

            <div className="mt-4 text-center text-sm">
              <button
                type="button"
                onClick={() => setIsRegister(!isRegister)}
                className="text-cyan-600 hover:text-cyan-700 font-medium"
              >
                {isRegister 
                  ? '¿Ya tienes cuenta? Inicia sesión' 
                  : '¿No tienes cuenta? Regístrate'}
              </button>
            </div>
          </CardContent>
        </Card>

        <p className="text-center text-xs text-slate-500 mt-6">
          Plataforma para reclutamiento ejecutivo en México y Latinoamérica
        </p>
      </div>
    </div>
  );
};

export default LoginPage;