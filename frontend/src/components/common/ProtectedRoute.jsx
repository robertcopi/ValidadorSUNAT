import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';

export const ProtectedRoute = ({ children, requiredRole }) => {
  const { user, isAuthenticated, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div style={{ display: 'flex', height: '100vh', alignItems: 'center', justifyContent: 'center' }}>
        <p style={{ color: '#64748b', fontSize: '0.9rem' }}>Cargando sesión...</p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (requiredRole && user?.rol !== requiredRole) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center' }}>
        <h2>403 - Acceso Denegado</h2>
        <p>No cuenta con los permisos necesarios para visualizar este módulo.</p>
      </div>
    );
  }

  return children;
};
