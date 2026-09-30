import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { ShieldCheck, LogIn, AlertCircle } from 'lucide-react';
import { PasswordInput } from '../components/common/PasswordInput';

export const Login = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const from = location.state?.from?.pathname || '/dashboard';

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (!username.trim() || !password) {
      setError('Por favor complete todos los campos.');
      return;
    }

    setLoading(true);
    try {
      await login(username.trim(), password);
      navigate(from, { replace: true });
    } catch (err) {
      const msg = err.response?.data?.detail || 'Error al iniciar sesión. Verifique sus credenciales.';
      setError(typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-container">
      <div className="login-card">
        <div className="login-header">
          <div className="login-logo">
            <ShieldCheck size={28} />
          </div>
          <h1 className="login-title">Validador SUNAT</h1>
          <p className="login-subtitle">Sistema de Validación de Comprobantes Electrónicos</p>
        </div>

        {error && (
          <div className="login-alert">
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <AlertCircle size={16} />
              <span>{error}</span>
            </div>
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label" htmlFor="username">
              Nombre de Usuario
            </label>
            <input
              id="username"
              type="text"
              className="form-input"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="robert"
              autoComplete="username"
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="password">
              Contraseña
            </label>
            <PasswordInput
              id="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              autoComplete="current-password"
              required
            />
          </div>

          <button type="submit" className="btn-primary" disabled={loading}>
            <LogIn size={18} />
            <span>{loading ? 'Validando...' : 'Iniciar Sesión'}</span>
          </button>
        </form>

        <div className="login-info-box">
          <strong>Acceso al Sistema:</strong><br />
          • Admin: <code>admin</code> (AdminDev2026!)<br />
          • DAIRA: <code>contador1.daira</code> o <code>robert</code> (ContadorDev2026!)<br />
          • JJD MAR: <code>contador1.jjdmar</code> (ContadorDev2026!)
        </div>
      </div>
    </div>
  );
};
