import React, { useState, useEffect } from 'react';
import axiosClient from '../api/axiosClient';
import {
  Building2,
  Plus,
  Search,
  Edit2,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Loader2,
  ShieldCheck,
  ShieldAlert,
  Users,
  X,
  RefreshCw,
} from 'lucide-react';

export const EmpresasAdmin = () => {
  const [empresas, setEmpresas] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Filtros
  const [busqueda, setBusqueda] = useState('');
  const [filtroActivo, setFiltroActivo] = useState('');

  // Modales
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showSunatStatusModal, setShowSunatStatusModal] = useState(false);

  // Estados de Formulario
  const [createData, setCreateData] = useState({
    ruc: '',
    razon_social: '',
    activo: true,
  });

  const [selectedEmpresa, setSelectedEmpresa] = useState(null);
  const [editRazonSocial, setEditRazonSocial] = useState('');

  // Estado de Consulta SUNAT Status
  const [sunatStatus, setSunatStatus] = useState(null);
  const [statusLoading, setStatusLoading] = useState(false);

  const [actionLoading, setActionLoading] = useState(false);
  const [modalError, setModalError] = useState('');

  const cargarEmpresas = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await axiosClient.get('/admin/empresas');
      setEmpresas(res.data || []);
    } catch (err) {
      console.error('Error al cargar empresas:', err);
      const msg = err.response?.data?.detail || 'Error al cargar las empresas.';
      setError(typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    cargarEmpresas();
  }, []);

  const handleCrearEmpresa = async (e) => {
    e.preventDefault();
    setModalError('');

    const rucClean = createData.ruc.trim();
    if (!/^\d{11}$/.test(rucClean)) {
      setModalError('El RUC debe tener exactamente 11 dígitos numéricos.');
      return;
    }

    try {
      setActionLoading(true);
      await axiosClient.post('/admin/empresas', {
        ruc: rucClean,
        razon_social: createData.razon_social.trim(),
        activo: true,
      });

      setShowCreateModal(false);
      setCreateData({ ruc: '', razon_social: '', activo: true });
      cargarEmpresas();
    } catch (err) {
      const msg = err.response?.data?.detail || 'Error al crear la empresa.';
      setModalError(typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setActionLoading(false);
    }
  };

  const openEditModal = (emp) => {
    setSelectedEmpresa(emp);
    setEditRazonSocial(emp.razon_social);
    setModalError('');
    setShowEditModal(true);
  };

  const handleEditarEmpresa = async (e) => {
    e.preventDefault();
    setModalError('');

    try {
      setActionLoading(true);
      await axiosClient.put(`/admin/empresas/${selectedEmpresa.id}`, {
        razon_social: editRazonSocial.trim(),
      });

      setShowEditModal(false);
      cargarEmpresas();
    } catch (err) {
      const msg = err.response?.data?.detail || 'Error al actualizar la empresa.';
      setModalError(typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setActionLoading(false);
    }
  };

  const handleToggleEstado = async (emp) => {
    const accion = emp.activo ? 'desactivar' : 'activar';
    if (!window.confirm(`¿Está seguro de que desea ${accion} la empresa ${emp.razon_social}?`)) {
      return;
    }

    try {
      await axiosClient.patch(`/admin/empresas/${emp.id}/estado`, {
        activo: !emp.activo,
      });
      cargarEmpresas();
    } catch (err) {
      const msg = err.response?.data?.detail || 'Error al cambiar estado de la empresa.';
      alert(typeof msg === 'string' ? msg : JSON.stringify(msg));
    }
  };

  const checkSunatStatus = async (emp) => {
    setSelectedEmpresa(emp);
    setSunatStatus(null);
    setShowSunatStatusModal(true);
    setStatusLoading(true);

    try {
      const res = await axiosClient.get(`/admin/empresas/${emp.id}/sunat-status`);
      setSunatStatus(res.data);
    } catch (err) {
      console.error('Error consultando estado SUNAT:', err);
      setSunatStatus({
        configurado: false,
        client_id_configurado: false,
        client_secret_configurado: false,
        error: 'No se pudo obtener el estado operacional de credenciales.',
      });
    } finally {
      setStatusLoading(false);
    }
  };

  const empresasFiltradas = empresas.filter((emp) => {
    if (filtroActivo !== '') {
      const activoBool = filtroActivo === 'true';
      if (emp.activo !== activoBool) return false;
    }
    if (busqueda.trim()) {
      const term = busqueda.toLowerCase();
      const matchRuc = emp.ruc.includes(term);
      const matchRazon = emp.razon_social.toLowerCase().includes(term);
      if (!matchRuc && !matchRazon) return false;
    }
    return true;
  });

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h2 style={{ fontSize: '1.5rem', fontWeight: '700', color: 'var(--color-text-main)', marginBottom: '0.25rem' }}>
            Administración de Empresas
          </h2>
          <p style={{ color: 'var(--color-text-muted)', fontSize: '0.875rem' }}>
            Gestión de entidades tributarias multiempresa y monitoreo de credenciales operacionales SUNAT.
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
          <Plus size={18} />
          <span>Registrar Empresa</span>
        </button>
      </div>

      {error && (
        <div className="login-alert" style={{ marginBottom: '1.5rem' }}>
          {error}
        </div>
      )}

      {/* Filtros */}
      <div className="card" style={{ marginBottom: '1.5rem', padding: '1rem' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '1rem' }}>
          <div>
            <label className="form-label" style={{ fontSize: '0.75rem' }}>Búsqueda por RUC o Razón Social</label>
            <div style={{ position: 'relative' }}>
              <input
                type="text"
                className="form-input"
                placeholder="RUC o nombre de la empresa..."
                value={busqueda}
                onChange={(e) => setBusqueda(e.target.value)}
                style={{ paddingLeft: '2.2rem' }}
              />
              <Search size={16} style={{ position: 'absolute', left: '0.75rem', top: '50%', transform: 'translateY(-50%)', color: '#94a3b8' }} />
            </div>
          </div>

          <div>
            <label className="form-label" style={{ fontSize: '0.75rem' }}>Estado</label>
            <select
              className="form-input"
              value={filtroActivo}
              onChange={(e) => setFiltroActivo(e.target.value)}
            >
              <option value="">Todas las empresas</option>
              <option value="true">Activas</option>
              <option value="false">Inactivas</option>
            </select>
          </div>
        </div>
      </div>

      {/* Tabla de Empresas */}
      <div className="custom-table-container">
        {loading ? (
          <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--color-text-muted)' }}>
            <Loader2 size={32} className="spin" style={{ margin: '0 auto 1rem' }} />
            <p>Cargando empresas registradas...</p>
          </div>
        ) : (
          <table className="custom-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>RUC</th>
                <th>Razón Social</th>
                <th>Usuarios Asignados</th>
                <th>Estado</th>
                <th>Credenciales SUNAT</th>
                <th style={{ textAlign: 'right' }}>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {empresasFiltradas.length === 0 ? (
                <tr>
                  <td colSpan="7" style={{ textAlign: 'center', padding: '2rem', color: '#64748b' }}>
                    No se encontraron empresas con los criterios seleccionados.
                  </td>
                </tr>
              ) : (
                empresasFiltradas.map((emp) => (
                  <tr key={emp.id}>
                    <td style={{ fontWeight: '600', color: '#64748b' }}>#{emp.id}</td>
                    <td style={{ fontFamily: 'monospace', fontWeight: '700', fontSize: '0.9rem' }}>
                      {emp.ruc}
                    </td>
                    <td style={{ fontWeight: '600', color: 'var(--color-text-main)' }}>
                      {emp.razon_social}
                    </td>
                    <td>
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem', color: '#475569', fontWeight: '500' }}>
                        <Users size={14} />
                        {emp.total_usuarios || 0} usuario(s)
                      </span>
                    </td>
                    <td>
                      <span className={`badge ${emp.activo ? 'badge-success' : 'badge-danger'}`}>
                        {emp.activo ? 'Activa' : 'Inactiva'}
                      </span>
                    </td>
                    <td>
                      <button
                        onClick={() => checkSunatStatus(emp)}
                        className="btn-sm btn-action-view"
                        title="Verificar configuración en servidor"
                      >
                        <ShieldCheck size={13} />
                        <span>Verificar SUNAT</span>
                      </button>
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <div style={{ display: 'inline-flex', gap: '0.35rem' }}>
                        <button
                          onClick={() => openEditModal(emp)}
                          className="btn-sm btn-action-edit"
                          title="Editar razón social"
                        >
                          <Edit2 size={13} />
                          <span>Editar</span>
                        </button>

                        <button
                          onClick={() => handleToggleEstado(emp)}
                          className={`btn-sm ${emp.activo ? 'btn-action-status-off' : 'btn-action-status-on'}`}
                          title={emp.activo ? 'Desactivar empresa' : 'Activar empresa'}
                        >
                          {emp.activo ? <XCircle size={13} /> : <CheckCircle2 size={13} />}
                          <span>{emp.activo ? 'Desactivar' : 'Activar'}</span>
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

      {/* Modal Registrar Empresa */}
      {showCreateModal && (
        <div className="modal-overlay">
          <div className="modal-content">
            <div className="modal-header">
              <div className="modal-title">
                <Building2 size={20} color="var(--color-primary)" />
                <span>Registrar Nueva Empresa</span>
              </div>
              <button
                onClick={() => setShowCreateModal(false)}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#94a3b8' }}
              >
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleCrearEmpresa}>
              <div className="modal-body">
                {modalError && (
                  <div className="login-alert" style={{ marginBottom: '1rem' }}>
                    {modalError}
                  </div>
                )}

                <div className="form-group">
                  <label className="form-label">RUC (11 dígitos numéricos)</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="Ej. 20538976815"
                    value={createData.ruc}
                    onChange={(e) => setCreateData({ ...createData, ruc: e.target.value })}
                    maxLength={11}
                    pattern="\d{11}"
                    required
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Razón Social</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="Ej. INVERSIONES & SERVICIOS S.A.C."
                    value={createData.razon_social}
                    onChange={(e) => setCreateData({ ...createData, razon_social: e.target.value })}
                    required
                  />
                </div>

                <div style={{
                  backgroundColor: '#f8fafc',
                  border: '1px solid #e2e8f0',
                  borderRadius: 'var(--radius-sm)',
                  padding: '0.75rem',
                  fontSize: '0.775rem',
                  color: '#64748b',
                  lineHeight: '1.4'
                }}>
                  <strong>Nota sobre credenciales SUNAT:</strong> Por seguridad estricta, las credenciales OAuth2 (Client ID y Client Secret) se gestionan en variables de entorno del servidor (ej. <code>SUNAT_{'{RUC}'}_CLIENT_ID</code>) y nunca se ingresan en texto plano en la base de datos.
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
                  {actionLoading ? <Loader2 size={16} className="spin" /> : 'Registrar Empresa'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal Editar Empresa */}
      {showEditModal && selectedEmpresa && (
        <div className="modal-overlay">
          <div className="modal-content">
            <div className="modal-header">
              <div className="modal-title">
                <Edit2 size={20} color="var(--color-primary)" />
                <span>Editar Empresa RUC {selectedEmpresa.ruc}</span>
              </div>
              <button
                onClick={() => setShowEditModal(false)}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#94a3b8' }}
              >
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleEditarEmpresa}>
              <div className="modal-body">
                {modalError && (
                  <div className="login-alert" style={{ marginBottom: '1rem' }}>
                    {modalError}
                  </div>
                )}

                <div className="form-group">
                  <label className="form-label">RUC (Inmutable)</label>
                  <input
                    type="text"
                    className="form-input"
                    value={selectedEmpresa.ruc}
                    disabled
                    style={{ backgroundColor: '#f1f5f9', cursor: 'not-allowed' }}
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Razón Social</label>
                  <input
                    type="text"
                    className="form-input"
                    value={editRazonSocial}
                    onChange={(e) => setEditRazonSocial(e.target.value)}
                    required
                  />
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

      {/* Modal Estado de Configuración SUNAT */}
      {showSunatStatusModal && selectedEmpresa && (
        <div className="modal-overlay">
          <div className="modal-content">
            <div className="modal-header">
              <div className="modal-title">
                <ShieldCheck size={20} color="var(--color-primary)" />
                <span>Estado de Configuración SUNAT</span>
              </div>
              <button
                onClick={() => setShowSunatStatusModal(false)}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#94a3b8' }}
              >
                <X size={20} />
              </button>
            </div>

            <div className="modal-body">
              <div style={{ marginBottom: '1.25rem' }}>
                <div style={{ fontSize: '0.9rem', fontWeight: '700', color: 'var(--color-text-main)' }}>
                  {selectedEmpresa.razon_social}
                </div>
                <div style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', fontFamily: 'monospace' }}>
                  RUC: {selectedEmpresa.ruc}
                </div>
              </div>

              {statusLoading ? (
                <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--color-text-muted)' }}>
                  <Loader2 size={24} className="spin" style={{ margin: '0 auto 0.5rem' }} />
                  <p style={{ fontSize: '0.85rem' }}>Verificando variables operacionales en servidor...</p>
                </div>
              ) : sunatStatus ? (
                <div>
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.75rem',
                    padding: '1rem',
                    borderRadius: 'var(--radius-md)',
                    backgroundColor: sunatStatus.configurado ? '#f0fdf4' : '#fffbeb',
                    border: `1px solid ${sunatStatus.configurado ? '#bbf7d0' : '#fde68a'}`,
                    marginBottom: '1.25rem',
                  }}>
                    {sunatStatus.configurado ? (
                      <ShieldCheck size={28} color="#16a34a" />
                    ) : (
                      <ShieldAlert size={28} color="#d97706" />
                    )}
                    <div>
                      <div style={{ fontWeight: '700', fontSize: '0.9rem', color: sunatStatus.configurado ? '#166534' : '#92400e' }}>
                        {sunatStatus.configurado
                          ? 'CREDENCIALES COMPLETAMENTE CONFIGURADAS'
                          : 'CONFIGURACIÓN INCOMPLETA EN SERVIDOR'}
                      </div>
                      <div style={{ fontSize: '0.775rem', color: sunatStatus.configurado ? '#15803d' : '#b45309' }}>
                        {sunatStatus.configurado
                          ? 'La empresa cuenta con Client ID y Client Secret válidos para operar con SUNAT.'
                          : 'Falta configurar Client ID o Client Secret en las variables de entorno.'}
                      </div>
                    </div>
                  </div>

                  <div style={{ border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)', overflow: 'hidden' }}>
                    <div style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '0.75rem 1rem',
                      borderBottom: '1px solid var(--color-border)',
                      backgroundColor: '#f8fafc',
                    }}>
                      <span style={{ fontSize: '0.85rem', fontWeight: '500' }}>Client ID (OAuth2)</span>
                      <span className={`badge ${sunatStatus.client_id_configurado ? 'badge-success' : 'badge-danger'}`}>
                        {sunatStatus.client_id_configurado ? 'Configurado' : 'No Configurado'}
                      </span>
                    </div>

                    <div style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '0.75rem 1rem',
                      backgroundColor: '#ffffff',
                    }}>
                      <span style={{ fontSize: '0.85rem', fontWeight: '500' }}>Client Secret (OAuth2)</span>
                      <span className={`badge ${sunatStatus.client_secret_configurado ? 'badge-success' : 'badge-danger'}`}>
                        {sunatStatus.client_secret_configurado ? 'Configurado' : 'No Configurado'}
                      </span>
                    </div>
                  </div>

                  <p style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: '1rem', fontStyle: 'italic' }}>
                    * Por directriz de seguridad zero-knowledge, los valores criptográficos de las credenciales nunca son expuestos ni devueltos por la API.
                  </p>
                </div>
              ) : null}
            </div>

            <div className="modal-footer">
              <button
                type="button"
                className="btn-primary"
                style={{ width: 'auto' }}
                onClick={() => setShowSunatStatusModal(false)}
              >
                Cerrar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
