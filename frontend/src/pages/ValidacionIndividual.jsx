import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import axiosClient from '../api/axiosClient';
import {
  Search,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Building2,
  FileText,
  Calendar,
  DollarSign,
  Hash,
  RotateCcw,
  ShieldAlert,
  Loader2,
  History,
  Trash2,
  X,
} from 'lucide-react';

const TIPOS_COMPROBANTE = [
  { codigo: '01', nombre: 'Factura Electrónica' },
  { codigo: '03', nombre: 'Boleta de Venta Electrónica' },
  { codigo: '07', nombre: 'Nota de Crédito Electrónica' },
  { codigo: '08', nombre: 'Nota de Débito Electrónica' },
];

export const ValidacionIndividual = () => {
  const { user } = useAuth();

  // Datos de la empresa autenticada (informativos, no editables)
  const empresaNombre = user?.empresa?.razon_social || (user?.rol === 'ADMINISTRADOR' ? 'Empresa no asignada' : '-');
  const empresaRuc = user?.empresa?.ruc || (user?.rol === 'ADMINISTRADOR' ? 'Sin RUC directo' : '-');
  const esAdminSinEmpresa = user?.rol === 'ADMINISTRADOR' && !user?.empresa_id;

  // Estado del formulario
  const [formData, setFormData] = useState({
    num_ruc: '',
    cod_comp: '01',
    numero_serie: '',
    numero: '',
    fecha_emision: new Date().toISOString().split('T')[0],
    monto: '',
  });

  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);
  const [resultado, setResultado] = useState(null);
  const [consultasRecientes, setConsultasRecientes] = useState([]);
  const [loadingHistorial, setLoadingHistorial] = useState(false);
  const [consultaAEliminar, setConsultaAEliminar] = useState(null);
  const [eliminando, setEliminando] = useState(false);
  const [errorEliminar, setErrorEliminar] = useState('');
  const [mensajeExito, setMensajeExito] = useState('');

  // Cargar historial reciente de la empresa
  const fetchHistorial = async () => {
    if (esAdminSinEmpresa) return;
    try {
      setLoadingHistorial(true);
      const res = await axiosClient.get('/sunat/consultas?limit=5');
      setConsultasRecientes(res.data);
    } catch (err) {
      console.error('Error al cargar historial de consultas:', err);
    } finally {
      setLoadingHistorial(false);
    }
  };

  const handleAbrirModalEliminar = (item) => {
    setErrorEliminar('');
    setConsultaAEliminar(item);
  };

  const handleConfirmarEliminar = async () => {
    if (!consultaAEliminar || eliminando) return;
    setEliminando(true);
    setErrorEliminar('');
    try {
      await axiosClient.delete(`/sunat/consultas/${consultaAEliminar.id}`);

      // Retirar inmediatamente de la tabla sin recargar toda la página
      setConsultasRecientes((prev) => prev.filter((c) => c.id !== consultaAEliminar.id));

      setConsultaAEliminar(null);
      setMensajeExito('Consulta eliminada correctamente');
      setTimeout(() => {
        setMensajeExito('');
      }, 5000);

      // Refrescar historial
      fetchHistorial();
    } catch (err) {
      console.error('Error al eliminar consulta:', err);
      const status = err.response?.status;
      const detail = err.response?.data?.detail;
      if (status === 409) {
        setErrorEliminar(
          typeof detail === 'string'
            ? detail
            : 'Esta consulta pertenece a un lote masivo y debe gestionarse desde el historial del lote.'
        );
      } else if (typeof detail === 'string') {
        setErrorEliminar(detail);
      } else {
        setErrorEliminar('No se pudo eliminar la consulta.');
      }
    } finally {
      setEliminando(false);
    }
  };

  useEffect(() => {
    fetchHistorial();
  }, [user]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }));
    if (errorMsg) setErrorMsg(null);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (loading) return;

    setErrorMsg(null);
    setResultado(null);

    // Validaciones del frontend para asistencia al usuario
    const rucTrim = formData.num_ruc.trim();
    if (!/^\d{11}$/.test(rucTrim)) {
      setErrorMsg('El RUC del emisor debe contener exactamente 11 dígitos numéricos.');
      return;
    }

    if (!formData.numero_serie.trim()) {
      setErrorMsg('La serie del comprobante es requerida (ej. F006).');
      return;
    }

    if (!formData.numero.trim()) {
      setErrorMsg('El número correlativo del comprobante es requerido.');
      return;
    }

    if (!formData.fecha_emision) {
      setErrorMsg('La fecha de emisión es requerida.');
      return;
    }

    const montoNum = parseFloat(formData.monto);
    if (isNaN(montoNum) || montoNum < 0) {
      setErrorMsg('El importe total debe ser un número decimal válido mayor o igual a 0.00.');
      return;
    }

    setLoading(true);

    try {
      // El frontend NO envía empresa_id. Se resuelve en backend mediante el JWT.
      const payload = {
        num_ruc: rucTrim,
        cod_comp: formData.cod_comp,
        numero_serie: formData.numero_serie.trim().toUpperCase(),
        numero: formData.numero.trim(),
        fecha_emision: formData.fecha_emision,
        monto: montoNum.toFixed(2),
      };

      const response = await axiosClient.post('/sunat/validar', payload);
      setResultado(response.data);
      // Actualizar historial
      fetchHistorial();
    } catch (err) {
      console.error('Error en validación SUNAT:', err);
      const detail = err.response?.data?.detail;
      if (typeof detail === 'string') {
        setErrorMsg(detail);
      } else if (Array.isArray(detail)) {
        setErrorMsg(detail.map((d) => d.msg).join(', '));
      } else {
        setErrorMsg('Error de comunicación con el servicio de SUNAT. Intente nuevamente.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleLimpiar = () => {
    setFormData({
      num_ruc: '',
      cod_comp: '01',
      numero_serie: '',
      numero: '',
      fecha_emision: new Date().toISOString().split('T')[0],
      monto: '',
    });
    setResultado(null);
    setErrorMsg(null);
  };

  const getEstadoBadge = (estado) => {
    switch (estado) {
      case 'VALIDO':
        return (
          <span className="badge badge-success" style={{ fontSize: '0.9rem', padding: '0.4rem 0.85rem' }}>
            <CheckCircle2 size={16} /> VÁLIDO
          </span>
        );
      case 'NO_VALIDO':
        return (
          <span className="badge badge-danger" style={{ fontSize: '0.9rem', padding: '0.4rem 0.85rem' }}>
            <XCircle size={16} /> NO VÁLIDO
          </span>
        );
      case 'OBSERVADO':
        return (
          <span className="badge badge-warning" style={{ fontSize: '0.9rem', padding: '0.4rem 0.85rem' }}>
            <AlertTriangle size={16} /> OBSERVADO
          </span>
        );
      case 'ERROR':
      default:
        return (
          <span className="badge badge-danger" style={{ fontSize: '0.9rem', padding: '0.4rem 0.85rem' }}>
            <ShieldAlert size={16} /> ERROR
          </span>
        );
    }
  };

  return (
    <div style={{ maxWidth: '1000px', margin: '0 auto' }}>
      {/* Banner de Contexto de Empresa Autenticada */}
      <div
        className="card"
        style={{
          marginBottom: '1.5rem',
          borderLeft: '4px solid var(--color-primary)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '1rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
          <div
            style={{
              width: '42px',
              height: '42px',
              borderRadius: '8px',
              backgroundColor: 'var(--color-primary-light)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--color-primary)',
            }}
          >
            <Building2 size={24} />
          </div>
          <div>
            <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--color-text-muted)', fontWeight: 600 }}>
              Empresa Consultora (Contexto Activo)
            </div>
            <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--color-text-main)' }}>
              {empresaNombre}
            </div>
          </div>
        </div>

        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--color-text-muted)', fontWeight: 600 }}>
            RUC de Consulta SUNAT
          </div>
          <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--color-primary)', fontFamily: 'monospace' }}>
            {empresaRuc}
          </div>
        </div>
      </div>

      {esAdminSinEmpresa && (
        <div className="login-alert" style={{ marginBottom: '1.5rem' }}>
          <strong>Aviso de Administrador:</strong> Su usuario administrador global no tiene una empresa asignada. Para consultar SUNAT, debe asociarse a una empresa activa (DAIRA o GRUPO JJD MAR).
        </div>
      )}

      {/* Tarjeta del Formulario de Validación */}
      <div className="card" style={{ marginBottom: '2rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.5rem' }}>
          <Search size={22} color="var(--color-primary)" />
          <h2 className="card-title" style={{ margin: 0 }}>
            Validación Individual de Comprobantes SUNAT
          </h2>
        </div>
        <p className="card-description">
          Ingrese los datos del comprobante electrónico emitido por un tercero para verificar su validez oficial y estado tributario ante SUNAT.
        </p>

        {errorMsg && (
          <div
            className="login-alert"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              marginBottom: '1.5rem',
            }}
          >
            <ShieldAlert size={18} />
            <span>{errorMsg}</span>
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
              gap: '1.25rem',
              marginBottom: '1.5rem',
            }}
          >
            {/* RUC Emisor */}
            <div className="form-group" style={{ margin: 0 }}>
              <label className="form-label" htmlFor="num_ruc">
                RUC del Emisor *
              </label>
              <div style={{ position: 'relative' }}>
                <input
                  id="num_ruc"
                  name="num_ruc"
                  type="text"
                  maxLength="11"
                  className="form-input"
                  placeholder="Ej. 20103134065"
                  value={formData.num_ruc}
                  onChange={handleChange}
                  required
                  disabled={loading}
                />
              </div>
              <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
                RUC de 11 dígitos de quien emite el comprobante
              </span>
            </div>

            {/* Tipo de Comprobante */}
            <div className="form-group" style={{ margin: 0 }}>
              <label className="form-label" htmlFor="cod_comp">
                Tipo de Comprobante *
              </label>
              <select
                id="cod_comp"
                name="cod_comp"
                className="form-input"
                value={formData.cod_comp}
                onChange={handleChange}
                disabled={loading}
                required
              >
                {TIPOS_COMPROBANTE.map((tipo) => (
                  <option key={tipo.codigo} value={tipo.codigo}>
                    {tipo.codigo} - {tipo.nombre}
                  </option>
                ))}
              </select>
              <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
                Catálogo SUNAT No. 01
              </span>
            </div>

            {/* Serie */}
            <div className="form-group" style={{ margin: 0 }}>
              <label className="form-label" htmlFor="numero_serie">
                Serie del Comprobante *
              </label>
              <input
                id="numero_serie"
                name="numero_serie"
                type="text"
                maxLength="10"
                className="form-input"
                placeholder="Ej. F006, E001, B001"
                value={formData.numero_serie}
                onChange={handleChange}
                required
                disabled={loading}
                style={{ textTransform: 'uppercase' }}
              />
              <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
                Letras y números (ej. F006)
              </span>
            </div>

            {/* Número */}
            <div className="form-group" style={{ margin: 0 }}>
              <label className="form-label" htmlFor="numero">
                Número Correlativo *
              </label>
              <input
                id="numero"
                name="numero"
                type="text"
                maxLength="20"
                className="form-input"
                placeholder="Ej. 0053117 o 53117"
                value={formData.numero}
                onChange={handleChange}
                required
                disabled={loading}
              />
              <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
                Número asignado al comprobante
              </span>
            </div>

            {/* Fecha de Emisión */}
            <div className="form-group" style={{ margin: 0 }}>
              <label className="form-label" htmlFor="fecha_emision">
                Fecha de Emisión *
              </label>
              <input
                id="fecha_emision"
                name="fecha_emision"
                type="date"
                className="form-input"
                value={formData.fecha_emision}
                onChange={handleChange}
                required
                disabled={loading}
              />
              <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
                Fecha indicada en el documento
              </span>
            </div>

            {/* Monto Total */}
            <div className="form-group" style={{ margin: 0 }}>
              <label className="form-label" htmlFor="monto">
                Importe Total (S/) *
              </label>
              <input
                id="monto"
                name="monto"
                type="number"
                step="0.01"
                min="0"
                className="form-input"
                placeholder="Ej. 387.23"
                value={formData.monto}
                onChange={handleChange}
                required
                disabled={loading}
              />
              <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
                Importe en Soles con hasta 2 decimales
              </span>
            </div>
          </div>

          {/* Acciones */}
          <div style={{ display: 'flex', gap: '1rem', justifyContent: 'flex-end', alignItems: 'center' }}>
            <button
              type="button"
              onClick={handleLimpiar}
              className="btn-logout"
              style={{
                width: 'auto',
                color: 'var(--color-text-muted)',
                backgroundColor: '#f1f5f9',
                border: '1px solid #cbd5e1',
              }}
              disabled={loading}
            >
              <RotateCcw size={16} />
              <span>Limpiar</span>
            </button>

            <button
              type="submit"
              className="btn-primary"
              style={{ width: 'auto', minWidth: '220px' }}
              disabled={loading || esAdminSinEmpresa}
            >
              {loading ? (
                <>
                  <Loader2 size={18} className="spin" style={{ animation: 'spin 1s linear infinite' }} />
                  <span>Consultando SUNAT...</span>
                </>
              ) : (
                <>
                  <Search size={18} />
                  <span>VALIDAR EN SUNAT</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>

      {/* Tarjeta de Resultado de Validación */}
      {resultado && (
        <div
          className="card"
          style={{
            marginBottom: '2rem',
            border:
              resultado.estado === 'VALIDO'
                ? '1px solid var(--color-success-border)'
                : resultado.estado === 'OBSERVADO'
                ? '1px solid var(--color-warning-border)'
                : '1px solid var(--color-danger-border)',
            boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
          }}
        >
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              borderBottom: '1px solid var(--color-border)',
              paddingBottom: '1rem',
              marginBottom: '1.25rem',
              flexWrap: 'wrap',
              gap: '0.75rem',
            }}
          >
            <div>
              <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>
                Resultado de Validación Oficial
              </span>
              <h3 style={{ fontSize: '1.25rem', fontWeight: 700, margin: '0.2rem 0 0', color: 'var(--color-text-main)' }}>
                {resultado.tipo_comprobante_descripcion} {resultado.serie}-{resultado.numero}
              </h3>
            </div>
            <div>{getEstadoBadge(resultado.estado)}</div>
          </div>

          {/* Grilla de Datos del Comprobante */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
              gap: '1rem',
              backgroundColor: '#f8fafc',
              padding: '1.25rem',
              borderRadius: 'var(--radius-sm)',
              marginBottom: '1.25rem',
            }}
          >
            <div>
              <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', display: 'block' }}>RUC Emisor:</span>
              <strong style={{ fontSize: '0.95rem', fontFamily: 'monospace' }}>{resultado.ruc_emisor}</strong>
            </div>

            <div>
              <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', display: 'block' }}>Fecha de Emisión:</span>
              <strong style={{ fontSize: '0.95rem' }}>{resultado.fecha_emision}</strong>
            </div>

            <div>
              <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', display: 'block' }}>Importe Total:</span>
              <strong style={{ fontSize: '0.95rem', color: 'var(--color-primary)' }}>S/ {parseFloat(resultado.monto).toFixed(2)}</strong>
            </div>

            <div>
              <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', display: 'block' }}>Código SUNAT:</span>
              <span className="badge badge-info" style={{ fontFamily: 'monospace' }}>
                {resultado.codigo_sunat || 'N/A'}
              </span>
            </div>
          </div>

          {/* Mensaje Funcional SUNAT */}
          <div
            style={{
              padding: '1rem',
              borderRadius: 'var(--radius-sm)',
              backgroundColor:
                resultado.estado === 'VALIDO'
                  ? 'var(--color-success-bg)'
                  : resultado.estado === 'OBSERVADO'
                  ? 'var(--color-warning-bg)'
                  : 'var(--color-danger-bg)',
              color:
                resultado.estado === 'VALIDO'
                  ? 'var(--color-success-text)'
                  : resultado.estado === 'OBSERVADO'
                  ? 'var(--color-warning-text)'
                  : 'var(--color-danger-text)',
              fontSize: '0.875rem',
              lineHeight: '1.5',
            }}
          >
            <strong>Respuesta SUNAT:</strong> {resultado.mensaje_sunat || 'Sin observaciones registradas.'}
          </div>
        </div>
      )}

      {/* Alerta de Éxito al eliminar consulta */}
      {mensajeExito && (
        <div
          style={{
            marginBottom: '1rem',
            padding: '0.75rem 1rem',
            backgroundColor: '#ecfdf5',
            border: '1px solid #a7f3d0',
            borderRadius: '6px',
            color: '#065f46',
            fontSize: '0.85rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <CheckCircle2 size={16} color="#059669" />
            <span>{mensajeExito}</span>
          </div>
          <button
            type="button"
            onClick={() => setMensajeExito('')}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              color: '#059669',
            }}
          >
            <X size={14} />
          </button>
        </div>
      )}

      {/* Historial Reciente de Consultas */}
      {consultasRecientes.length > 0 && (
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
            <History size={18} color="var(--color-text-muted)" />
            <h3 style={{ fontSize: '1rem', fontWeight: 600, margin: 0 }}>
              Consultas Recientes de {empresaNombre}
            </h3>
          </div>

          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--color-border)', textAlign: 'left', color: 'var(--color-text-muted)' }}>
                  <th style={{ padding: '0.6rem 0.5rem' }}>Comprobante</th>
                  <th style={{ padding: '0.6rem 0.5rem' }}>RUC Emisor</th>
                  <th style={{ padding: '0.6rem 0.5rem' }}>Fecha Emisión</th>
                  <th style={{ padding: '0.6rem 0.5rem', textAlign: 'right' }}>Importe</th>
                  <th style={{ padding: '0.6rem 0.5rem', textAlign: 'center' }}>Estado</th>
                  <th style={{ padding: '0.6rem 0.5rem' }}>Fecha Consulta</th>
                  <th style={{ padding: '0.6rem 0.5rem', textAlign: 'center' }}>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {consultasRecientes.map((item) => (
                  <tr key={item.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                    <td style={{ padding: '0.6rem 0.5rem', fontWeight: 500 }}>
                      {item.tipo_comprobante}-{item.serie}-{item.numero}
                    </td>
                    <td style={{ padding: '0.6rem 0.5rem', fontFamily: 'monospace' }}>
                      {item.ruc_emisor}
                    </td>
                    <td style={{ padding: '0.6rem 0.5rem' }}>{item.fecha_emision}</td>
                    <td style={{ padding: '0.6rem 0.5rem', textAlign: 'right', fontWeight: 600 }}>
                      S/ {parseFloat(item.monto).toFixed(2)}
                    </td>
                    <td style={{ padding: '0.6rem 0.5rem', textAlign: 'center' }}>
                      {getEstadoBadge(item.estado)}
                    </td>
                    <td style={{ padding: '0.6rem 0.5rem', color: 'var(--color-text-muted)', fontSize: '0.8rem' }}>
                      {new Date(item.created_at).toLocaleString('es-PE', { dateStyle: 'short', timeStyle: 'short' })}
                    </td>
                    <td style={{ padding: '0.6rem 0.5rem', textAlign: 'center' }}>
                      <button
                        type="button"
                        onClick={() => handleAbrirModalEliminar(item)}
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '0.35rem',
                          padding: '0.35rem 0.65rem',
                          fontSize: '0.75rem',
                          fontWeight: 500,
                          color: '#dc2626',
                          backgroundColor: '#fee2e2',
                          border: '1px solid #fecaca',
                          borderRadius: '6px',
                          cursor: 'pointer',
                          transition: 'all 0.15s ease-in-out',
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.backgroundColor = '#fca5a5';
                          e.currentTarget.style.color = '#b91c1c';
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.backgroundColor = '#fee2e2';
                          e.currentTarget.style.color = '#dc2626';
                        }}
                        title="Eliminar consulta"
                      >
                        <Trash2 size={13} />
                        <span>Eliminar</span>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Modal de Confirmación de Eliminación */}
      {consultaAEliminar && (
        <div className="modal-overlay" style={{ zIndex: 1100 }}>
          <div className="modal-content" style={{ maxWidth: '440px' }}>
            <div className="modal-header">
              <div className="modal-title" style={{ color: '#b91c1c' }}>
                <AlertTriangle size={20} color="#dc2626" />
                <span>Eliminar consulta</span>
              </div>
              <button
                type="button"
                onClick={() => !eliminando && setConsultaAEliminar(null)}
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

              <p style={{ margin: '0 0 0.75rem 0', fontSize: '0.9rem', color: '#1e293b' }}>
                ¿Seguro que deseas eliminar esta consulta?
              </p>

              <div
                style={{
                  marginBottom: '1rem',
                  backgroundColor: '#f8fafc',
                  padding: '0.85rem 1rem',
                  borderRadius: '6px',
                  border: '1px solid #e2e8f0',
                  fontSize: '0.85rem',
                }}
              >
                <div style={{ marginBottom: '0.4rem' }}>
                  <span style={{ color: '#64748b' }}>Comprobante: </span>
                  <strong style={{ color: '#0f172a' }}>
                    {consultaAEliminar.tipo_comprobante}-{consultaAEliminar.serie}-{consultaAEliminar.numero}
                  </strong>
                </div>
                <div style={{ marginBottom: '0.4rem' }}>
                  <span style={{ color: '#64748b' }}>RUC: </span>
                  <strong style={{ color: '#0f172a', fontFamily: 'monospace' }}>
                    {consultaAEliminar.ruc_emisor}
                  </strong>
                </div>
                <div style={{ marginBottom: '0.4rem' }}>
                  <span style={{ color: '#64748b' }}>Importe: </span>
                  <strong style={{ color: '#0f172a' }}>
                    S/ {parseFloat(consultaAEliminar.monto).toLocaleString('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </strong>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                  <span style={{ color: '#64748b' }}>Estado: </span>
                  <span>{getEstadoBadge(consultaAEliminar.estado)}</span>
                </div>
              </div>

              <p style={{ margin: '0 0 0.5rem 0', fontSize: '0.825rem', color: '#64748b' }}>
                Esta acción eliminará la consulta del historial.
              </p>
              <p style={{ margin: 0, fontSize: '0.825rem', color: '#dc2626', fontWeight: '600' }}>
                Esta acción no se puede deshacer.
              </p>
            </div>

            <div className="modal-footer">
              <button
                type="button"
                disabled={eliminando}
                onClick={() => setConsultaAEliminar(null)}
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
                <span>{eliminando ? 'Eliminando...' : 'Eliminar'}</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ValidacionIndividual;
