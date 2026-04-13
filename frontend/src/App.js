import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { TaxonomyProvider } from './contexts/TaxonomyContext';
import { Toaster } from './components/ui/sonner';
import axios from 'axios';
import './App.css';

// Pages
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import CandidatesPage from './pages/CandidatesPage';
import CandidateDetailPage from './pages/CandidateDetailPage';
import UploadPage from './pages/UploadPage';
import SearchPage from './pages/SearchPage';
import JobsPage from './pages/JobsPage';
import JobDetailPage from './pages/JobDetailPage';
import FoldersPage from './pages/FoldersPage';
import FolderViewPage from './pages/FolderViewPage';
import AdminPage from './pages/AdminPage';
import ValidationPage from './pages/ValidationPage';
import UsersPage from './pages/UsersPage';
import DuplicatesPage from './pages/DuplicatesPage';

// Configure axios defaults
axios.defaults.baseURL = process.env.REACT_APP_BACKEND_URL;

// Protected Route Component
const ProtectedRoute = ({ children }) => {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="spinner w-12 h-12 border-4 border-slate-300 border-t-cyan-500 rounded-full"></div>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return children;
};

// Public Route Component (redirects to dashboard if already logged in)
const PublicRoute = ({ children }) => {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="spinner w-12 h-12 border-4 border-slate-300 border-t-cyan-500 rounded-full"></div>
      </div>
    );
  }

  if (user) {
    return <Navigate to="/dashboard" replace />;
  }

  return children;
};

function AppRoutes() {
  return (
    <Routes>
      {/* Public Routes */}
      <Route
        path="/login"
        element={
          <PublicRoute>
            <LoginPage />
          </PublicRoute>
        }
      />

      {/* Protected Routes */}
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <DashboardPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/candidates"
        element={
          <ProtectedRoute>
            <CandidatesPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/candidates/:id"
        element={
          <ProtectedRoute>
            <CandidateDetailPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/upload"
        element={
          <ProtectedRoute>
            <UploadPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/search"
        element={
          <ProtectedRoute>
            <SearchPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/jobs"
        element={
          <ProtectedRoute>
            <JobsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/jobs/:id"
        element={
          <ProtectedRoute>
            <JobDetailPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/folders"
        element={
          <ProtectedRoute>
            <FoldersPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/folders/:id"
        element={
          <ProtectedRoute>
            <FolderViewPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin"
        element={
          <ProtectedRoute>
            <AdminPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/validation"
        element={
          <ProtectedRoute>
            <ValidationPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/users"
        element={
          <ProtectedRoute>
            <UsersPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/duplicates"
        element={
          <ProtectedRoute>
            <DuplicatesPage />
          </ProtectedRoute>
        }
      />

      {/* Redirect root to dashboard */}
      <Route path="/" element={<Navigate to="/dashboard" replace />} />

      {/* 404 */}
      <Route
        path="*"
        element={
          <div className="min-h-screen flex items-center justify-center bg-slate-50">
            <div className="text-center">
              <h1 className="text-4xl font-bold text-slate-900 mb-2">404</h1>
              <p className="text-slate-600 mb-4">Página no encontrada</p>
              <a href="/dashboard" className="text-cyan-600 hover:underline">
                Volver al Dashboard
              </a>
            </div>
          </div>
        }
      />
    </Routes>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <TaxonomyProvider>
          <div className="App">
            <AppRoutes />
            <Toaster position="top-right" />
          </div>
        </TaxonomyProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
