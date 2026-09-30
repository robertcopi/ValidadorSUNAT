import React, { useState, useEffect } from 'react';
import axiosClient from '../api/axiosClient';
import { Pagination } from '../components/common/Pagination';
import {
  ShieldAlert,
  Search,
  Filter,
  Calendar,
  RotateCcw,
  Eye,
  Loader2,
  FileText,
  Clock,
  User,
  Building2,
  Activity,
  X,
} from 'lucide-react';

const ACCION_BADGE_MAP = {
  LOGIN_EXITOSO: 'badge-success',
  LOGIN_FALLIDO: 'badge-danger',
  CAMBIO_PASSWORD: 'badge-info',
  RESET_PASSWORD: 'badge-warning',
  USUARIO_CREADO: 'badge-info',
  USUARIO_EDITADO: 'badge-warning',
  USUARIO_ACTIVADO: 'badge-success',
  USUARIO_DESACTIVADO: 'badge-danger',
  EMPRESA_CREADA: 'badge-info',
  EMPRESA_EDITADA: 'badge-warning',
  PROCESO_MASIVO_CREADO: 'badge-info',
  REINTENTO_PROCESO: 'badge-warning',
  EXPORTACION_EXCEL: 'badge-success',
};

export const AuditoriaAdmin = () => {
  const [eventos, setEventos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Paginación
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [totalItems, setTotalItems] = useState(0);
  const [totalPages, setTotalPages] = useState(1);

  // Filtros
  const [accion, setAccion] = useState('');
  const [fechaDesde, setFechaDesde] = useState('');
  const [fechaHasta, setFechaHasta] = useState('');

  // Modal Detalle
  const [selectedEvento, setSelectedEvento] = useState(null);

  const cargarAuditoria = async () => {
    try {
      setLoading(true);
      setError(null);

      const params = {
        page,
        page_size: pageSize,
      };
      if (accion) params.accion = accion;
      if (fechaDesde) params.fecha_desde = new Date(fechaDesde).toISOString();
      if (fechaHasta) {
        const hasta = new Date(fechaHasta);
        hasta.setHours(23, 59, 59, 999);
        params.fecha_hasta = hasta.toISOString();
      }

      const res = await axiosClient.get('/admin/auditoria', { params });
      setEventos(res.data.items || []);
      setTotalItems(res.data.total || 0);
      setTotalPages(res.data.total_pages || 1);
    } catch (err) {
      console.error('Error al cargar auditoría:', err);
      const msg = err.response?.data?.detail || 'Error al cargar los registros de auditoría.';
      setError(typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    cargarAuditoria();
  }, [page, pageSize]);

  const handleBuscar = (e) => {
    e.preventDefault();
    setPage(1);
    cargarAuditoria();
  };

  const handleLimpiarFiltros = () => {
    setAccion('');
    setFechaDesde('');
    setFechaHasta('');
    setPage(1);
  };

  const formatearFecha = (isoStr) => {
    if (!isoStr) return '-';
    const d = new Date(isoStr);
    return d.toLocaleString('es-PE', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  return (
    <div>
      <div style={{ marginBottom: '1.5rem' }}>
        <h2 style={{ fontSize: '1.5rem', fontWeight: '700', color: 'var(--color-text-main)', marginBottom: '0.25rem' }}>
          Visor de Auditoría Operacional
        </h2>
        <p style={{ color: 'var(--color-text-muted)', fontSize: '0.875rem' }}>
          Registro cronológico e inmutable de eventos críticos, accesos y operaciones en el sistema.
        </p>
      </div>

      {error && (
        <div className="login-alert" style={{ marginBottom: '1.5rem' }}>
          {error}
        </div>
      )}

      {/* Filtros */}
      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <form onSubmit={handleBuscar}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', alignItems: 'flex-end' }}>
            <div>
              <label className="form-label" style={{ fontSize: '0.75rem' }}>Acción Auditada</label>
              <select
                className="form-input"
                value={accion}
                onChange={(e) => setAccion(e.target.value)}
              >
                <option value="">Todas las acciones</option>
                <option value="LOGIN_EXITOSO">LOGIN_EXITOSO</option>
                <option value="LOGIN_FALLIDO">LOGIN_FALLIDO</option>
                <option value="CAMBIO_PASSWORD">CAMBIO_PASSWORD</option>
                <option value="RESET_PASSWORD">RESET_PASSWORD</option>
                <option value="USUARIO_CREADO">USUARIO_CREADO</option>
                <option value="USUARIO_EDITADO">USUARIO_EDITADO</option>
                <option value="USUARIO_ACTIVADO">USUARIO_ACTIVADO</option>
                <option value="USUARIO_DESACTIVADO">USUARIO_DESACTIVADO</option>
                <option value="EMPRESA_CREADA">EMPRESA_CREADA</option>
                <option value="EMPRESA_EDITADA">EMPRESA_EDITADA</option>
                <option value="PROCESO_MASIVO_CREADO">PROCESO_MASIVO_CREADO</option>
                <option value="REINTENTO_PROCESO">REINTENTO_PROCESO</option>
                <option value="EXPORTACION_EXCEL">EXPORTACION_EXCEL</option>
              </select>
            </div>

            <div>
              <label className="form-label" style={{ fontSize: '0.75rem' }}>Fecha Desde</label>
              <input
                type="date"
                className="form-input"
                value={fechaDesde}
                onChange={(e) => setFechaDesde(e.target.value)}
              />
            </div>

            <div>
              <label className="form-label" style={{ fontSize: '0.75rem' }}>Fecha Hasta</label>
              <input
                type="date"
                className="form-input"
                value={fechaHasta}
                onChange={(e) => setFechaHasta(e.target.value)}
              />
            </div>

            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button
                type="submit"
                className="btn-primary"
                style={{ width: 'auto', padding: '0.65rem 1rem' }}
              >
                <Search size={16} />
                <span>Filtrar</span>
              </button>

              <button
                type="button"
                className="btn-secondary"
                onClick={handleLimpiarFiltros}
                title="Limpiar filtros"
              >
                <RotateCcw size={16} />
              </button>
            </div>
          </div>
        </form>
      </div>

      {/* Tabla de Auditoría */}
      <div className="custom-table-container">
        {loading ? (
          <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--color-text-muted)' }}>
            <Loader2 size={32} className="spin" style={{ margin: '0 auto 1rem' }} />
            <p>Cargando registros de auditoría...</p>
          </div>
        ) : (
          <>
            <table className="custom-table">
              <thead>
                <tr>
                  <th>Fecha y Hora</th>
                  <th>Acción</th>
                  <th>Entidad</th>
                  <th>Usuario</th>
                  <th>Empresa</th>
                  <th>IP</th>
                  <th style={{ textAlign: 'right' }}>Detalle</th>
                </tr>
              </thead>
              <tbody>
                {eventos.length === 0 ? (
                  <tr>
                    <td colSpan="7" style={{ textAlign: 'center', padding: '2.5rem', color: '#64748b' }}>
                      No se encontraron eventos de auditoría con los criterios indicados.
                    </td>
                  </tr>
                ) : (
                  eventos.map((ev) => (
                    <tr key={ev.id}>
                      <td style={{ whiteSpace: 'nowrap', fontSize: '0.8rem', color: '#475569' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                          <Clock size={13} color="#94a3b8" />
                          <span>{formatearFecha(ev.created_at)}</span>
                        </div>
                      </td>
                      <td>
                        <span className={`badge ${ACCION_BADGE_MAP[ev.accion] || 'badge-info'}`}>
                          {ev.accion}
                        </span>
                      </td>
                      <td>
                        <span style={{ fontWeight: '500', color: '#334155' }}>
                          {ev.entidad} {ev.entidad_id ? `(#${ev.entidad_id})` : ''}
                        </span>
                      </td>
                      <td>
                        {ev.usuario_nombre ? (
                          <div>
                            <div style={{ fontWeight: '600', fontSize: '0.85rem' }}>{ev.usuario_nombre}</div>
                            <div style={{ fontSize: '0.725rem', color: 'var(--color-text-muted)' }}>{ev.usuario_email}</div>
                          </div>
                        ) : (
                          <span style={{ color: '#94a3b8', fontStyle: 'italic' }}>Sistema / Anónimo</span>
                        )}
                      </td>
                      <td>
                        {ev.empresa_razon_social ? (
                          <span style={{ fontSize: '0.825rem', color: '#334155' }}>
                            {ev.empresa_razon_social}
                          </span>
                        ) : (
                          <span style={{ color: '#94a3b8', fontSize: '0.8rem' }}>N/A</span>
                        )}
                      </td>
                      <td>
                        <span style={{ fontFamily: 'monospace', fontSize: '0.775rem', color: '#64748b' }}>
                          {ev.ip || '-'}
                        </span>
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <button
                          onClick={() => setSelectedEvento(ev)}
                          className="btn-sm btn-action-view"
                          title="Ver detalle del evento"
                        >
                          <Eye size={13} />
                          <span>Ver</span>
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>

            {/* Paginación */}
            {totalPages > 0 && (
              <div style={{ padding: '0.75rem 1rem', borderTop: '1px solid var(--color-border)', backgroundColor: '#f8fafc' }}>
                <Pagination
                  currentPage={page}
                  totalPages={totalPages}
                  totalItems={totalItems}
                  pageSize={pageSize}
                  onPageChange={setPage}
                  onPageSizeChange={(newSize) => {
                    setPageSize(newSize);
                    setPage(1);
                  }}
                  pageSizeOptions={[10, 20, 50, 100]}
                />
              </div>
            )}
          </>
        )}
      </div>

      {/* Modal Detalle de Evento */}
      {selectedEvento && (
        <div className="modal-overlay">
          <div className="modal-content" style={{ maxWidth: '600px' }}>
            <div className="modal-header">
              <div className="modal-title">
                <FileText size={20} color="var(--color-primary)" />
                <span>Detalle de Evento #{selectedEvento.id}</span>
              </div>
              <button
                onClick={() => setSelectedEvento(null)}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#94a3b8' }}
              >
                <X size={20} />
              </button>
            </div>

            <div className="modal-body">
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.75rem', marginBottom: '1.25rem' }}>
                <div>
                  <label className="form-label" style={{ fontSize: '0.725rem', color: '#64748b' }}>Acción</label>
                  <span className={`badge ${ACCION_BADGE_MAP[selectedEvento.accion] || 'badge-info'}`}>
                    {selectedEvento.accion}
                  </span>
                </div>

                <div>
                  <label className="form-label" style={{ fontSize: '0.725rem', color: '#64748b' }}>Fecha de Registro</label>
                  <span style={{ fontSize: '0.85rem', fontWeight: '500' }}>
                    {formatearFecha(selectedEvento.created_at)}
                  </span>
                </div>

                <div>
                  <label className="form-label" style={{ fontSize: '0.725rem', color: '#64748b' }}>Usuario Ejecutor</label>
                  <span style={{ fontSize: '0.85rem', fontWeight: '500' }}>
                    {selectedEvento.usuario_nombre || 'Sistema / Anónimo'}
                  </span>
                </div>

                <div>
                  <label className="form-label" style={{ fontSize: '0.725rem', color: '#64748b' }}>Dirección IP</label>
                  <span style={{ fontSize: '0.85rem', fontFamily: 'monospace' }}>
                    {selectedEvento.ip || 'N/A'}
                  </span>
                </div>
              </div>

              <div>
                <label className="form-label" style={{ fontSize: '0.75rem', color: '#64748b' }}>
                  Datos Sanitizados del Evento (JSON Seguro)
                </label>
                <pre style={{
                  backgroundColor: '#0f172a',
                  color: '#f8fafc',
                  padding: '1rem',
                  borderRadius: 'var(--radius-sm)',
                  fontSize: '0.8rem',
                  overflowX: 'auto',
                  fontFamily: 'monospace',
                }}>
                  {JSON.stringify(selectedEvento.detalle || {}, null, 2)}
                </pre>
              </div>
            </div>

            <div className="modal-footer">
              <button
                type="button"
                className="btn-primary"
                style={{ width: 'auto' }}
                onClick={() => setSelectedEvento(null)}
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
