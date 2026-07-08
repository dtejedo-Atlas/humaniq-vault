import React, { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { toast } from 'sonner';

// Procesa el retorno de Google OAuth (Emergent Auth): {origin}/dashboard#session_id=xxx
// REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
export default function AuthCallback() {
  const navigate = useNavigate();
  const { loginWithGoogleSession } = useAuth();
  const hasProcessed = useRef(false);

  useEffect(() => {
    if (hasProcessed.current) return;
    hasProcessed.current = true;

    const hash = window.location.hash || '';
    const sessionId = new URLSearchParams(hash.substring(1)).get('session_id');
    window.history.replaceState(null, '', window.location.pathname);

    if (!sessionId) {
      navigate('/login', { replace: true });
      return;
    }

    loginWithGoogleSession(sessionId)
      .then(() => {
        toast.success('¡Bienvenido a Humaniq!');
        navigate('/dashboard', { replace: true });
      })
      .catch((error) => {
        toast.error(error.response?.data?.detail || 'Error al iniciar sesión con Google');
        navigate('/login', { replace: true });
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50" data-testid="google-auth-callback">
      <div className="text-center">
        <div className="spinner w-12 h-12 border-4 border-slate-300 border-t-cyan-500 rounded-full mx-auto mb-4"></div>
        <p className="text-slate-600 text-sm">Verificando tu cuenta de Google...</p>
      </div>
    </div>
  );
}
