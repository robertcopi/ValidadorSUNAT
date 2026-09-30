import React, { useState, useEffect } from 'react';
import axiosClient from '../api/axiosClient';
import {
  Users,
  UserPlus,
  Search,
  KeyRound,
  Edit2,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Loader2,
  Copy,
  Check,
  Building2,
  Shield,
  X,
} from 'lucide-react';
import { PasswordInput } from '../components/common/PasswordInput';

export const UsuariosAdmin = () => {
  const [usuarios, setUsuarios] = useState([]);
  const [empresas, setEmpresas] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Filtros
  const [filtroRol, setFiltroRol] = useState('');
  const [filtroEmpresa, setFiltroEmpresa] = useState('');
  const [filtroActivo, setFiltroActivo] = useState('');
  const [busqueda, setBusqueda] = useState('');

  // Modales
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showResetModal, setShowResetModal] = useState(false);

  // Formulario Crear
  const [createData, setCreateData] = useState({
    nombre_completo: '',
    username: '',
    email: '',
    rol: 'CONTADOR',
    empresa_id: '',
    password: '',
  });

  // Formulario Editar
  const [selectedUser, setSelectedUser] = useState(null);
  const [editData, setEditData] = useState({
    nombre_completo: '',
    username: '',
    email: '',
    rol: 'CONTADOR',
    empresa_id: '',
  });

  // Reset Password State
  const [tempPassword, setTempPassword] = useState('');
  const [customTempPassword, setCustomTempPassword] = useState('');
  const [copied, setCopied] = useState(false);

  const [actionLoading, setActionLoading] = useState(false);
  const [modalError, setModalError] = useState('');

  const cargarDatos = async () => {
    try {
      setLoading(true);
      setError(null);

      const [resUsuarios, resEmpresas] = await Promise.all([
        axiosClient.get('/admin/usuarios'),
        axiosClient.get('/admin/empresas'),
      ]);

      setUsuarios(resUsuarios.data || []);
      setEmpresas(resEmpresas.data || []);
    } catch (err) {
      console.error('Error al cargar datos de usuarios:', err);
      const msg = err.response?.data?.detail || 'Error al cargar usuarios y empresas.';
      setError(typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    cargarDatos();
  }, []);

  const handleCrearUsuario = async (e) => {
    e.preventDefault();
    setModalError('');

    if (createData.rol === 'CONTADOR' && !createData.empresa_id) {
      setModalError('Un usuario con rol CONTADOR debe pertenecer obligatoriamente a una empresa.');
      return;
    }

    try {
      setActionLoading(true);
      const payload = {
        nombre_completo: createData.nombre_completo.trim(),
        username: createData.username.trim().toLowerCase(),
        email: createData.email.trim().toLowerCase(),
        rol: createData.rol,
        empresa_id: createData.empresa_id ? parseInt(createData.empresa_id, 10) : null,
        password: createData.password,
        activo: true,
      };

      await axiosClient.post('/admin/usuarios', payload);
      setShowCreateModal(false);
      setCreateData({
        nombre_completo: '',
        username: '',
        email: '',
        rol: 'CONTADOR',
        empresa_id: '',
        password: '',
      });
      cargarDatos();
    } catch (err) {
      const msg = err.response?.data?.detail || 'Error al crear el usuario.';
      setModalError(typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setActionLoading(false);
    }
  };

  const openEditModal = (u) => {
    setSelectedUser(u);
    setEditData({
      nombre_completo: u.nombre_completo,
      username: u.username || '',
      email: u.email,
      rol: u.rol,
      empresa_id: u.empresa_id ? String(u.empresa_id) : '',
    });
    setModalError('');
    setShowEditModal(true);
  };

  const handleEditarUsuario = async (e) => {
    e.preventDefault();
    setModalError('');

    if (editData.rol === 'CONTADOR' && !editData.empresa_id) {
      setModalError('Un usuario con rol CONTADOR no puede quedar sin empresa asignada.');
      return;
    }

    try {
      setActionLoading(true);
      const payload = {
        nombre_completo: editData.nombre_completo.trim(),
        username: editData.username.trim().toLowerCase(),
        email: editData.email.trim().toLowerCase(),
        rol: editData.rol,
        empresa_id: editData.empresa_id ? parseInt(editData.empresa_id, 10) : (editData.rol === 'ADMINISTRADOR' ? 0 : null),
      };

      await axiosClient.put(`/admin/usuarios/${selectedUser.id}`, payload);
      setShowEditModal(false);
      cargarDatos();
    } catch (err) {
      const msg = err.response?.data?.detail || 'Error al actualizar usuario.';
      setModalError(typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setActionLoading(false);
    }
  };

  const handleToggleEstado = async (u) => {
    const accion = u.activo ? 'desactivar' : 'activar';
    if (!window.confirm(`¿Está seguro de que desea ${accion} al usuario ${u.nombre_completo}?`)) {
      return;
    }

    try {
      await axiosClient.patch(`/admin/usuarios/${u.id}/estado`, {
        activo: !u.activo,
      });
      cargarDatos();
    } catch (err) {
      const msg = err.response?.data?.detail || 'Error al cambiar estado del usuario.';
      alert(typeof msg === 'string' ? msg : JSON.stringify(msg));
    }
  };

  const openResetModal = (u) => {
    setSelectedUser(u);
    setTempPassword('');
    setCustomTempPassword('');
    setCopied(false);
    setModalError('');
    setShowResetModal(true);
  };

  const handleResetPassword = async (e) => {
    e.preventDefault();
    setModalError('');

    try {
      setActionLoading(true);
      const payload = customTempPassword ? { temporary_password: customTempPassword } : {};
      const res = await axiosClient.post(`/admin/usuarios/${selectedUser.id}/reset-password`, payload);
      setTempPassword(res.data.temporary_password);
      cargarDatos();
    } catch (err) {
      const msg = err.response?.data?.detail || 'Error al restablecer la contraseña.';
      setModalError(typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setActionLoading(false);
    }
  };

  const copyToClipboard = () => {
    if (tempPassword) {
      navigator.clipboard.writeText(tempPassword);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    }
  };

  // Filtrado en memoria
  const usuariosFiltrados = usuarios.filter((u) => {
    if (filtroRol && u.rol !== filtroRol) return false;
    if (filtroEmpresa && String(u.empresa_id) !== filtroEmpresa) return false;
    if (filtroActivo !== '') {
      const activoBool = filtroActivo === 'true';
      if (u.activo !== activoBool) return false;
    }
    if (busqueda.trim()) {
      const term = busqueda.toLowerCase();
      const matchNom = u.nombre_completo.toLowerCase().includes(term);
      const matchUname = u.username?.toLowerCase().includes(term);
      const matchEmail = u.email.toLowerCase().includes(term);
      const matchEmp = u.empresa?.razon_social?.toLowerCase().includes(term);
      if (!matchNom && !matchUname && !matchEmail && !matchEmp) return false;
    }
    return true;
  });

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h2 style={{ fontSize: '1.5rem', fontWeight: '700', color: 'var(--color-text-main)', marginBottom: '0.25rem' }}>
            Administración de Usuarios
          </h2>
          <p style={{ color: 'var(--color-text-muted)', fontSize: '0.875rem' }}>
            Control de accesos, asignación de empresas y restablecimiento de credenciales.
          </p>
        </div>

        <button
          onClick={() => {
            setModalError('');
            setShowCreateModal(true);
          }}
          className="btn-primary"
          style={{ width: 'auto', padding: '0.65rem 1.25rem' }}
        >
          <UserPlus size={18} />
          <span>Crear Usuario</span>
        </button>
      </div>

      {error && (
        <div className="login-alert" style={{ marginBottom: '1.5rem' }}>
          {error}
        </div>
      )}

      {/* Barra de Filtros */}
      <div className="card" style={{ marginBottom: '1.5rem', padding: '1rem' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
          <div>
            <label className="form-label" style={{ fontSize: '0.75rem' }}>Búsqueda</label>
            <div style={{ position: 'relative' }}>
              <input
                type="text"
                className="form-input"
                placeholder="Nombre, email o empresa..."
                value={busqueda}
                onChange={(e) => setBusqueda(e.target.value)}
                style={{ paddingLeft: '2.2rem' }}
              />
              <Search size={16} style={{ position: 'absolute', left: '0.75rem', top: '50%', transform: 'translateY(-50%)', color: '#94a3b8' }} />
            </div>
          </div>

          <div>
            <label className="form-label" style={{ fontSize: '0.75rem' }}>Rol</label>
            <select
              className="form-input"
              value={filtroRol}
              onChange={(e) => setFiltroRol(e.target.value)}
            >
              <option value="">Todos los roles</option>
              <option value="ADMINISTRADOR">ADMINISTRADOR</option>
              <option value="CONTADOR">CONTADOR</option>
            </select>
          </div>

          <div>
            <label className="form-label" style={{ fontSize: '0.75rem' }}>Empresa Asignada</label>
            <select
              className="form-input"
              value={filtroEmpresa}
              onChange={(e) => setFiltroEmpresa(e.target.value)}
            >
              <option value="">Todas las empresas</option>
              {empresas.map((emp) => (
                <option key={emp.id} value={emp.id}>
                  {emp.razon_social} ({emp.ruc})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="form-label" style={{ fontSize: '0.75rem' }}>Estado</label>
            <select
              className="form-input"
              value={filtroActivo}
              onChange={(e) => setFiltroActivo(e.target.value)}
            >
              <option value="">Todos</option>
              <option value="true">Activos</option>
              <option value="false">Inactivos</option>
            </select>
          </div>
        </div>
      </div>

      {/* Tabla de Usuarios */}
      <div className="custom-table-container">
        {loading ? (
          <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--color-text-muted)' }}>
            <Loader2 size={32} className="spin" style={{ margin: '0 auto 1rem' }} />
            <p>Cargando lista de usuarios...</p>
          </div>
        ) : (
          <table className="custom-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Usuario</th>
                <th>Rol</th>
                <th>Empresa Asignada</th>
                <th>Estado</th>
                <th>Clave Temp.</th>
                <th style={{ textAlign: 'right' }}>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {usuariosFiltrados.length === 0 ? (
                <tr>
                  <td colSpan="7" style={{ textAlign: 'center', padding: '2rem', color: '#64748b' }}>
                    No se encontraron usuarios que coincidan con los filtros.
                  </td>
                </tr>
              ) : (
                usuariosFiltrados.map((u) => (
                  <tr key={u.id}>
                    <td style={{ fontWeight: '600', color: '#64748b' }}>#{u.id}</td>
                    <td>
                      <div style={{ fontWeight: '600' }}>{u.nombre_completo}</div>
                      {u.username && (
                        <div style={{ fontSize: '0.8rem', color: 'var(--color-primary)', fontWeight: '500' }}>
                          @{u.username}
                        </div>
                      )}
                      <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>{u.email}</div>
                    </td>
                    <td>
                      <span className={`badge ${u.rol === 'ADMINISTRADOR' ? 'badge-info' : 'badge-success'}`}>
                        {u.rol}
                      </span>
                    </td>
                    <td>
                      {u.empresa ? (
                        <div>
                          <div style={{ fontWeight: '500' }}>{u.empresa.razon_social}</div>
                          <div style={{ fontSize: '0.75rem', color: '#64748b', fontFamily: 'monospace' }}>
                            RUC: {u.empresa.ruc}
                          </div>
                        </div>
                      ) : (
                        <span style={{ color: '#94a3b8', fontStyle: 'italic' }}>
                          {u.rol === 'ADMINISTRADOR' ? 'Global (Sin empresa fija)' : 'Sin Asignar'}
                        </span>
                      )}
                    </td>
                    <td>
                      <span className={`badge ${u.activo ? 'badge-success' : 'badge-danger'}`}>
                        {u.activo ? 'Activo' : 'Inactivo'}
                      </span>
                    </td>
                    <td>
                      {u.must_change_password ? (
                        <span className="badge badge-warning" title="Requiere cambio obligatorio">
                          Pendiente
                        </span>
                      ) : (
                        <span style={{ color: '#94a3b8', fontSize: '0.8rem' }}>No</span>
                      )}
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <div style={{ display: 'inline-flex', gap: '0.35rem' }}>
                        <button
                          onClick={() => openEditModal(u)}
                          className="btn-sm btn-action-edit"
                          title="Editar usuario"
                        >
                          <Edit2 size={13} />
                          <span>Editar</span>
                        </button>

                        <button
                          onClick={() => openResetModal(u)}
                          className="btn-sm btn-action-view"
                          title="Restablecer contraseña temporal"
                        >
                          <KeyRound size={13} />
                          <span>Reset Clave</span>
                        </button>

                        <button
                          onClick={() => handleToggleEstado(u)}
                          className={`btn-sm ${u.activo ? 'btn-action-status-off' : 'btn-action-status-on'}`}
                          title={u.activo ? 'Desactivar usuario' : 'Activar usuario'}
                        >
                          {u.activo ? <XCircle size={13} /> : <CheckCircle2 size={13} />}
                          <span>{u.activo ? 'Desactivar' : 'Activar'}</span>
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        )}
      </div>

      {/* Modal Crear Usuario */}
      {showCreateModal && (
        <div className="modal-overlay">
          <div className="modal-content">
            <div className="modal-header">
              <div className="modal-title">
                <UserPlus size={20} color="var(--color-primary)" />
                <span>Nuevo Usuario</span>
              </div>
              <button
                onClick={() => setShowCreateModal(false)}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#94a3b8' }}
              >
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleCrearUsuario}>
              <div className="modal-body">
                {modalError && (
                  <div className="login-alert" style={{ marginBottom: '1rem' }}>
                    {modalError}
                  </div>
                )}

                <div className="form-group">
                  <label className="form-label">Nombre Completo *</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="Ej. Juan Pérez"
                    value={createData.nombre_completo}
                    onChange={(e) => setCreateData({ ...createData, nombre_completo: e.target.value })}
                    required
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Nombre de Usuario *</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="Ej. robert (letras, números, '.', '_', '-')"
                    value={createData.username}
                    onChange={(e) => setCreateData({ ...createData, username: e.target.value })}
                    required
                    minLength={3}
                    maxLength={50}
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Correo Electrónico *</label>
                  <input
                    type="email"
                    className="form-input"
                    placeholder="ejemplo@empresa.com"
                    value={createData.email}
                    onChange={(e) => setCreateData({ ...createData, email: e.target.value })}
                    required
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Rol del Usuario</label>
                  <select
                    className="form-input"
                    value={createData.rol}
                    onChange={(e) => setCreateData({ ...createData, rol: e.target.value })}
                    required
                  >
                    <option value="CONTADOR">CONTADOR (Requiere empresa fija)</option>
                    <option value="ADMINISTRADOR">ADMINISTRADOR (Acceso global)</option>
                  </select>
                </div>

                <div className="form-group">
                  <label className="form-label">
                    Empresa Asignada {createData.rol === 'CONTADOR' && <span style={{ color: '#ef4444' }}>*</span>}
                  </label>
                  <select
                    className="form-input"
                    value={createData.empresa_id}
                    onChange={(e) => setCreateData({ ...createData, empresa_id: e.target.value })}
                    required={createData.rol === 'CONTADOR'}
                  >
                    <option value="">
                      {createData.rol === 'ADMINISTRADOR' ? 'Sin empresa (Alcance Global)' : '-- Seleccione Empresa --'}
                    </option>
                    {empresas.filter((emp) => emp.activo).map((emp) => (
                      <option key={emp.id} value={emp.id}>
                        {emp.razon_social} (RUC: {emp.ruc})
                      </option>
                    ))}
                  </select>
                </div>

                <div className="form-group">
                  <label className="form-label">Contraseña Inicial</label>
                  <PasswordInput
                    placeholder="Mínimo 6 caracteres"
                    value={createData.password}
                    onChange={(e) => setCreateData({ ...createData, password: e.target.value })}
                    autoComplete="new-password"
                    required
                    minLength={6}
                  />
                </div>
              </div>

              <div className="modal-footer">
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => setShowCreateModal(false)}
                  disabled={actionLoading}
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="btn-primary"
                  style={{ width: 'auto', padding: '0.6rem 1.25rem' }}
                  disabled={actionLoading}
                >
                  {actionLoading ? <Loader2 size={16} className="spin" /> : 'Guardar Usuario'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal Editar Usuario */}
      {showEditModal && selectedUser && (
        <div className="modal-overlay">
          <div className="modal-content">
            <div className="modal-header">
              <div className="modal-title">
                <Edit2 size={20} color="var(--color-primary)" />
                <span>Editar Usuario #{selectedUser.id}</span>
              </div>
              <button
                onClick={() => setShowEditModal(false)}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#94a3b8' }}
              >
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleEditarUsuario}>
              <div className="modal-body">
                {modalError && (
                  <div className="login-alert" style={{ marginBottom: '1rem' }}>
                    {modalError}
                  </div>
                )}

                <div className="form-group">
                  <label className="form-label">Nombre Completo</label>
                  <input
                    type="text"
                    className="form-input"
                    value={editData.nombre_completo}
                    onChange={(e) => setEditData({ ...editData, nombre_completo: e.target.value })}
                    required
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Nombre de Usuario *</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="Ej. robert"
                    value={editData.username}
                    onChange={(e) => setEditData({ ...editData, username: e.target.value })}
                    required
                    minLength={3}
                    maxLength={50}
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Correo Electrónico</label>
                  <input
                    type="email"
                    className="form-input"
                    value={editData.email}
                    onChange={(e) => setEditData({ ...editData, email: e.target.value })}
                    required
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Rol</label>
                  <select
                    className="form-input"
                    value={editData.rol}
                    onChange={(e) => setEditData({ ...editData, rol: e.target.value })}
                    required
                  >
                    <option value="CONTADOR">CONTADOR</option>
                    <option value="ADMINISTRADOR">ADMINISTRADOR</option>
                  </select>
                </div>

                <div className="form-group">
                  <label className="form-label">
                    Empresa Asignada {editData.rol === 'CONTADOR' && <span style={{ color: '#ef4444' }}>*</span>}
                  </label>
                  <select
                    className="form-input"
                    value={editData.empresa_id}
                    onChange={(e) => setEditData({ ...editData, empresa_id: e.target.value })}
                    required={editData.rol === 'CONTADOR'}
                  >
                    <option value="">
                      {editData.rol === 'ADMINISTRADOR' ? 'Sin empresa (Alcance Global)' : '-- Seleccione Empresa --'}
                    </option>
                    {empresas.map((emp) => (
                      <option key={emp.id} value={emp.id}>
                        {emp.razon_social} (RUC: {emp.ruc}) {!emp.activo ? '[Inactiva]' : ''}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="modal-footer">
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => setShowEditModal(false)}
                  disabled={actionLoading}
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="btn-primary"
                  style={{ width: 'auto', padding: '0.6rem 1.25rem' }}
                  disabled={actionLoading}
                >
                  {actionLoading ? <Loader2 size={16} className="spin" /> : 'Guardar Cambios'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal Restablecer Contraseña */}
      {showResetModal && selectedUser && (
        <div className="modal-overlay">
          <div className="modal-content">
            <div className="modal-header">
              <div className="modal-title">
                <KeyRound size={20} color="var(--color-primary)" />
                <span>Restablecer Contraseña</span>
              </div>
              <button
                onClick={() => setShowResetModal(false)}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#94a3b8' }}
              >
                <X size={20} />
              </button>
            </div>

            <div className="modal-body">
              <p style={{ fontSize: '0.875rem', color: 'var(--color-text-muted)', marginBottom: '1.25rem' }}>
                Genera una contraseña temporal para <strong>{selectedUser.nombre_completo}</strong> ({selectedUser.email}). Al ingresar, el usuario estará obligado a cambiarla.
              </p>

              {modalError && (
                <div className="login-alert" style={{ marginBottom: '1rem' }}>
                  {modalError}
                </div>
              )}

              {tempPassword ? (
                <div style={{
                  backgroundColor: '#f0fdf4',
                  border: '1px solid #bbf7d0',
                  borderRadius: 'var(--radius-md)',
                  padding: '1.25rem',
                  textAlign: 'center',
                }}>
                  <div style={{ fontSize: '0.8rem', color: '#166534', fontWeight: '600', marginBottom: '0.5rem' }}>
                    CONTRASEÑA TEMPORAL GENERADA
                  </div>
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '0.75rem',
                    background: '#ffffff',
                    border: '1px solid #86efac',
                    borderRadius: '6px',
                    padding: '0.6rem 1rem',
                    margin: '0.5rem 0',
                    fontFamily: 'monospace',
                    fontSize: '1.15rem',
                    fontWeight: '700',
                    color: '#0f172a',
                  }}>
                    <span>{tempPassword}</span>
                    <button
                      onClick={copyToClipboard}
                      className="btn-sm btn-secondary"
                      title="Copiar contraseña"
                    >
                      {copied ? <Check size={14} color="#16a34a" /> : <Copy size={14} />}
                    </button>
                  </div>
                  <p style={{ fontSize: '0.75rem', color: '#15803d', marginTop: '0.5rem' }}>
                    Copie y entregue esta clave al usuario de forma segura. No volverá a mostrarse.
                  </p>
                </div>
              ) : (
                <form onSubmit={handleResetPassword}>
                  <div className="form-group">
                    <label className="form-label">Contraseña Temporal Personalizada (Opcional)</label>
                    <PasswordInput
                      placeholder="Dejar en blanco para generar una aleatoria segura"
                      value={customTempPassword}
                      onChange={(e) => setCustomTempPassword(e.target.value)}
                      autoComplete="new-password"
                    />
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '1.5rem' }}>
                    <button
                      type="button"
                      className="btn-secondary"
                      onClick={() => setShowResetModal(false)}
                      disabled={actionLoading}
                    >
                      Cancelar
                    </button>
                    <button
                      type="submit"
                      className="btn-primary"
                      style={{ width: 'auto', padding: '0.6rem 1.25rem' }}
                      disabled={actionLoading}
                    >
                      {actionLoading ? <Loader2 size={16} className="spin" /> : 'Generar Clave Temporal'}
                    </button>
                  </div>
                </form>
              )}
            </div>

            {tempPassword && (
              <div className="modal-footer">
                <button
                  type="button"
                  className="btn-primary"
                  style={{ width: 'auto' }}
                  onClick={() => setShowResetModal(false)}
                >
                  Entendido y Cerrar
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
