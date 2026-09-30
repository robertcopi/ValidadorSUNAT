import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axiosClient from '../api/axiosClient';
import { useAuth } from '../context/AuthContext';
import { StatusBadge } from '../components/common/StatusBadge';
import { Pagination } from '../components/common/Pagination';
import { ProcessSummary } from '../components/common/ProcessSummary';
import {
  ArrowLeft,
  Download,
  FileSpreadsheet,
  Search,
  Filter,
  RotateCcw,
  AlertCircle,
  Loader2,
  Calendar,
  Building2,
  RefreshCw,
} from 'lucide-react';

export const DetalleProceso = () => {
  const { procesoId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();

  const [proceso, setProceso] = useState(null);
  const [items, setItems] = useState([]);
  const [loadingProceso, setLoadingProceso] = useState(true);
  const [loadingItems, setLoadingItems] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState(null);

  // Paginación
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [totalItems, setTotalItems] = useState(0);
  const [totalPages, setTotalPages] = useState(1);

  // Filtros
  const [busqueda, setBusqueda] = useState('');
  const [filtroEstado, setFiltroEstado] = useState('');
  const [filtroRuc, setFiltroRuc] = useState('');
  const [filtroRazonSocial, setFiltroRazonSocial] = useState('');
  const [filtroSerie, setFiltroSerie] = useState('');
  const [filtroNumero, setFiltroNumero] = useState('');

  // 1. Cargar cabecera del proceso
  const cargarProceso = async () => {
    try {
      setLoadingProceso(true);
      setError(null);
      const res = await axiosClient.get(`/procesos-masivos/${procesoId}`);
      setProceso(res.data);
    } catch (err) {
      console.error('Error al cargar proceso:', err);
      const msg = err.response?.data?.detail || 'No fue posible cargar el detalle del proceso.';
      setError(typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setLoadingProceso(false);
    }
  };

  // 2. Cargar items paginados y filtrados
  const cargarItems = async () => {
    try {
      setLoadingItems(true);
      const params = {
        page,
        page_size: pageSize,
      };
      if (busqueda.trim()) params.busqueda = busqueda.trim();
      if (filtroEstado) params.estado = filtroEstado;
      if (filtroRuc.trim()) params.ruc = filtroRuc.trim();
      if (filtroRazonSocial.trim()) params.razon_social = filtroRazonSocial.trim();
      if (filtroSerie.trim()) params.serie = filtroSerie.trim();
      if (filtroNumero.trim()) params.numero = filtroNumero.trim();

      const res = await axiosClient.get(`/procesos-masivos/${procesoId}/items`, { params });
      setItems(res.data.items || []);
      setTotalItems(res.data.total || 0);
      setTotalPages(res.data.total_pages || 1);
    } catch (err) {
      console.error('Error al cargar items del proceso:', err);
    } finally {
      setLoadingItems(false);
    }
  };

  useEffect(() => {
    cargarProceso();
  }, [procesoId]);

  useEffect(() => {
    cargarItems();
  }, [procesoId, page, pageSize]);

  const handleBuscar = (e) => {
    e.preventDefault();
    setPage(1);
    cargarItems();
  };

  const handleLimpiarFiltros = () => {
    setBusqueda('');
    setFiltroEstado('');
    setFiltroRuc('');
    setFiltroRazonSocial('');
    setFiltroSerie('');
    setFiltroNumero('');
    setPage(1);
    setTimeout(() => {
      cargarItems();
    }, 50);
  };

  // 3. Descargar Excel con JWT
  const handleExportarExcel = async () => {
    if (exporting) return;
    try {
      setExporting(true);
      const response = await axiosClient.get(`/procesos-masivos/${procesoId}/exportar`, {
        responseType: 'blob',
      });

      // Extraer nombre de archivo desde cabecera Content-Disposition si existe
      let filename = `resultado_sunat_${proceso?.nombre_archivo || procesoId}.xlsx`;
      const disposition = response.headers['content-disposition'];
      if (disposition && disposition.includes('filename=')) {
        const matches = disposition.match(/filename="?([^";]+)"?/);
        if (matches && matches[1]) {
          filename = matches[1];
        }
      }

      // Crear URL temporal para descarga de archivo binario
      const blob = new Blob([response.data], {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Error al exportar archivo Excel:', err);
      alert('Ocurrió un error al descargar el reporte Excel. Intente nuevamente.');
    } finally {
      setExporting(false);
    }
  };

  return (
    <div style={{ maxWidth: '1440px', margin: '0 auto', padding: '1.5rem' }}>
      {/* Botón Volver y Cabecera */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '1rem',
          marginBottom: '1.25rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <button
            onClick={() => navigate('/historial')}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.4rem',
              padding: '0.45rem 0.85rem',
              borderRadius: '6px',
              border: '1px solid #cbd5e1',
              backgroundColor: '#ffffff',
              color: '#475569',
              fontSize: '0.825rem',
              fontWeight: '600',
              cursor: 'pointer',
            }}
          >
            <ArrowLeft size={16} />
            <span>Volver al historial</span>
          </button>

          <div>
            <h2
              style={{
                fontSize: '1.35rem',
                fontWeight: '700',
                color: 'var(--color-text-main, #0f172a)',
                margin: 0,
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
              }}
            >
              <FileSpreadsheet size={22} color="#0284c7" />
              <span>{proceso?.nombre_archivo || 'Detalle del Lote de Compras'}</span>
            </h2>
            <div style={{ fontSize: '0.8rem', color: '#64748b', marginTop: '0.2rem' }}>
              ID Proceso: <code style={{ color: '#0f172a' }}>{procesoId}</code> • Registrado el{' '}
              {proceso?.created_at
                ? new Date(proceso.created_at).toLocaleString('es-PE')
                : '-'}
            </div>
          </div>
        </div>

        {/* Botón Exportar Excel */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <button
            onClick={handleExportarExcel}
            disabled={exporting || loadingProceso}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.5rem',
              padding: '0.55rem 1.25rem',
              borderRadius: '6px',
              border: 'none',
              backgroundColor: '#16a34a',
              color: '#ffffff',
              fontSize: '0.85rem',
              fontWeight: '700',
              cursor: exporting ? 'wait' : 'pointer',
              boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
              transition: 'background-color 0.15s ease',
            }}
          >
            {exporting ? (
              <>
                <Loader2 size={16} className="spin" />
                <span>Generando Excel...</span>
              </>
            ) : (
              <>
                <Download size={16} />
                <span>EXPORTAR EXCEL</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Error */}
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

      {/* Tarjetas de Resumen Superior */}
      {proceso && (
        <ProcessSummary
          total={proceso.total_registros}
          validos={proceso.total_validos}
          noValidos={proceso.total_no_validos}
          observados={proceso.total_observados}
          errores={proceso.total_errores}
          tituloTotal="TOTAL EN PROCESO"
          subtituloTotal={`Procesados ${proceso.total_procesados} de ${proceso.total_registros}`}
        />
      )}

      {/* Formulario de Filtros */}
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
              gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
              gap: '0.85rem',
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
                Búsqueda General
              </label>
              <input
                type="text"
                placeholder="RUC, razón social, serie..."
                value={busqueda}
                onChange={(e) => setBusqueda(e.target.value)}
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
                Estado SUNAT
              </label>
              <select
                value={filtroEstado}
                onChange={(e) => setFiltroEstado(e.target.value)}
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
                <option value="">Todos</option>
                <option value="VALIDO">VÁLIDO</option>
                <option value="NO_VALIDO">NO VÁLIDO</option>
                <option value="OBSERVADO">OBSERVADO</option>
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
                RUC Emisor
              </label>
              <input
                type="text"
                placeholder="Filtrar por RUC"
                value={filtroRuc}
                onChange={(e) => setFiltroRuc(e.target.value)}
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
                Razón Social
              </label>
              <input
                type="text"
                placeholder="Filtrar por nombre"
                value={filtroRazonSocial}
                onChange={(e) => setFiltroRazonSocial(e.target.value)}
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
                Serie
              </label>
              <input
                type="text"
                placeholder="Ej. F001"
                value={filtroSerie}
                onChange={(e) => setFiltroSerie(e.target.value)}
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
                Número Correlativo
              </label>
              <input
                type="text"
                placeholder="Ej. 00052814"
                value={filtroNumero}
                onChange={(e) => setFiltroNumero(e.target.value)}
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
                  padding: '0.48rem 1rem',
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
                  padding: '0.48rem 0.85rem',
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

      {/* Tabla de Items */}
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
              fontSize: '0.8rem',
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
                <th style={{ padding: '0.65rem 0.75rem', textAlign: 'center', width: '50px' }}>
                  FILA
                </th>
                <th style={{ padding: '0.65rem 0.75rem' }}>RUC EMISOR</th>
                <th style={{ padding: '0.65rem 0.75rem' }}>RAZÓN SOCIAL</th>
                <th style={{ padding: '0.65rem 0.75rem', textAlign: 'center' }}>TIPO</th>
                <th style={{ padding: '0.65rem 0.75rem' }}>SERIE</th>
                <th style={{ padding: '0.65rem 0.75rem' }}>NÚMERO</th>
                <th style={{ padding: '0.65rem 0.75rem', textAlign: 'center' }}>EMISIÓN</th>
                <th style={{ padding: '0.65rem 0.75rem', textAlign: 'right' }}>IMP. ORIGINAL</th>
                <th style={{ padding: '0.65rem 0.75rem', textAlign: 'right' }}>IMP. SUNAT</th>
                <th style={{ padding: '0.65rem 0.75rem', textAlign: 'center' }}>ESTADO</th>
                <th style={{ padding: '0.65rem 0.75rem', textAlign: 'center' }}>CÓDIGO</th>
                <th style={{ padding: '0.65rem 0.75rem' }}>RESPUESTA OFICIAL SUNAT</th>
              </tr>
            </thead>
            <tbody>
              {loadingItems ? (
                <tr>
                  <td colSpan={12} style={{ padding: '3rem', textAlign: 'center', color: '#64748b' }}>
                    <div
                      style={{
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        gap: '0.5rem',
                      }}
                    >
                      <Loader2 size={26} className="spin" color="var(--color-primary, #1e40af)" />
                      <span>Cargando comprobantes validados...</span>
                    </div>
                  </td>
                </tr>
              ) : items.length === 0 ? (
                <tr>
                  <td colSpan={12} style={{ padding: '3rem', textAlign: 'center', color: '#64748b' }}>
                    No se encontraron comprobantes que coincidan con los filtros aplicados.
                  </td>
                </tr>
              ) : (
                items.map((it) => {
                  const montoOrig = parseFloat(it.monto_original !== undefined ? it.monto_original : it.monto);
                  const isNegativo = montoOrig < 0;

                  return (
                    <tr
                      key={it.id}
                      style={{
                        borderBottom: '1px solid #f1f5f9',
                        transition: 'background-color 0.15s ease',
                      }}
                    >
                      <td
                        style={{
                          padding: '0.65rem 0.75rem',
                          textAlign: 'center',
                          color: '#64748b',
                          fontWeight: '600',
                        }}
                      >
                        {it.fila_excel || it.id}
                      </td>
                      <td style={{ padding: '0.65rem 0.75rem', fontFamily: 'monospace', fontWeight: '600' }}>
                        {it.num_ruc}
                      </td>
                      <td style={{ padding: '0.65rem 0.75rem', maxWidth: '240px' }}>
                        <span
                          style={{
                            display: 'block',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                            color: '#1e293b',
                          }}
                          title={it.razon_social}
                        >
                          {it.razon_social || '-'}
                        </span>
                      </td>
                      <td style={{ padding: '0.65rem 0.75rem', textAlign: 'center' }}>
                        <span
                          style={{
                            fontSize: '0.72rem',
                            fontWeight: '700',
                            backgroundColor: '#f1f5f9',
                            padding: '0.15rem 0.45rem',
                            borderRadius: '4px',
                            color: '#475569',
                          }}
                        >
                          {it.cod_comp}
                        </span>
                      </td>
                      <td style={{ padding: '0.65rem 0.75rem', fontWeight: '600' }}>
                        {it.numero_serie}
                      </td>
                      <td style={{ padding: '0.65rem 0.75rem' }}>{it.numero}</td>
                      <td style={{ padding: '0.65rem 0.75rem', textAlign: 'center', whiteSpace: 'nowrap' }}>
                        {it.fecha_emision}
                      </td>
                      <td
                        style={{
                          padding: '0.65rem 0.75rem',
                          textAlign: 'right',
                          fontWeight: '700',
                          color: isNegativo ? '#dc2626' : '#0f172a',
                        }}
                      >
                        S/ {montoOrig.toFixed(2)}
                      </td>
                      <td
                        style={{
                          padding: '0.65rem 0.75rem',
                          textAlign: 'right',
                          fontWeight: '700',
                          color: 'var(--color-primary, #1e40af)',
                        }}
                      >
                        S/ {parseFloat(it.monto).toFixed(2)}
                      </td>
                      <td style={{ padding: '0.65rem 0.75rem', textAlign: 'center' }}>
                        <StatusBadge estado={it.estado} size="sm" />
                      </td>
                      <td style={{ padding: '0.65rem 0.75rem', textAlign: 'center' }}>
                        <span
                          style={{
                            fontSize: '0.75rem',
                            fontFamily: 'monospace',
                            color: '#64748b',
                          }}
                        >
                          {it.codigo_sunat || '-'}
                        </span>
                      </td>
                      <td style={{ padding: '0.65rem 0.75rem', color: '#475569', maxWidth: '300px' }}>
                        <span
                          style={{
                            display: 'block',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                            fontSize: '0.78rem',
                          }}
                          title={it.mensaje_sunat || it.estado_sunat}
                        >
                          {it.mensaje_sunat || it.estado_sunat || '-'}
                        </span>
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
    </div>
  );
};
