import React from 'react';
import { Outlet, Link, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Sidebar } from '../components/common/Sidebar';
import { Navbar } from '../components/common/Navbar';
import { AlertTriangle, ArrowRight } from 'lucide-react';

export const DashboardLayout = () => {
  const { user } = useAuth();
  const location = useLocation();

  const isProfilePage = location.pathname === '/perfil';

  return (
    <div className="app-container">
      <Sidebar />
      <div className="main-wrapper">
        <Navbar />

        {user?.must_change_password && !isProfilePage && (
          <div style={{
            backgroundColor: '#fef3c7',
            borderBottom: '1px solid #fde68a',
            color: '#92400e',
            padding: '0.65rem 2rem',
            fontSize: '0.85rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '0.5rem',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <AlertTriangle size={16} color="#d97706" />
              <span>
                <strong>Aviso de Seguridad:</strong> Su cuenta requiere cambio obligatorio de contraseña temporal.
              </span>
            </div>
            <Link
              to="/perfil"
              style={{
                color: '#92400e',
                fontWeight: '700',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.25rem',
                textDecoration: 'underline',
              }}
            >
              <span>Cambiar mi contraseña ahora</span>
              <ArrowRight size={14} />
            </Link>
          </div>
        )}

        <main className="content-container">
          <Outlet />
        </main>
      </div>
    </div>
  );
};
