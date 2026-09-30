import React from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';

export const Pagination = ({
  page,
  totalPages,
  totalItems,
  pageSize,
  onPageChange,
  onPageSizeChange,
}) => {
  if (!totalItems || totalItems === 0) return null;

  const maxPage = Math.max(1, totalPages || 1);
  const startItem = (page - 1) * pageSize + 1;
  const endItem = Math.min(page * pageSize, totalItems);

  // Generar números de página a mostrar
  const pagesToShow = [];
  const delta = 2;
  for (let i = Math.max(1, page - delta); i <= Math.min(maxPage, page + delta); i++) {
    pagesToShow.push(i);
  }

  return (
    <div
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0.85rem 1.25rem',
        backgroundColor: '#ffffff',
        borderTop: '1px solid var(--color-border, #e2e8f0)',
        gap: '0.75rem',
        fontSize: '0.85rem',
        color: '#64748b',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
        <span>
          Mostrando <strong style={{ color: '#0f172a' }}>{startItem}</strong> -{' '}
          <strong style={{ color: '#0f172a' }}>{endItem}</strong> de{' '}
          <strong style={{ color: '#0f172a' }}>{totalItems}</strong> registros
        </span>

        {onPageSizeChange && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <span style={{ fontSize: '0.78rem' }}>Por página:</span>
            <select
              value={pageSize}
              onChange={(e) => onPageSizeChange(Number(e.target.value))}
              style={{
                padding: '0.2rem 0.4rem',
                borderRadius: '4px',
                border: '1px solid #cbd5e1',
                fontSize: '0.78rem',
                backgroundColor: '#ffffff',
              }}
            >
              <option value={10}>10</option>
              <option value={20}>20</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
            </select>
          </div>
        )}
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
        <button
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: '32px',
            height: '32px',
            borderRadius: '6px',
            border: '1px solid #cbd5e1',
            backgroundColor: page <= 1 ? '#f8fafc' : '#ffffff',
            color: page <= 1 ? '#94a3b8' : '#0f172a',
            cursor: page <= 1 ? 'not-allowed' : 'pointer',
            transition: 'all 0.15s ease',
          }}
          title="Página anterior"
        >
          <ChevronLeft size={16} />
        </button>

        {pagesToShow[0] > 1 && (
          <>
            <button
              onClick={() => onPageChange(1)}
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '6px',
                border: '1px solid #cbd5e1',
                backgroundColor: '#ffffff',
                cursor: 'pointer',
              }}
            >
              1
            </button>
            {pagesToShow[0] > 2 && <span style={{ padding: '0 0.2rem' }}>...</span>}
          </>
        )}

        {pagesToShow.map((p) => {
          const isActive = p === page;
          return (
            <button
              key={p}
              onClick={() => onPageChange(p)}
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '6px',
                border: isActive ? 'none' : '1px solid #cbd5e1',
                backgroundColor: isActive ? 'var(--color-primary, #1e40af)' : '#ffffff',
                color: isActive ? '#ffffff' : '#0f172a',
                fontWeight: isActive ? '700' : '500',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
            >
              {p}
            </button>
          );
        })}

        {pagesToShow[pagesToShow.length - 1] < maxPage && (
          <>
            {pagesToShow[pagesToShow.length - 1] < maxPage - 1 && (
              <span style={{ padding: '0 0.2rem' }}>...</span>
            )}
            <button
              onClick={() => onPageChange(maxPage)}
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '6px',
                border: '1px solid #cbd5e1',
                backgroundColor: '#ffffff',
                cursor: 'pointer',
              }}
            >
              {maxPage}
            </button>
          </>
        )}

        <button
          onClick={() => onPageChange(page + 1)}
          disabled={page >= maxPage}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: '32px',
            height: '32px',
            borderRadius: '6px',
            border: '1px solid #cbd5e1',
            backgroundColor: page >= maxPage ? '#f8fafc' : '#ffffff',
            color: page >= maxPage ? '#94a3b8' : '#0f172a',
            cursor: page >= maxPage ? 'not-allowed' : 'pointer',
            transition: 'all 0.15s ease',
          }}
          title="Página siguiente"
        >
          <ChevronRight size={16} />
        </button>
      </div>
    </div>
  );
};
