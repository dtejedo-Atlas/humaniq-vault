import React, { createContext, useContext, useState, useEffect } from 'react';
import axios from 'axios';

const AuthContext = createContext(null);

export const SESSION_CLOSED_MESSAGE = 'Tu sesión se cerró porque la contraseña cambió. Inicia sesión de nuevo.';
export const SESSION_CLOSED_KEY = 'atlas_session_closed';

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem('atlas_token'));
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const id = axios.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response?.status === 401 && error.response?.data?.detail === SESSION_CLOSED_MESSAGE) {
          sessionStorage.setItem(SESSION_CLOSED_KEY, '1');
          logout();
        }
        return Promise.reject(error);
      }
    );
    return () => axios.interceptors.response.eject(id);
  }, []);

  useEffect(() => {
    if (token) {
      // Verify token and get user
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
      fetchCurrentUser();
    } else {
      setLoading(false);
    }
  }, [token]);

  const fetchCurrentUser = async () => {
    try {
      const response = await axios.get(`${process.env.REACT_APP_BACKEND_URL}/api/auth/me`);
      setUser(response.data);
    } catch (error) {
      console.error('Error fetching user:', error);
      logout();
    } finally {
      setLoading(false);
    }
  };

  const login = async (email, password) => {
    const response = await axios.post(`${process.env.REACT_APP_BACKEND_URL}/api/auth/login`, {
      email,
      password
    });
    
    const { access_token, user: userData } = response.data;
    
    setToken(access_token);
    setUser(userData);
    localStorage.setItem('atlas_token', access_token);
    sessionStorage.removeItem(SESSION_CLOSED_KEY);
    axios.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;
    
    return userData;
  };

  const loginWithGoogleSession = async (sessionId) => {
    const response = await axios.post(`${process.env.REACT_APP_BACKEND_URL}/api/auth/google/session`, {
      session_id: sessionId
    });

    const { access_token, user: userData } = response.data;

    setToken(access_token);
    setUser(userData);
    localStorage.setItem('atlas_token', access_token);
    sessionStorage.removeItem(SESSION_CLOSED_KEY);
    axios.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;

    return userData;
  };

  const logout = () => {
    setUser(null);
    setToken(null);
    localStorage.removeItem('atlas_token');
    delete axios.defaults.headers.common['Authorization'];
  };

  return (
    <AuthContext.Provider value={{ user, token, loading, login, loginWithGoogleSession, logout }}>
      {children}
    </AuthContext.Provider>
  );
};