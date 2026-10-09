import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import {
  consultarSSCO,
  obtenerEstadoSSCO,
  sincronizarSSCO,
  cargarExcelSSCO,
} from '../api/ssco';
import {
  Search,
  AlertTriangle,
  Info,
  ShieldAlert,
  RefreshCw,
  UploadCloud,
  Building2,
  Calendar,
  FileText,
  User,
  CheckCircle2,
  XCircle,
  HelpCircle,
} from 'lucide-react';

export const ConsultaSSCO = () => {
  const { user } = useAuth();
  const isAdmin = user?.rol === 'ADMINISTRADOR';

  // Estados de consulta
  const [rucInput, setRucInput] = useState('');
  const [loadingConsulta, setLoadingConsulta] = useState(false);
  const [errorConsulta, setErrorConsulta] = useState(null);
  const [resultado, setResultado] = useState(null);

  // Estados del padrón
  const [estadoPadron, setEstadoPadron] = useState(null);
  const [loadingEstado, setLoadingEstado] = useState(false);

  // Estados de administración
  const [modalConfirmacionSync, setModalConfirmacionSync] = useState(false);
  const [loadingSync, setLoadingSync] = useState(false);
  const [mensajeAdmin, setMensajeAdmin] = useState(null);
  const [errorAdmin, setErrorAdmin] = useState(null);

  // Cargar estado del padrón al montar
  const cargarEstado = async () => {
    try {
      setLoadingEstado(true);
      const data = await obtenerEstadoSSCO();
      setEstadoPadron(data);
    } catch (err) {
      console.error('Error al cargar estado del padrón SSCO:', err);
    } finally {
      setLoadingEstado(false);
    }
  };

  useEffect(() => {
    cargarEstado();
  }, []);

  // Manejar consulta individual por RUC
  const handleConsultar = async (e) => {
    e.preventDefault();
    const rucLimpio = rucInput.trim();

    if (!rucLimpio) {
      setErrorConsulta('Por favor ingrese un número de RUC.');
      return;
    }

    if (rucLimpio.length !== 11 || !/^\d+$/.test(rucLimpio)) {
      setErrorConsulta('El RUC debe contener exactamente 11 dígitos numéricos.');
      return;
    }

    setErrorConsulta(null);
    setResultado(null);
    setLoadingConsulta(true);

    try {
      const data = await consultarSSCO(rucLimpio);
      setResultado(data);
    } catch (err) {
      const msg = err.response?.data?.detail || 'Ocurrió un error al consultar el padrón SSCO.';
      setErrorConsulta(msg);
    } finally {
      setLoadingConsulta(false);
    }
  };

  // Manejar sincronización desde SUNAT (Admin)
  const handleEjecutarSync = async () => {
    setModalConfirmacionSync(false);
    setLoadingSync(true);
    setMensajeAdmin(null);
    setErrorAdmin(null);

    try {
      const res = await sincronizarSSCO();
      setMensajeAdmin(res.mensaje);
      await cargarEstado();
    } catch (err) {
      const msg = err.response?.data?.detail || 'Error al sincronizar el padrón con SUNAT.';
      setErrorAdmin(msg);
    } finally {
      setLoadingSync(false);
    }
  };

  // Manejar carga manual de Excel (Admin)
  const handleCargaManual = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.name.toLowerCase().endsWith('.xlsx')) {
      setErrorAdmin('El archivo debe tener extensión .xlsx.');
      return;
    }

    setLoadingSync(true);
    setMensajeAdmin(null);
    setErrorAdmin(null);

    try {
      const res = await cargarExcelSSCO(file);
      setMensajeAdmin(res.mensaje);
      await cargarEstado();
    } catch (err) {
      const msg = err.response?.data?.detail || 'Error al procesar el archivo Excel oficial.';
      setErrorAdmin(msg);
    } finally {
      setLoadingSync(false);
      e.target.value = ''; // Reset input file
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Encabezado Principal */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: '700', color: '#1e293b', margin: 0 }}>
            Verificación SSCO
          </h1>
          <p style={{ color: '#64748b', margin: '0.25rem 0 0', fontSize: '0.95rem' }}>
            Consulta de Sujetos Sin Capacidad Operativa — Verifique si el RUC de un proveedor figura en el padrón oficial consultado.
          </p>
        </div>

        {/* Badge Estado Padrón */}
        <div style={{
          backgroundColor: estadoPadron?.padron_disponible ? '#f0fdf4' : '#fffbeb',
          border: `1px solid ${estadoPadron?.padron_disponible ? '#bbf7d0' : '#fde68a'}`,
          borderRadius: '8px',
          padding: '0.5rem 1rem',
          fontSize: '0.85rem',
          display: 'flex',
          alignItems: 'center',
          gap: '0.5rem',
        }}>
          <div style={{
            width: '8px',
            height: '8px',
            borderRadius: '50%',
            backgroundColor: estadoPadron?.padron_disponible ? '#22c55e' : '#f59e0b',
          }} />
          <span style={{ fontWeight: '600', color: estadoPadron?.padron_disponible ? '#166534' : '#92400e' }}>
            {estadoPadron?.padron_disponible
              ? `Padrón SSCO: ${estadoPadron.total_registros} RUCs (${estadoPadron.fecha_padron_sunat || 'Vigente'})`
              : 'Padrón no disponible'}
          </span>
        </div>
      </div>

      {/* Controles de Administración (Solo Administrador) */}
      {isAdmin && (
        <div style={{
          backgroundColor: '#ffffff',
          borderRadius: '10px',
          padding: '1.25rem',
          border: '1px solid #e2e8f0',
          boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
            <div>
              <h2 style={{ fontSize: '0.95rem', fontWeight: '700', color: '#0f172a', margin: 0 }}>
                Administración del Padrón Oficial
              </h2>
              <p style={{ fontSize: '0.8rem', color: '#64748b', margin: '0.2rem 0 0' }}>
                Fuente: portal web de SUNAT (sujesincapacidadOperativa.xlsx)
              </p>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
              <button
                type="button"
                onClick={() => setModalConfirmacionSync(true)}
                disabled={loadingSync}
                style={{
                  backgroundColor: '#1e40af',
                  color: '#ffffff',
                  border: 'none',
                  borderRadius: '6px',
                  padding: '0.5rem 1rem',
                  fontSize: '0.85rem',
                  fontWeight: '600',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.4rem',
                  cursor: loadingSync ? 'not-allowed' : 'pointer',
                  opacity: loadingSync ? 0.7 : 1,
                }}
              >
                <RefreshCw size={15} className={loadingSync ? 'spin' : ''} />
                <span>Actualizar desde SUNAT</span>
              </button>

              <label style={{
                backgroundColor: '#f1f5f9',
                color: '#334155',
                border: '1px solid #cbd5e1',
                borderRadius: '6px',
                padding: '0.5rem 1rem',
                fontSize: '0.85rem',
                fontWeight: '600',
                display: 'flex',
                alignItems: 'center',
                gap: '0.4rem',
                cursor: loadingSync ? 'not-allowed' : 'pointer',
              }}>
                <UploadCloud size={15} />
                <span>Cargar Excel oficial</span>
                <input
                  type="file"
                  accept=".xlsx"
                  onChange={handleCargaManual}
                  disabled={loadingSync}
                  style={{ display: 'none' }}
                />
              </label>
            </div>
          </div>

          {mensajeAdmin && (
            <div style={{
              marginTop: '0.75rem',
              padding: '0.65rem 1rem',
              backgroundColor: '#f0fdf4',
              color: '#166534',
              borderRadius: '6px',
              fontSize: '0.85rem',
              border: '1px solid #bbf7d0',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
            }}>
              <CheckCircle2 size={16} />
              <span>{mensajeAdmin}</span>
            </div>
          )}

          {errorAdmin && (
            <div style={{
              marginTop: '0.75rem',
              padding: '0.65rem 1rem',
              backgroundColor: '#fef2f2',
              color: '#991b1b',
              borderRadius: '6px',
              fontSize: '0.85rem',
              border: '1px solid #fecaca',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
            }}>
              <XCircle size={16} />
              <span>{errorAdmin}</span>
            </div>
          )}
        </div>
      )}

      {/* Formulario de Consulta por RUC */}
      <div style={{
        backgroundColor: '#ffffff',
        borderRadius: '10px',
        padding: '1.5rem',
        border: '1px solid #e2e8f0',
        boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
      }}>
        <form onSubmit={handleConsultar} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div>
            <label style={{ display: 'block', fontWeight: '700', fontSize: '0.85rem', color: '#1e293b', marginBottom: '0.4rem' }}>
              RUC DEL PROVEEDOR
            </label>
            <div style={{ display: 'flex', gap: '0.75rem', maxWidth: '500px' }}>
              <input
                type="text"
                maxLength={11}
                value={rucInput}
                onChange={(e) => {
                  const val = e.target.value.replace(/\D/g, '');
                  setRucInput(val);
                  setErrorConsulta(null);
                }}
                placeholder="Ingrese los 11 dígitos del RUC"
                style={{
                  flex: 1,
                  padding: '0.65rem 1rem',
                  fontSize: '1rem',
                  borderRadius: '6px',
                  border: errorConsulta ? '1px solid #ef4444' : '1px solid #cbd5e1',
                  outline: 'none',
                  fontFamily: 'monospace',
                  letterSpacing: '1px',
                }}
              />
              <button
                type="submit"
                disabled={loadingConsulta || rucInput.length !== 11}
                style={{
                  backgroundColor: '#0284c7',
                  color: '#ffffff',
                  border: 'none',
                  borderRadius: '6px',
                  padding: '0.65rem 1.5rem',
                  fontSize: '0.95rem',
                  fontWeight: '600',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.4rem',
                  cursor: (loadingConsulta || rucInput.length !== 11) ? 'not-allowed' : 'pointer',
                  opacity: (loadingConsulta || rucInput.length !== 11) ? 0.6 : 1,
                }}
              >
                <Search size={16} />
                <span>{loadingConsulta ? 'Consultando...' : 'Consultar'}</span>
              </button>
            </div>
          </div>

          {errorConsulta && (
            <div style={{ color: '#dc2626', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <AlertTriangle size={15} />
              <span>{errorConsulta}</span>
            </div>
          )}

          <div style={{ fontSize: '0.8rem', color: '#64748b' }}>
            La búsqueda en este módulo utiliza exclusivamente el RUC del emisor/proveedor contra el padrón local de resoluciones firmes.
          </div>
        </form>
      </div>

      {/* Resultados de la Consulta */}
      {resultado && (
        <div>
          {/* CASO 1: ENCONTRADO EN SSCO */}
          {resultado.estado === 'ENCONTRADO_SSCO' && (
            <div style={{
              backgroundColor: '#fffbeb',
              borderRadius: '10px',
              border: '2px solid #f59e0b',
              padding: '1.5rem',
              boxShadow: '0 4px 6px -1px rgba(245, 158, 11, 0.1)',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem' }}>
                <div style={{ backgroundColor: '#fef3c7', padding: '0.5rem', borderRadius: '8px' }}>
                  <AlertTriangle size={28} color="#d97706" />
                </div>
                <div>
                  <h3 style={{ fontSize: '1.15rem', fontWeight: '800', color: '#92400e', margin: 0 }}>
                    ⚠ RUC ENCONTRADO EN PADRÓN SSCO
                  </h3>
                  <div style={{
                    display: 'inline-block',
                    marginTop: '0.25rem',
                    backgroundColor: '#dc2626',
                    color: '#ffffff',
                    padding: '0.2rem 0.6rem',
                    borderRadius: '4px',
                    fontSize: '0.75rem',
                    fontWeight: '700',
                    letterSpacing: '0.5px',
                  }}>
                    REQUIERE REVISIÓN CONTABLE
                  </div>
                </div>
              </div>

              <p style={{ fontSize: '0.9rem', color: '#78350f', margin: '0 0 1.25rem' }}>
                {resultado.mensaje}
              </p>

              {/* Grid de Detalles Oficiales */}
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
                gap: '1rem',
                backgroundColor: '#ffffff',
                padding: '1.25rem',
                borderRadius: '8px',
                border: '1px solid #fde68a',
              }}>
                <div>
                  <span style={{ fontSize: '0.75rem', color: '#64748b', fontWeight: '600' }}>RUC DEL PROVEEDOR</span>
                  <div style={{ fontSize: '1rem', fontWeight: '700', color: '#1e293b', fontFamily: 'monospace' }}>
                    {resultado.ruc}
                  </div>
                </div>

                <div>
                  <span style={{ fontSize: '0.75rem', color: '#64748b', fontWeight: '600' }}>RAZÓN SOCIAL</span>
                  <div style={{ fontSize: '0.95rem', fontWeight: '700', color: '#1e293b' }}>
                    {resultado.razon_social || '-'}
                  </div>
                </div>

                <div style={{ gridColumn: 'span 2' }}>
                  <span style={{ fontSize: '0.75rem', color: '#64748b', fontWeight: '600' }}>DOMICILIO FISCAL</span>
                  <div style={{ fontSize: '0.85rem', color: '#334155' }}>
                    {resultado.domicilio_fiscal || '-'}
                  </div>
                </div>

                <div>
                  <span style={{ fontSize: '0.75rem', color: '#64748b', fontWeight: '600' }}>RESOLUCIÓN DE ATRIBUCIÓN</span>
                  <div style={{ fontSize: '0.85rem', fontWeight: '600', color: '#1e293b' }}>
                    {resultado.resolucion_atribucion || '-'}
                  </div>
                </div>

                <div>
                  <span style={{ fontSize: '0.75rem', color: '#64748b', fontWeight: '600' }}>FECHA EMISIÓN RESOLUCIÓN</span>
                  <div style={{ fontSize: '0.85rem', color: '#334155' }}>
                    {resultado.fecha_emision_resolucion || '-'}
                  </div>
                </div>

                <div>
                  <span style={{ fontSize: '0.75rem', color: '#64748b', fontWeight: '600' }}>FECHA DE FIRMEZA</span>
                  <div style={{ fontSize: '0.85rem', color: '#334155' }}>
                    {resultado.fecha_firmeza || '-'}
                  </div>
                </div>

                <div>
                  <span style={{ fontSize: '0.75rem', color: '#64748b', fontWeight: '600' }}>REPRESENTANTE LEGAL</span>
                  <div style={{ fontSize: '0.85rem', color: '#334155' }}>
                    {resultado.nombre_representante ? `${resultado.nombre_representante} (${resultado.doc_representante || '-'})` : '-'}
                  </div>
                </div>

                <div>
                  <span style={{ fontSize: '0.75rem', color: '#64748b', fontWeight: '600' }}>FECHA DE PUBLICACIÓN OFICIAL</span>
                  <div style={{ fontSize: '0.85rem', color: '#334155' }}>
                    {resultado.fecha_publicacion || '-'}
                  </div>
                </div>

                <div>
                  <span style={{ fontSize: '0.75rem', color: '#64748b', fontWeight: '600' }}>FECHA DEL PADRÓN CONSULTADO</span>
                  <div style={{ fontSize: '0.85rem', color: '#334155' }}>
                    {resultado.fecha_padron || '-'}
                  </div>
                </div>
              </div>

              <div style={{ marginTop: '1rem', fontSize: '0.8rem', color: '#92400e', fontStyle: 'italic' }}>
                * Conforme al D. Leg. 1532, los comprobantes emitidos por un Sujeto Sin Capacidad Operativa con resolución firme no permiten deducir crédito fiscal de IGV ni sustentar costo o gasto.
              </div>
            </div>
          )}

          {/* CASO 2: NO ENCONTRADO EN PADRÓN SSCO */}
          {resultado.estado === 'NO_ENCONTRADO' && (
            <div style={{
              backgroundColor: '#f8fafc',
              borderRadius: '10px',
              border: '2px solid #cbd5e1',
              padding: '1.5rem',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.75rem' }}>
                <div style={{ backgroundColor: '#e2e8f0', padding: '0.5rem', borderRadius: '8px' }}>
                  <Info size={26} color="#475569" />
                </div>
                <div>
                  <h3 style={{ fontSize: '1.1rem', fontWeight: '700', color: '#1e293b', margin: 0 }}>
                    RUC NO ENCONTRADO EN EL PADRÓN SSCO CONSULTADO
                  </h3>
                  <p style={{ margin: '0.2rem 0 0', fontSize: '0.85rem', color: '#64748b' }}>
                    RUC: <strong style={{ fontFamily: 'monospace' }}>{resultado.ruc}</strong> — Información oficial al: <strong>{resultado.fecha_padron || 'Fecha actual'}</strong>
                  </p>
                </div>
              </div>

              <div style={{
                backgroundColor: '#ffffff',
                padding: '1rem',
                borderRadius: '6px',
                border: '1px solid #e2e8f0',
                fontSize: '0.85rem',
                color: '#334155',
              }}>
                <p style={{ margin: '0 0 0.5rem', fontWeight: '600' }}>
                  {resultado.mensaje}
                </p>
                <p style={{ margin: 0, fontSize: '0.8rem', color: '#64748b' }}>
                  Aviso: Este resultado indica únicamente que el RUC no aparece en la relación oficial de Sujetos Sin Capacidad Operativa con resoluciones firmes publicada por SUNAT. No constituye una certificación general de validez comercial ni tributaria.
                </p>
              </div>
            </div>
          )}

          {/* CASO 3: NO VERIFICADO (PADRÓN NO DISPONIBLE) */}
          {resultado.estado === 'NO_VERIFICADO' && (
            <div style={{
              backgroundColor: '#fef2f2',
              borderRadius: '10px',
              border: '2px solid #f87171',
              padding: '1.5rem',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.75rem' }}>
                <div style={{ backgroundColor: '#fee2e2', padding: '0.5rem', borderRadius: '8px' }}>
                  <HelpCircle size={26} color="#dc2626" />
                </div>
                <div>
                  <h3 style={{ fontSize: '1.1rem', fontWeight: '700', color: '#991b1b', margin: 0 }}>
                    NO SE PUDO VERIFICAR EL RUC
                  </h3>
                  <p style={{ margin: '0.2rem 0 0', fontSize: '0.85rem', color: '#b91c1c' }}>
                    {resultado.mensaje}
                  </p>
                </div>
              </div>

              <div style={{
                backgroundColor: '#ffffff',
                padding: '1rem',
                borderRadius: '6px',
                border: '1px solid #fecaca',
                fontSize: '0.85rem',
                color: '#7f1d1d',
              }}>
                No existe actualmente un padrón SSCO cargado en el sistema para realizar la verificación. Contacte a un administrador para sincronizar o cargar el archivo oficial desde SUNAT.
              </div>
            </div>
          )}
        </div>
      )}

      {/* Modal Confirmación Sincronización */}
      {modalConfirmacionSync && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0,0,0,0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000,
        }}>
          <div style={{
            backgroundColor: '#ffffff',
            borderRadius: '10px',
            maxWidth: '480px',
            width: '90%',
            padding: '1.5rem',
            boxShadow: '0 20px 25px -5px rgba(0,0,0,0.2)',
          }}>
            <h3 style={{ fontSize: '1.15rem', fontWeight: '700', color: '#0f172a', margin: '0 0 0.75rem' }}>
              Confirmar Sincronización desde SUNAT
            </h3>
            <p style={{ fontSize: '0.9rem', color: '#475569', lineHeight: '1.5', margin: '0 0 1.25rem' }}>
              Se descargará y actualizará el padrón SSCO utilizando la fuente oficial de SUNAT. Si la actualización falla, se conservará la versión actual.
            </p>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
              <button
                type="button"
                onClick={() => setModalConfirmacionSync(false)}
                style={{
                  backgroundColor: '#f1f5f9',
                  color: '#475569',
                  border: '1px solid #cbd5e1',
                  borderRadius: '6px',
                  padding: '0.5rem 1rem',
                  fontSize: '0.85rem',
                  fontWeight: '600',
                  cursor: 'pointer',
                }}
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={handleEjecutarSync}
                style={{
                  backgroundColor: '#1e40af',
                  color: '#ffffff',
                  border: 'none',
                  borderRadius: '6px',
                  padding: '0.5rem 1.25rem',
                  fontSize: '0.85rem',
                  fontWeight: '600',
                  cursor: 'pointer',
                }}
              >
                Actualizar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ConsultaSSCO;
