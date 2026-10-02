import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import {
  LayoutDashboard,
  Search,
  UploadCloud,
  History,
  FileSpreadsheet,
  Users,
  Building,
  ShieldCheck,
  ShieldAlert,
  User,
  LogOut,
  FileText,
} from 'lucide-react';
import logoEmpresa from '../../assets/logo-empresa.png';

export const Sidebar = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const isAdmin = user?.rol === 'ADMINISTRADOR';

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <img
          src={logoEmpresa}
          alt="Logo Corporativo JD"
          className="sidebar-corporate-logo"
        />
        <div className="sidebar-brand-text">
          <h1 className="sidebar-title">Validador SUNAT</h1>
          <p className="sidebar-subtitle">Gestión Contable Multiempresa</p>
        </div>
      </div>

      <nav className="sidebar-nav">
        <span className="sidebar-section-title">Operaciones</span>

        <NavLink
          to="/dashboard"
          className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}
        >
          <LayoutDashboard size={18} />
          <span>Dashboard</span>
        </NavLink>

        <NavLink
          to="/validacion-individual"
          className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}
        >
          <Search size={18} />
          <span>Validación individual</span>
        </NavLink>

        <NavLink
          to="/carga-masiva"
          className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}
        >
          <UploadCloud size={18} />
          <span>Carga masiva Excel</span>
        </NavLink>

        <NavLink
          to="/historial"
          className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}
        >
          <History size={18} />
          <span>Historial</span>
        </NavLink>

        <span className="sidebar-section-title" style={{ marginTop: '0.75rem' }}>Cuenta</span>

        <NavLink
          to="/perfil"
          className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}
        >
          <User size={18} />
          <span>Mi Perfil</span>
          {user?.must_change_password && (
            <span style={{
              marginLeft: 'auto',
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              backgroundColor: '#f59e0b',
            }} title="Cambio de clave pendiente" />
          )}
        </NavLink>

        {isAdmin && (
          <>
            <span className="sidebar-section-title" style={{ marginTop: '0.75rem' }}>Administración</span>

            <NavLink
              to="/admin/usuarios"
              className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}
            >
              <Users size={18} />
              <span>Usuarios</span>
            </NavLink>

            <NavLink
              to="/admin/empresas"
              className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}
            >
              <Building size={18} />
              <span>Empresas</span>
            </NavLink>

            <NavLink
              to="/admin/auditoria"
              className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}
            >
              <FileText size={18} />
              <span>Auditoría</span>
            </NavLink>
          </>
        )}
      </nav>

      <div className="sidebar-footer">
        <button onClick={handleLogout} className="btn-logout" title="Cerrar sesión segura">
          <LogOut size={18} />
          <span>Cerrar sesión</span>
        </button>
      </div>
    </aside>
  );
};
