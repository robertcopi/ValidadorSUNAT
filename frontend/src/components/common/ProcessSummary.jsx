import React from 'react';
import { FileText, CheckCircle2, XCircle, AlertTriangle, AlertOctagon } from 'lucide-react';

/**
 * Tarjetas de resumen métrico para procesos masivos y dashboard.
 * Totalmente dinámico (1, 3, 25, 100, 220, 500+ items).
 */
export const ProcessSummary = ({
  total = 0,
  validos = 0,
  noValidos = 0,
  observados = 0,
  errores = 0,
  tituloTotal = 'TOTAL COMPROBANTES',
  subtituloTotal = 'Comprobantes del lote',
}) => {
  const tot = Number(total) || 0;
  const val = Number(validos) || 0;
  const noVal = Number(noValidos) || 0;
  const obs = Number(observados) || 0;
  const err = Number(errores) || 0;

  const pctVal = tot > 0 ? ((val / tot) * 100).toFixed(1) : '0.0';
  const pctNoVal = tot > 0 ? ((noVal / tot) * 100).toFixed(1) : '0.0';
  const pctObs = tot > 0 ? ((obs / tot) * 100).toFixed(1) : '0.0';
  const pctErr = tot > 0 ? ((err / tot) * 100).toFixed(1) : '0.0';

  const cards = [
    {
      title: tituloTotal,
      value: tot,
      pct: '100%',
      icon: FileText,
      color: '#1e40af',
      bgColor: '#eff6ff',
      borderColor: '#bfdbfe',
      textColor: '#1e3a8a',
      subtitle: subtituloTotal,
    },
    {
      title: 'VÁLIDOS',
      value: val,
      pct: `${pctVal}%`,
      icon: CheckCircle2,
      color: '#16a34a',
      bgColor: '#f0fdf4',
      borderColor: '#bbf7d0',
      textColor: '#15803d',
      subtitle: 'Comprobantes aceptados',
    },
    {
      title: 'NO VÁLIDOS',
      value: noVal,
      pct: `${pctNoVal}%`,
      icon: XCircle,
      color: '#dc2626',
      bgColor: '#fef2f2',
      borderColor: '#fecaca',
      textColor: '#b91c1c',
      subtitle: 'Rechazados o no existen',
    },
    {
      title: 'OBSERVADOS',
      value: obs,
      pct: `${pctObs}%`,
      icon: AlertTriangle,
      color: '#d97706',
      bgColor: '#fffbeb',
      borderColor: '#fde68a',
      textColor: '#b45309',
      subtitle: 'Con inconsistencias',
    },
    {
      title: 'ERRORES',
      value: err,
      pct: `${pctErr}%`,
      icon: AlertOctagon,
      color: '#6b7280',
      bgColor: '#f9fafb',
      borderColor: '#e5e7eb',
      textColor: '#4b5563',
      subtitle: 'Fallo de conexión o red',
    },
  ];

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
        gap: '1rem',
        marginBottom: '1.5rem',
      }}
    >
      {cards.map((card, idx) => {
        const Icon = card.icon;
        return (
          <div
            key={idx}
            style={{
              backgroundColor: card.bgColor,
              border: `1px solid ${card.borderColor}`,
              borderRadius: '10px',
              padding: '1rem 1.25rem',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
              transition: 'transform 0.15s ease, box-shadow 0.15s ease',
            }}
          >
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: '0.4rem',
              }}
            >
              <span
                style={{
                  fontSize: '0.75rem',
                  fontWeight: '700',
                  color: card.textColor,
                  letterSpacing: '0.04em',
                }}
              >
                {card.title}
              </span>
              <div
                style={{
                  width: '28px',
                  height: '28px',
                  borderRadius: '50%',
                  backgroundColor: '#ffffff',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: card.color,
                  boxShadow: '0 1px 2px rgba(0,0,0,0.05)',
                }}
              >
                <Icon size={16} />
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.5rem', margin: '0.2rem 0' }}>
              <span
                style={{
                  fontSize: '1.85rem',
                  fontWeight: '800',
                  color: card.textColor,
                  lineHeight: '1',
                }}
              >
                {card.value}
              </span>
              <span
                style={{
                  fontSize: '0.85rem',
                  fontWeight: '700',
                  color: card.color,
                }}
              >
                ({card.pct})
              </span>
            </div>

            <div style={{ fontSize: '0.73rem', color: '#64748b', marginTop: '0.25rem' }}>
              {card.subtitle}
            </div>
          </div>
        );
      })}
    </div>
  );
};
