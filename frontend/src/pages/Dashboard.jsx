import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axiosClient from '../api/axiosClient';
import { useAuth } from '../context/AuthContext';
import { ProcessSummary } from '../components/common/ProcessSummary';
import { StatusBadge } from '../components/common/StatusBadge';
import {
  LayoutDashboard,
  Filter,
  RotateCcw,
  Calendar,
  FileSpreadsheet,
  ArrowRight,
  TrendingUp,
  ShieldCheck,
  Building2,
  Loader2,
  PieChart,
} from 'lucide-react';

export const Dashboard = () => {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [resumen, setResumen] = useState({
    total: 0,
    validos: 0,
    no_validos: 0,
    observados: 0,
    errores: 0,
    porcentaje_validos: 0.0,
    porcentaje_no_validos: 0.0,
    porcentaje_observados: 0.0,
    porcentaje_errores: 0.0,
  });

  const [procesosRecientes, setProcesosRecientes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Filtros
  const [fechaDesde, setFechaDesde] = useState('');
  const [fechaHasta, setFechaHasta] = useState('');
  const [filtroEstado, setFiltroEstado] = useState('');
  const [filtroProceso, setFiltroProceso] = useState('');

  // 1. Cargar resumen del dashboard
  const cargarResumen = async () => {
    try {
      setLoading(true);
      setError(null);

      const params = {};
      if (fechaDesde) params.fecha_desde = fechaDesde;
      if (fechaHasta) params.fecha_hasta = fechaHasta;
      if (filtroEstado) params.estado = filtroEstado;
      if (filtroProceso) params.proceso_id = filtroProceso;

      const res = await axiosClient.get('/dashboard/resumen', { params });
      setResumen(res.data);
    } catch (err) {
      console.error('Error al cargar métricas del dashboard:', err);
      setError('No fue posible cargar las estadísticas del dashboard.');
    } finally {
      setLoading(false);
    }
  };

  // 2. Cargar lista de procesos para el selector y tabla rápida
  const cargarProcesosRecientes = async () => {
    try {
      const res = await axiosClient.get('/procesos-masivos?page=1&page_size=6');
      setProcesosRecientes(res.data.items || []);
    } catch (err) {
      console.error('Error al cargar procesos recientes:', err);
    }
  };

  useEffect(() => {
    cargarResumen();
  }, [fechaDesde, fechaHasta, filtroEstado, filtroProceso]);

  useEffect(() => {
    cargarProcesosRecientes();
  }, []);

  const handleLimpiarFiltros = () => {
    setFechaDesde('');
    setFechaHasta('');
    setFiltroEstado('');
    setFiltroProceso('');
  };

  const empresaNombre = user?.empresa?.razon_social || (user?.rol === 'ADMINISTRADOR' ? 'Visión Consolidada' : 'Sin Empresa');
  const empresaRuc = user?.empresa?.ruc || (user?.rol === 'ADMINISTRADOR' ? 'TODAS' : '-');

  const total = Number(resumen.total) || 0;
  const pctValidos = total > 0 ? ((resumen.validos / total) * 100).toFixed(1) : 0;
  const pctNoValidos = total > 0 ? ((resumen.no_validos / total) * 100).toFixed(1) : 0;
  const pctObservados = total > 0 ? ((resumen.observados / total) * 100).toFixed(1) : 0;
  const pctErrores = total > 0 ? ((resumen.errores / total) * 100).toFixed(1) : 0;

  return (
    <div style={{ maxWidth: '1440px', margin: '0 auto', padding: '1.5rem' }}>
      {/* Banner de Bienvenida y Empresa */}
      <div
        className="card"
        style={{
          marginBottom: '1.5rem',
          background: 'linear-gradient(135deg, #1e3a8a 0%, #0f172a 100%)',
          color: '#ffffff',
          borderRadius: '10px',
          padding: '1.5rem 1.75rem',
          boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <span
              style={{
                fontSize: '0.75rem',
                fontWeight: '700',
                color: '#93c5fd',
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
              }}
            >
              PANEL GENERAL DE VALIDACIÓN SUNAT
            </span>
            <h2 style={{ fontSize: '1.5rem', fontWeight: '800', margin: '0.3rem 0 0.5rem 0', color: '#ffffff' }}>
              {empresaNombre}
            </h2>
            <p style={{ fontSize: '0.85rem', color: '#cbd5e1', margin: 0 }}>
              RUC Emisor / Receptor:{' '}
              <strong style={{ color: '#67e8f9', fontFamily: 'monospace' }}>{empresaRuc}</strong>{' '}
              • Usuario Activo: <strong style={{ color: '#ffffff' }}>{user?.nombre_completo}</strong> ({user?.rol})
            </p>
          </div>

          <div style={{ display: 'flex', gap: '0.75rem' }}>
            <button
              onClick={() => navigate('/carga-masiva')}
              style={{
                backgroundColor: 'rgba(255, 255, 255, 0.15)',
                color: '#ffffff',
                border: '1px solid rgba(255, 255, 255, 0.3)',
                padding: '0.55rem 1rem',
                borderRadius: '6px',
                fontSize: '0.825rem',
                fontWeight: '600',
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.4rem',
              }}
            >
              <FileSpreadsheet size={16} />
              <span>Validar nuevo Excel</span>
            </button>
          </div>
        </div>
      </div>

      {/* Filtros del Dashboard */}
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
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
            gap: '1rem',
            alignItems: 'flex-end',
          }}
        >
          <div>
            <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: '600', color: '#475569', marginBottom: '0.35rem' }}>
              Filtrar por Proceso Masivo
            </label>
            <select
              value={filtroProceso}
              onChange={(e) => setFiltroProceso(e.target.value)}
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
              <option value="">Todos los procesos (Global)</option>
              {procesosRecientes.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.nombre_archivo || p.id.substring(0, 8)} ({p.total_registros} items)
                </option>
              ))}
            </select>
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: '600', color: '#475569', marginBottom: '0.35rem' }}>
              Estado
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
              <option value="">Todos los estados</option>
              <option value="VALIDO">VÁLIDO</option>
              <option value="NO_VALIDO">NO VÁLIDO</option>
              <option value="OBSERVADO">OBSERVADO</option>
              <option value="ERROR">ERROR</option>
            </select>
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: '600', color: '#475569', marginBottom: '0.35rem' }}>
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
            <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: '600', color: '#475569', marginBottom: '0.35rem' }}>
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

          <div>
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
              <span>Limpiar filtros</span>
            </button>
          </div>
        </div>
      </div>

      {/* Tarjetas Principales del Dashboard */}
      {loading ? (
        <div style={{ padding: '3rem', textAlign: 'center', color: '#64748b' }}>
          <Loader2 size={32} className="spin" color="var(--color-primary, #1e40af)" />
          <p style={{ marginTop: '0.5rem', fontSize: '0.9rem' }}>Actualizando métricas contables...</p>
        </div>
      ) : (
        <>
          <ProcessSummary
            total={resumen.total}
            validos={resumen.validos}
            noValidos={resumen.no_validos}
            observados={resumen.observados}
            errores={resumen.errores}
            tituloTotal="TOTAL PROCESADOS"
            subtituloTotal="Comprobantes consultados ante SUNAT"
          />

          {/* Gráfico de Distribución Visual */}
          <div
            className="card"
            style={{
              padding: '1.25rem 1.5rem',
              marginBottom: '1.5rem',
              backgroundColor: '#ffffff',
              borderRadius: '8px',
              border: '1px solid var(--color-border, #e2e8f0)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <PieChart size={18} color="var(--color-primary, #1e40af)" />
                <h3 style={{ fontSize: '1rem', fontWeight: '700', margin: 0, color: '#0f172a' }}>
                  Distribución Porcentual de Comprobantes
                </h3>
              </div>
              <span style={{ fontSize: '0.8rem', color: '#64748b' }}>
                Total: <strong style={{ color: '#0f172a' }}>{total}</strong> comprobantes evaluados
              </span>
            </div>

            {total === 0 ? (
              <div style={{ padding: '1.5rem', textAlign: 'center', color: '#94a3b8', fontSize: '0.85rem' }}>
                Sin comprobantes procesados para el rango de filtros seleccionado.
              </div>
            ) : (
              <div>
                {/* Barra de Distribución Multi-segmento */}
                <div
                  style={{
                    height: '24px',
                    width: '100%',
                    backgroundColor: '#e2e8f0',
                    borderRadius: '8px',
                    overflow: 'hidden',
                    display: 'flex',
                    marginBottom: '1.25rem',
                  }}
                >
                  {resumen.validos > 0 && (
                    <div
                      style={{
                        width: `${pctValidos}%`,
                        backgroundColor: '#16a34a',
                        transition: 'width 0.4s ease',
                      }}
                      title={`Válidos: ${resumen.validos} (${pctValidos}%)`}
                    />
                  )}
                  {resumen.no_validos > 0 && (
                    <div
                      style={{
                        width: `${pctNoValidos}%`,
                        backgroundColor: '#dc2626',
                        transition: 'width 0.4s ease',
                      }}
                      title={`No Válidos: ${resumen.no_validos} (${pctNoValidos}%)`}
                    />
                  )}
                  {resumen.observados > 0 && (
                    <div
                      style={{
                        width: `${pctObservados}%`,
                        backgroundColor: '#d97706',
                        transition: 'width 0.4s ease',
                      }}
                      title={`Observados: ${resumen.observados} (${pctObservados}%)`}
                    />
                  )}
                  {resumen.errores > 0 && (
                    <div
                      style={{
                        width: `${pctErrores}%`,
                        backgroundColor: '#6b7280',
                        transition: 'width 0.4s ease',
                      }}
                      title={`Errores: ${resumen.errores} (${pctErrores}%)`}
                    />
                  )}
                </div>

                {/* Leyenda Detallada */}
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
                    gap: '1rem',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <div style={{ width: '12px', height: '12px', borderRadius: '3px', backgroundColor: '#16a34a' }} />
                    <span style={{ fontSize: '0.825rem', color: '#334155' }}>
                      Válidos: <strong>{resumen.validos}</strong> ({pctValidos}%)
                    </span>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <div style={{ width: '12px', height: '12px', borderRadius: '3px', backgroundColor: '#dc2626' }} />
                    <span style={{ fontSize: '0.825rem', color: '#334155' }}>
                      No Válidos: <strong>{resumen.no_validos}</strong> ({pctNoValidos}%)
                    </span>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <div style={{ width: '12px', height: '12px', borderRadius: '3px', backgroundColor: '#d97706' }} />
                    <span style={{ fontSize: '0.825rem', color: '#334155' }}>
                      Observados: <strong>{resumen.observados}</strong> ({pctObservados}%)
                    </span>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <div style={{ width: '12px', height: '12px', borderRadius: '3px', backgroundColor: '#6b7280' }} />
                    <span style={{ fontSize: '0.825rem', color: '#334155' }}>
                      Errores: <strong>{resumen.errores}</strong> ({pctErrores}%)
                    </span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </>
      )}

      {/* Últimos Procesos Masivos */}
      <div
        className="card"
        style={{
          padding: '1.25rem 1.5rem',
          backgroundColor: '#ffffff',
          borderRadius: '8px',
          border: '1px solid var(--color-border, #e2e8f0)',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <h3 style={{ fontSize: '1rem', fontWeight: '700', margin: 0, color: '#0f172a' }}>
            Últimos Lotes de Compras Procesados
          </h3>
          <button
            onClick={() => navigate('/historial')}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.35rem',
              backgroundColor: 'transparent',
              border: 'none',
              color: 'var(--color-primary, #1e40af)',
              fontSize: '0.825rem',
              fontWeight: '600',
              cursor: 'pointer',
            }}
          >
            <span>Ver historial completo</span>
            <ArrowRight size={14} />
          </button>
        </div>

        {procesosRecientes.length === 0 ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: '#94a3b8', fontSize: '0.85rem' }}>
            No se han registrado procesos masivos aún para <strong>{empresaNombre}</strong>.
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.825rem', textAlign: 'left' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #e2e8f0', color: '#64748b' }}>
                  <th style={{ padding: '0.5rem 0.75rem' }}>FECHA</th>
                  <th style={{ padding: '0.5rem 0.75rem' }}>ARCHIVO</th>
                  <th style={{ padding: '0.5rem 0.75rem', textAlign: 'center' }}>TOTAL</th>
                  <th style={{ padding: '0.5rem 0.75rem', textAlign: 'center', color: '#16a34a' }}>VÁLIDOS</th>
                  <th style={{ padding: '0.5rem 0.75rem', textAlign: 'center', color: '#dc2626' }}>NO VÁLIDOS</th>
                  <th style={{ padding: '0.5rem 0.75rem', textAlign: 'center', color: '#d97706' }}>OBSERVADOS</th>
                  <th style={{ padding: '0.5rem 0.75rem', textAlign: 'center' }}>ESTADO</th>
                  <th style={{ padding: '0.5rem 0.75rem', textAlign: 'center' }}>ACCIÓN</th>
                </tr>
              </thead>
              <tbody>
                {procesosRecientes.map((p) => (
                  <tr key={p.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                    <td style={{ padding: '0.6rem 0.75rem', color: '#475569' }}>
                      {p.created_at ? new Date(p.created_at).toLocaleDateString('es-PE') : '-'}
                    </td>
                    <td style={{ padding: '0.6rem 0.75rem', fontWeight: '500', color: '#0f172a' }}>
                      {p.nombre_archivo || 'Lote sin nombre'}
                    </td>
                    <td style={{ padding: '0.6rem 0.75rem', textAlign: 'center', fontWeight: '700' }}>
                      {p.total_registros}
                    </td>
                    <td style={{ padding: '0.6rem 0.75rem', textAlign: 'center', fontWeight: '700', color: '#16a34a' }}>
                      {p.total_validos}
                    </td>
                    <td style={{ padding: '0.6rem 0.75rem', textAlign: 'center', fontWeight: '700', color: '#dc2626' }}>
                      {p.total_no_validos}
                    </td>
                    <td style={{ padding: '0.6rem 0.75rem', textAlign: 'center', fontWeight: '700', color: '#d97706' }}>
                      {p.total_observados}
                    </td>
                    <td style={{ padding: '0.6rem 0.75rem', textAlign: 'center' }}>
                      <StatusBadge estado={p.estado} size="sm" />
                    </td>
                    <td style={{ padding: '0.6rem 0.75rem', textAlign: 'center' }}>
                      <button
                        onClick={() => navigate(`/historial/${p.id}`)}
                        style={{
                          backgroundColor: '#f1f5f9',
                          border: '1px solid #cbd5e1',
                          borderRadius: '4px',
                          padding: '0.25rem 0.6rem',
                          fontSize: '0.75rem',
                          fontWeight: '600',
                          color: '#1e40af',
                          cursor: 'pointer',
                        }}
                      >
                        Ver
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
