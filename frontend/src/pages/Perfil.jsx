import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import axiosClient from '../api/axiosClient';
import {
  User,
  Shield,
  Building2,
  Mail,
  KeyRound,
  CheckCircle2,
  AlertTriangle,
  Loader2,
  Lock,
} from 'lucide-react';
import { PasswordInput } from '../components/common/PasswordInput';

export const Perfil = () => {
  const { user } = useAuth();

  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');

  const [loading, setLoading] = useState(false);
  const [successMsg, setSuccessMsg] = useState('');
  const [errorMsg, setErrorMsg] = useState('');

  const handleChangePassword = async (e) => {
    e.preventDefault();
    setSuccessMsg('');
    setErrorMsg('');

    if (newPassword.length < 6) {
      setErrorMsg('La nueva contraseña debe tener al menos 6 caracteres.');
      return;
    }

    if (newPassword !== confirmPassword) {
      setErrorMsg('La nueva contraseña y la confirmación no coinciden.');
      return;
    }

    if (currentPassword === newPassword) {
      setErrorMsg('La nueva contraseña debe ser distinta a la contraseña actual.');
      return;
    }

    try {
      setLoading(true);
      await axiosClient.post('/auth/change-password', {
        current_password: currentPassword,
        new_password: newPassword,
        confirm_password: confirmPassword,
      });

      setSuccessMsg('Contraseña actualizada exitosamente.');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');

      // Actualizar flag must_change_password en localStorage si existía
      if (user) {
        const updatedUser = { ...user, must_change_password: false };
        localStorage.setItem('user', JSON.stringify(updatedUser));
      }
    } catch (err) {
      const msg = err.response?.data?.detail || 'Error al cambiar la contraseña.';
      setErrorMsg(typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: '850px', margin: '0 auto' }}>
      <div style={{ marginBottom: '1.75rem' }}>
        <h2 style={{ fontSize: '1.5rem', fontWeight: '700', color: 'var(--color-text-main)', marginBottom: '0.25rem' }}>
          Mi Perfil de Usuario
        </h2>
        <p style={{ color: 'var(--color-text-muted)', fontSize: '0.875rem' }}>
          Información general de su cuenta y gestión segura de credenciales de acceso.
        </p>
      </div>

      {user?.must_change_password && (
        <div className="alert-banner alert-banner-warning">
          <AlertTriangle size={20} />
          <div>
            <strong>Cambio de contraseña requerido:</strong> Su cuenta posee una contraseña temporal asignada. Por motivos de seguridad debe actualizarla a continuación.
          </div>
        </div>
      )}

      {/* Tarjeta de Información General */}
      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.25rem', borderBottom: '1px solid var(--color-border)', paddingBottom: '0.75rem' }}>
          <User size={20} color="var(--color-primary)" />
          <h3 className="card-title" style={{ margin: 0 }}>Datos de la Cuenta</h3>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '1.25rem' }}>
          <div>
            <label className="form-label" style={{ color: 'var(--color-text-muted)' }}>Nombre Completo</label>
            <div style={{ fontWeight: '600', fontSize: '0.95rem' }}>{user?.nombre_completo || 'N/A'}</div>
          </div>

          <div>
            <label className="form-label" style={{ color: 'var(--color-text-muted)' }}>Correo Electrónico</label>
            <div style={{ fontWeight: '500', fontSize: '0.95rem' }}>{user?.email || 'N/A'}</div>
          </div>

          <div>
            <label className="form-label" style={{ color: 'var(--color-text-muted)' }}>Rol en el Sistema</label>
            <div>
              <span className={`badge ${user?.rol === 'ADMINISTRADOR' ? 'badge-info' : 'badge-success'}`}>
                <Shield size={12} />
                {user?.rol || 'CONTADOR'}
              </span>
            </div>
          </div>

          <div>
            <label className="form-label" style={{ color: 'var(--color-text-muted)' }}>Empresa Asignada</label>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Building2 size={16} color="#64748b" />
              <span style={{ fontWeight: '600' }}>
                {user?.empresa?.razon_social || (user?.rol === 'ADMINISTRADOR' ? 'Visión Global Multiempresa' : 'Sin Empresa')}
              </span>
            </div>
            {user?.empresa?.ruc && (
              <span style={{ fontSize: '0.775rem', color: 'var(--color-text-muted)', fontFamily: 'monospace' }}>
                RUC: {user.empresa.ruc}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Tarjeta de Cambio de Contraseña */}
      <div className="card">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.25rem', borderBottom: '1px solid var(--color-border)', paddingBottom: '0.75rem' }}>
          <KeyRound size={20} color="var(--color-primary)" />
          <h3 className="card-title" style={{ margin: 0 }}>Cambiar mi Contraseña</h3>
        </div>

        {errorMsg && (
          <div className="login-alert" style={{ marginBottom: '1.25rem' }}>
            {errorMsg}
          </div>
        )}

        {successMsg && (
          <div style={{
            backgroundColor: 'var(--color-success-bg)',
            border: '1px solid var(--color-success-border)',
            color: 'var(--color-success-text)',
            padding: '0.75rem 1rem',
            borderRadius: 'var(--radius-sm)',
            fontSize: '0.85rem',
            marginBottom: '1.25rem',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem'
          }}>
            <CheckCircle2 size={18} />
            <span>{successMsg}</span>
          </div>
        )}

        <form onSubmit={handleChangePassword}>
          <div className="form-group">
            <label className="form-label">Contraseña Actual</label>
            <PasswordInput
              placeholder="Ingrese su contraseña actual"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '1rem' }}>
            <div className="form-group">
              <label className="form-label">Nueva Contraseña</label>
              <PasswordInput
                placeholder="Mínimo 6 caracteres"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                autoComplete="new-password"
                required
                minLength={6}
              />
            </div>

            <div className="form-group">
              <label className="form-label">Confirmar Nueva Contraseña</label>
              <PasswordInput
                placeholder="Repita la nueva contraseña"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                autoComplete="new-password"
                required
                minLength={6}
              />
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '1rem' }}>
            <button
              type="submit"
              className="btn-primary"
              style={{ width: 'auto', padding: '0.65rem 1.5rem' }}
              disabled={loading}
            >
              {loading ? (
                <>
                  <Loader2 size={16} className="spin" />
                  <span>Actualizando...</span>
                </>
              ) : (
                <>
                  <Lock size={16} />
                  <span>Actualizar Contraseña</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
