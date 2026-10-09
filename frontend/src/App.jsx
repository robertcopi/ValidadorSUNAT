import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { ProtectedRoute } from './components/common/ProtectedRoute';
import { DashboardLayout } from './layouts/DashboardLayout';
import { Login } from './pages/Login';
import { Dashboard } from './pages/Dashboard';
import { ValidacionIndividual } from './pages/ValidacionIndividual';
import { CargaMasiva } from './pages/CargaMasiva';
import { Historial } from './pages/Historial';
import { DetalleProceso } from './pages/DetalleProceso';
import { Perfil } from './pages/Perfil';
import { ConsultaSSCO } from './pages/ConsultaSSCO';
import { UsuariosAdmin } from './pages/UsuariosAdmin';
import { EmpresasAdmin } from './pages/EmpresasAdmin';
import { AuditoriaAdmin } from './pages/AuditoriaAdmin';

export const App = () => {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />

          <Route
            path="/"
            element={
              <ProtectedRoute>
                <DashboardLayout />
              </ProtectedRoute>
            }
          >
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="dashboard" element={<Dashboard />} />
            <Route path="validacion-individual" element={<ValidacionIndividual />} />
            <Route path="carga-masiva" element={<CargaMasiva />} />
            <Route path="historial" element={<Historial />} />
            <Route path="historial/:procesoId" element={<DetalleProceso />} />
            <Route path="ssco" element={<ConsultaSSCO />} />
            <Route path="perfil" element={<Perfil />} />

            {/* Módulos de Administración (Exclusivos para ADMINISTRADOR) */}
            <Route
              path="admin/usuarios"
              element={
                <ProtectedRoute requiredRole="ADMINISTRADOR">
                  <UsuariosAdmin />
                </ProtectedRoute>
              }
            />
            <Route
              path="admin/empresas"
              element={
                <ProtectedRoute requiredRole="ADMINISTRADOR">
                  <EmpresasAdmin />
                </ProtectedRoute>
              }
            />
            <Route
              path="admin/auditoria"
              element={
                <ProtectedRoute requiredRole="ADMINISTRADOR">
                  <AuditoriaAdmin />
                </ProtectedRoute>
              }
            />
          </Route>

          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
};

export default App;
