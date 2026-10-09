import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axiosClient from '../api/axiosClient';
import { useAuth } from '../context/AuthContext';
import { StatusBadge } from '../components/common/StatusBadge';
import { Pagination } from '../components/common/Pagination';
import {
  History,
  Search,
  Filter,
  Calendar,
  RotateCcw,
  Eye,
  FileSpreadsheet,
  AlertCircle,
  Loader2,
  Building2,
  Trash2,
  AlertTriangle,
  X,
  CheckCircle2,
} from 'lucide-react';

export const Historial = () => {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [procesos, setProcesos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Estado para modal de eliminación de lote de prueba
  const [loteAEliminar, setLoteAEliminar] = useState(null);
  const [eliminando, setEliminando] = useState(false);
  const [mensajeExito, setMensajeExito] = useState('');
  const [errorEliminar, setErrorEliminar] = useState('');

  // Paginación
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [totalItems, setTotalItems] = useState(0);
  const [totalPages, setTotalPages] = useState(1);

  // Filtros
  const [nombreArchivo, setNombreArchivo] = useState('');
  const [estado, setEstado] = useState('');
  const [fechaDesde, setFechaDesde] = useState('');
  const [fechaHasta, setFechaHasta] = useState('');

  const handleConfirmarEliminar = async () => {
    if (!loteAEliminar) return;
    setEliminando(true);
    setErrorEliminar('');
    try {
      await axiosClient.delete(`/procesos-masivos/${loteAEliminar.id}`);
      setLoteAEliminar(null);
      setMensajeExito('Lote eliminado correctamente.');
      setTimeout(() => setMensajeExito(''), 4500);
      cargarHistorial();
    } catch (err) {
      console.error('Error al eliminar lote:', err);
      const msg = err.response?.data?.detail || 'Error al eliminar el lote de prueba.';
      setErrorEliminar(msg);
    } finally {
      setEliminando(false);
    }
  };

  const cargarHistorial = async () => {
    try {
      setLoading(true);
      setError(null);

      const params = {
        page,
        page_size: pageSize,
      };
      if (nombreArchivo.trim()) params.nombre_archivo = nombreArchivo.trim();
      if (estado) params.estado = estado;
      if (fechaDesde) params.fecha_desde = fechaDesde;
      if (fechaHasta) params.fecha_hasta = fechaHasta;

      const res = await axiosClient.get('/procesos-masivos', { params });
      setProcesos(res.data.items || []);
      setTotalItems(res.data.total || 0);
      setTotalPages(res.data.total_pages || 1);
    } catch (err) {
      console.error('Error al cargar historial de procesos:', err);
      const msg = err.response?.data?.detail || 'Error al cargar el historial de procesos masivos.';
      setError(typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    cargarHistorial();
  }, [page, pageSize]);

  const handleBuscar = (e) => {
    e.preventDefault();
    setPage(1);
    cargarHistorial();
  };

  const handleLimpiarFiltros = () => {
    setNombreArchivo('');
    setEstado('');
    setFechaDesde('');
    setFechaHasta('');
    setPage(1);
    setTimeout(() => {
      cargarHistorial();
    }, 50);
  };

  const empresaNombre = user?.empresa?.razon_social || 'Empresa';
  const empresaRuc = user?.empresa?.ruc || '-';

  return (
    <div style={{ maxWidth: '1440px', margin: '0 auto', padding: '1.5rem' }}>
      {/* Encabezado */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '1rem',
          marginBottom: '1.5rem',
        }}
      >
        <div>
          <h2
            style={{
              fontSize: '1.5rem',
              fontWeight: '700',
              color: 'var(--color-text-main, #0f172a)',
              margin: '0 0 0.25rem 0',
              display: 'flex',
              alignItems: 'center',
              gap: '0.6rem',
            }}
          >
            <History size={24} color="var(--color-primary, #1e40af)" />
            <span>Historial de Procesos Masivos</span>
          </h2>
          <p style={{ color: 'var(--color-text-muted, #64748b)', fontSize: '0.875rem', margin: 0 }}>
            Registro cronológico de lotes de Registro de Compras validados ante SUNAT para{' '}
            <strong>{empresaNombre}</strong> (RUC: {empresaRuc})
          </p>
        </div>
      </div>

      {/* Alerta de Error */}
      {error && (
        <div
          style={{
            backgroundColor: '#fef2f2',
            border: '1px solid #fecaca',
            color: '#991b1b',
            padding: '1rem',
            borderRadius: '8px',
            marginBottom: '1.5rem',
            display: 'flex',
            alignItems: 'center',
            gap: '0.75rem',
          }}
        >
          <AlertCircle size={20} />
          <span>{error}</span>
        </div>
      )}

      {/* Alerta de Éxito al eliminar lote */}
      {mensajeExito && (
        <div
          style={{
            marginBottom: '1.25rem',
            padding: '0.85rem 1.25rem',
            backgroundColor: '#f0fdf4',
            border: '1px solid #bbf7d0',
            borderRadius: '8px',
            color: '#15803d',
            fontSize: '0.875rem',
            fontWeight: '600',
            display: 'flex',
            alignItems: 'center',
            gap: '0.6rem',
            boxShadow: '0 1px 2px rgba(0, 0, 0, 0.05)',
          }}
        >
          <CheckCircle2 size={18} color="#16a34a" />
          <span>{mensajeExito}</span>
        </div>
      )}

      {/* Barra de Filtros */}
      <div
        className="card"
        style={{
          padding: '1rem 1.25rem',
          marginBottom: '1.5rem',
          backgroundColor: '#ffffff',
          borderRadius: '8px',
          border: '1px solid var(--color-border, #e2e8f0)',
        }}
      >
        <form onSubmit={handleBuscar}>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
              gap: '1rem',
              alignItems: 'flex-end',
            }}
          >
            <div>
              <label
                style={{
                  display: 'block',
                  fontSize: '0.75rem',
                  fontWeight: '600',
                  color: '#475569',
                  marginBottom: '0.35rem',
                }}
              >
                Nombre del Archivo
              </label>
              <input
                type="text"
                placeholder="Buscar por archivo..."
                value={nombreArchivo}
                onChange={(e) => setNombreArchivo(e.target.value)}
                style={{
                  width: '100%',
                  padding: '0.45rem 0.75rem',
                  fontSize: '0.825rem',
                  border: '1px solid #cbd5e1',
                  borderRadius: '6px',
                  outline: 'none',
                }}
              />
            </div>

            <div>
              <label
                style={{
                  display: 'block',
                  fontSize: '0.75rem',
                  fontWeight: '600',
                  color: '#475569',
                  marginBottom: '0.35rem',
                }}
              >
                Estado del Proceso
              </label>
              <select
                value={estado}
                onChange={(e) => setEstado(e.target.value)}
                style={{
                  width: '100%',
                  padding: '0.45rem 0.75rem',
                  fontSize: '0.825rem',
                  border: '1px solid #cbd5e1',
                  borderRadius: '6px',
                  backgroundColor: '#ffffff',
                  outline: 'none',
                }}
              >
                <option value="">Todos los estados</option>
                <option value="COMPLETADO">COMPLETADO</option>
                <option value="COMPLETADO_CON_ERRORES">COMPLETADO CON ERRORES</option>
                <option value="PROCESANDO">PROCESANDO</option>
                <option value="PENDIENTE">PENDIENTE</option>
                <option value="ERROR">ERROR</option>
              </select>
            </div>

            <div>
              <label
                style={{
                  display: 'block',
                  fontSize: '0.75rem',
                  fontWeight: '600',
                  color: '#475569',
                  marginBottom: '0.35rem',
                }}
              >
                Fecha Desde
              </label>
              <input
                type="date"
                value={fechaDesde}
                onChange={(e) => setFechaDesde(e.target.value)}
                style={{
                  width: '100%',
                  padding: '0.45rem 0.75rem',
                  fontSize: '0.825rem',
                  border: '1px solid #cbd5e1',
                  borderRadius: '6px',
                  outline: 'none',
                }}
              />
            </div>

            <div>
              <label
                style={{
                  display: 'block',
                  fontSize: '0.75rem',
                  fontWeight: '600',
                  color: '#475569',
                  marginBottom: '0.35rem',
                }}
              >
                Fecha Hasta
              </label>
              <input
                type="date"
                value={fechaHasta}
                onChange={(e) => setFechaHasta(e.target.value)}
                style={{
                  width: '100%',
                  padding: '0.45rem 0.75rem',
                  fontSize: '0.825rem',
                  border: '1px solid #cbd5e1',
                  borderRadius: '6px',
                  outline: 'none',
                }}
              />
            </div>

            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              <button
                type="submit"
                className="btn-primary"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.4rem',
                  padding: '0.5rem 1rem',
                  fontSize: '0.825rem',
                  fontWeight: '600',
                  borderRadius: '6px',
                  border: 'none',
                  backgroundColor: 'var(--color-primary, #1e40af)',
                  color: '#ffffff',
                  cursor: 'pointer',
                }}
              >
                <Filter size={15} />
                <span>Filtrar</span>
              </button>

              <button
                type="button"
                onClick={handleLimpiarFiltros}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.4rem',
                  padding: '0.5rem 0.85rem',
                  fontSize: '0.825rem',
                  borderRadius: '6px',
                  border: '1px solid #cbd5e1',
                  backgroundColor: '#f8fafc',
                  color: '#64748b',
                  cursor: 'pointer',
                }}
              >
                <RotateCcw size={14} />
                <span>Limpiar</span>
              </button>
            </div>
          </div>
        </form>
      </div>

      {/* Tabla de Procesos Masivos */}
      <div
        className="card"
        style={{
          padding: 0,
          backgroundColor: '#ffffff',
          borderRadius: '8px',
          border: '1px solid var(--color-border, #e2e8f0)',
          overflow: 'hidden',
          boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
        }}
      >
        <div style={{ overflowX: 'auto' }}>
          <table
            style={{
              width: '100%',
              borderCollapse: 'collapse',
              fontSize: '0.825rem',
              textAlign: 'left',
            }}
          >
            <thead>
              <tr
                style={{
                  backgroundColor: '#f8fafc',
                  color: '#475569',
                  borderBottom: '1px solid #e2e8f0',
                  fontWeight: '600',
                }}
              >
                <th style={{ padding: '0.75rem 1rem' }}>FECHA Y HORA</th>
                <th style={{ padding: '0.75rem 1rem' }}>ARCHIVO ORIGEN</th>
                <th style={{ padding: '0.75rem 0.75rem', textAlign: 'center' }}>TOTAL</th>
                <th style={{ padding: '0.75rem 0.75rem', textAlign: 'center', color: '#16a34a' }}>
                  VÁLIDOS
                </th>
                <th style={{ padding: '0.75rem 0.75rem', textAlign: 'center', color: '#dc2626' }}>
                  NO VÁLIDOS
                </th>
                <th style={{ padding: '0.75rem 0.75rem', textAlign: 'center', color: '#d97706' }}>
                  OBSERVADOS
                </th>
                <th style={{ padding: '0.75rem 0.75rem', textAlign: 'center', color: '#991b1b' }}>
                  ERRORES
                </th>
                <th style={{ padding: '0.75rem 1rem', textAlign: 'center' }}>ESTADO</th>
                <th style={{ padding: '0.75rem 0.75rem', textAlign: 'center' }}>AVANCE</th>
                <th style={{ padding: '0.75rem 1rem' }}>USUARIO</th>
                <th style={{ padding: '0.75rem 1rem', textAlign: 'center' }}>ACCIONES</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={11} style={{ padding: '3rem', textAlign: 'center', color: '#64748b' }}>
                    <div
                      style={{
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        gap: '0.5rem',
                      }}
                    >
                      <Loader2 size={28} className="spin" color="var(--color-primary, #1e40af)" />
                      <span>Cargando historial de validaciones...</span>
                    </div>
                  </td>
                </tr>
              ) : procesos.length === 0 ? (
                <tr>
                  <td colSpan={11} style={{ padding: '3rem', textAlign: 'center', color: '#64748b' }}>
                    <div
                      style={{
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        gap: '0.5rem',
                      }}
                    >
                      <FileSpreadsheet size={32} color="#94a3b8" />
                      <strong>No se encontraron procesos masivos registrados.</strong>
                      <span style={{ fontSize: '0.78rem', color: '#94a3b8' }}>
                        Cargue un archivo de compras en formato Excel (.xlsx) desde la sección "Carga
                        masiva Excel".
                      </span>
                    </div>
                  </td>
                </tr>
              ) : (
                procesos.map((p) => {
                  const fechaStr = p.created_at
                    ? new Date(p.created_at).toLocaleString('es-PE', {
                        dateStyle: 'short',
                        timeStyle: 'short',
                      })
                    : '-';
                  return (
                    <tr
                      key={p.id}
                      style={{
                        borderBottom: '1px solid #f1f5f9',
                        transition: 'background-color 0.15s ease',
                      }}
                    >
                      <td style={{ padding: '0.75rem 1rem', whiteSpace: 'nowrap' }}>
                        <span style={{ fontWeight: '600', color: '#1e293b' }}>{fechaStr}</span>
                      </td>
                      <td style={{ padding: '0.75rem 1rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          <FileSpreadsheet size={16} color="#0284c7" />
                          <span style={{ fontWeight: '500', color: '#0f172a' }}>
                            {p.nombre_archivo || 'Lote sin nombre'}
                          </span>
                        </div>
                      </td>
                      <td
                        style={{
                          padding: '0.75rem 0.75rem',
                          textAlign: 'center',
                          fontWeight: '700',
                          color: '#0f172a',
                        }}
                      >
                        {p.total_registros}
                      </td>
                      <td
                        style={{
                          padding: '0.75rem 0.75rem',
                          textAlign: 'center',
                          fontWeight: '700',
                          color: '#15803d',
                        }}
                      >
                        {p.total_validos}
                      </td>
                      <td
                        style={{
                          padding: '0.75rem 0.75rem',
                          textAlign: 'center',
                          fontWeight: '700',
                          color: '#dc2626',
                        }}
                      >
                        {p.total_no_validos}
                      </td>
                      <td
                        style={{
                          padding: '0.75rem 0.75rem',
                          textAlign: 'center',
                          fontWeight: '700',
                          color: '#d97706',
                        }}
                      >
                        {p.total_observados}
                      </td>
                      <td
                        style={{
                          padding: '0.75rem 0.75rem',
                          textAlign: 'center',
                          fontWeight: '700',
                          color: '#991b1b',
                        }}
                      >
                        {p.total_errores}
                      </td>
                      <td style={{ padding: '0.75rem 1rem', textAlign: 'center' }}>
                        <StatusBadge estado={p.estado} size="sm" />
                      </td>
                      <td style={{ padding: '0.75rem 0.75rem', textAlign: 'center' }}>
                        <span
                          style={{
                            fontWeight: '700',
                            fontSize: '0.8rem',
                            color:
                              p.estado === 'COMPLETADO'
                                ? '#15803d'
                                : 'var(--color-primary, #1e40af)',
                          }}
                        >
                          {p.porcentaje}%
                        </span>
                      </td>
                      <td style={{ padding: '0.75rem 1rem', color: '#64748b' }}>
                        <span style={{ fontSize: '0.8rem' }}>
                          {p.usuario_nombre || 'Contador'}
                        </span>
                      </td>
                      <td style={{ padding: '0.75rem 1rem', textAlign: 'center' }}>
                        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', justifyContent: 'center' }}>
                          <button
                            onClick={() => navigate(`/historial/${p.id}`)}
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '0.35rem',
                              padding: '0.4rem 0.75rem',
                              fontSize: '0.785rem',
                              fontWeight: '600',
                              borderRadius: '6px',
                              border: '1px solid #cbd5e1',
                              backgroundColor: '#ffffff',
                              color: 'var(--color-primary, #1e40af)',
                              cursor: 'pointer',
                              transition: 'all 0.15s ease',
                            }}
                            title="Ver detalle y resultados del proceso"
                          >
                            <Eye size={14} />
                            <span>Ver resultados</span>
                          </button>
                          <button
                            onClick={() => {
                              setErrorEliminar('');
                              setLoteAEliminar(p);
                            }}
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '0.3rem',
                              padding: '0.4rem 0.65rem',
                              fontSize: '0.785rem',
                              fontWeight: '600',
                              borderRadius: '6px',
                              border: '1px solid #fecaca',
                              backgroundColor: '#fef2f2',
                              color: '#dc2626',
                              cursor: 'pointer',
                              transition: 'all 0.15s ease',
                            }}
                            title="Eliminar lote de prueba"
                          >
                            <Trash2 size={13} />
                            <span>Eliminar</span>
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Paginación */}
        <Pagination
          page={page}
          totalPages={totalPages}
          totalItems={totalItems}
          pageSize={pageSize}
          onPageChange={(newPage) => setPage(newPage)}
          onPageSizeChange={(newSize) => {
            setPageSize(newSize);
            setPage(1);
          }}
        />
      </div>

      {/* Modal de Confirmación para Eliminar Lote de Prueba */}
      {loteAEliminar && (
        <div className="modal-overlay" style={{ zIndex: 1100 }}>
          <div className="modal-content" style={{ maxWidth: '460px' }}>
            <div className="modal-header">
              <div className="modal-title" style={{ color: '#b91c1c' }}>
                <AlertTriangle size={20} color="#dc2626" />
                <span>Eliminar lote de prueba</span>
              </div>
              <button
                onClick={() => !eliminando && setLoteAEliminar(null)}
                disabled={eliminando}
                style={{
                  background: 'none',
                  border: 'none',
                  cursor: eliminando ? 'not-allowed' : 'pointer',
                  color: '#64748b',
                }}
              >
                <X size={18} />
              </button>
            </div>

            <div className="modal-body">
              {errorEliminar && (
                <div
                  style={{
                    padding: '0.75rem',
                    marginBottom: '1rem',
                    backgroundColor: '#fef2f2',
                    border: '1px solid #fecaca',
                    borderRadius: '6px',
                    color: '#991b1b',
                    fontSize: '0.825rem',
                  }}
                >
                  {errorEliminar}
                </div>
              )}

              <div
                style={{
                  marginBottom: '1.25rem',
                  backgroundColor: '#f8fafc',
                  padding: '0.85rem 1rem',
                  borderRadius: '6px',
                  border: '1px solid #e2e8f0',
                }}
              >
                <div style={{ marginBottom: '0.5rem', fontSize: '0.825rem', color: '#475569' }}>
                  <span style={{ display: 'block', color: '#64748b', fontSize: '0.75rem' }}>Archivo:</span>
                  <strong style={{ color: '#0f172a' }}>{loteAEliminar.nombre_archivo || 'Lote sin nombre'}</strong>
                </div>
                <div style={{ fontSize: '0.825rem', color: '#475569' }}>
                  <span style={{ display: 'block', color: '#64748b', fontSize: '0.75rem' }}>Comprobantes:</span>
                  <strong style={{ color: '#0f172a' }}>{loteAEliminar.total_registros}</strong>
                </div>
              </div>

              <p style={{ margin: '0 0 0.5rem 0', fontSize: '0.85rem', color: '#334155' }}>
                Esta acción eliminará este lote y sus registros asociados.
              </p>
              <p style={{ margin: 0, fontSize: '0.825rem', color: '#dc2626', fontWeight: '600' }}>
                Esta acción no se puede deshacer.
              </p>
            </div>

            <div className="modal-footer">
              <button
                type="button"
                disabled={eliminando}
                onClick={() => setLoteAEliminar(null)}
                style={{
                  padding: '0.5rem 1rem',
                  borderRadius: '6px',
                  border: '1px solid #cbd5e1',
                  backgroundColor: '#ffffff',
                  color: '#334155',
                  fontSize: '0.825rem',
                  fontWeight: '600',
                  cursor: eliminando ? 'not-allowed' : 'pointer',
                }}
              >
                Cancelar
              </button>
              <button
                type="button"
                disabled={eliminando}
                onClick={handleConfirmarEliminar}
                style={{
                  padding: '0.5rem 1.1rem',
                  borderRadius: '6px',
                  border: 'none',
                  backgroundColor: '#dc2626',
                  color: '#ffffff',
                  fontSize: '0.825rem',
                  fontWeight: '600',
                  cursor: eliminando ? 'not-allowed' : 'pointer',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.4rem',
                  boxShadow: '0 1px 2px rgba(220, 38, 38, 0.2)',
                }}
              >
                {eliminando ? <Loader2 size={15} className="spin" /> : <Trash2 size={15} />}
                <span>{eliminando ? 'Eliminando...' : 'Eliminar lote'}</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
