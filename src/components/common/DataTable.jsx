import React from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import Button from './Button';

export function DataTable({
  columns = [],
  data = [],
  keyField = 'id',
  emptyMessage = 'No records found.',
  className = '',
  onRowClick,
}) {
  if (!data.length) {
    return (
      <div className="bg-white border border-[#E2E8F0] rounded-xl p-8 text-center text-sm text-[#64748B]">
        {emptyMessage}
      </div>
    );
  }

  return (
    <div className={`bg-white border border-[#E2E8F0] rounded-xl overflow-hidden shadow-xs ${className}`}>
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-[#E2E8F0] bg-[#F8FAFC]">
              {columns.map((col, idx) => (
                <th
                  key={idx}
                  className={`px-5 py-3 text-xs font-semibold text-[#475569] uppercase tracking-wider ${
                    col.align === 'right' ? 'text-right' : col.align === 'center' ? 'text-center' : 'text-left'
                  } ${col.width || ''}`}
                >
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-[#E2E8F0] text-sm text-[#0F172A]">
            {data.map((row, rowIdx) => (
              <tr
                key={row[keyField] || rowIdx}
                onClick={() => onRowClick?.(row)}
                className={`transition-colors ${
                  onRowClick
                    ? 'hover:bg-[#F8FAFC] cursor-pointer'
                    : 'hover:bg-[#F8FAFC]/50'
                }`}
              >
                {columns.map((col, colIdx) => (
                  <td
                    key={colIdx}
                    className={`px-5 py-3.5 ${
                      col.align === 'right'
                        ? 'text-right'
                        : col.align === 'center'
                        ? 'text-center'
                        : 'text-left'
                    }`}
                  >
                    {col.render ? col.render(row, rowIdx) : row[col.accessor]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function Pagination({
  currentPage = 1,
  totalPages = 1,
  onPageChange,
  className = '',
}) {
  if (totalPages <= 1) return null;

  return (
    <div className={`flex items-center justify-between py-3 px-2 ${className}`}>
      <span className="text-xs text-[#64748B]">
        Page <span className="font-semibold text-[#0F172A]">{currentPage}</span> of{' '}
        <span className="font-semibold text-[#0F172A]">{totalPages}</span>
      </span>

      <div className="flex items-center gap-1.5">
        <Button
          variant="outline"
          size="sm"
          disabled={currentPage <= 1}
          onClick={() => onPageChange?.(currentPage - 1)}
          icon={ChevronLeft}
        >
          Previous
        </Button>
        <Button
          variant="outline"
          size="sm"
          disabled={currentPage >= totalPages}
          onClick={() => onPageChange?.(currentPage + 1)}
          icon={ChevronRight}
          iconPosition="right"
        >
          Next
        </Button>
      </div>
    </div>
  );
}

export default DataTable;
