import React from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { Building2, AlertTriangle } from 'lucide-react';
import logoEmpresa from '../../assets/logo-empresa.png';

export const Navbar = () => {
  const { user } = useAuth();

  const empresaNombre = user?.empresa?.razon_social || (user?.rol === 'ADMINISTRADOR' ? 'Visión Global / Multiempresa' : 'Sin Empresa');
  const empresaRuc = user?.empresa?.ruc || (user?.rol === 'ADMINISTRADOR' ? 'ADMIN' : 'N/A');

  const userInitial = user?.nombre_completo ? user.nombre_completo.charAt(0).toUpperCase() : 'U';

  return (
    <header className="navbar">
      <div className="navbar-brand-group">
        <img
          src={logoEmpresa}
          alt="Logo Corporativo JD"
          className="navbar-corporate-logo"
        />
        <div className="navbar-tenant-badge">
          <Building2 size={16} color="var(--color-primary)" />
          <span className="tenant-name">{empresaNombre}</span>
          <span className="tenant-ruc">RUC: {empresaRuc}</span>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
        {user?.must_change_password && (
          <Link
            to="/perfil"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.4rem',
              backgroundColor: '#fffbeb',
              border: '1px solid #fde68a',
              color: '#92400e',
              padding: '0.35rem 0.75rem',
              borderRadius: '9999px',
              fontSize: '0.75rem',
              fontWeight: '600',
              textDecoration: 'none',
            }}
            title="Debe cambiar su contraseña temporal"
          >
            <AlertTriangle size={14} />
            <span>Cambio de clave requerido</span>
          </Link>
        )}

        <Link
          to="/perfil"
          className="navbar-user"
          style={{ textDecoration: 'none', cursor: 'pointer' }}
          title="Ver mi perfil"
        >
          <div className="user-avatar" title={user?.nombre_completo}>
            {userInitial}
          </div>
          <div className="user-details">
            <span className="user-name">{user?.nombre_completo}</span>
            <span className="user-role-badge">{user?.rol}</span>
          </div>
        </Link>
      </div>
    </header>
  );
};
