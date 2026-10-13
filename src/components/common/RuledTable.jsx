import React from 'react';

export default function RuledTable({
  columns = [],
  data = [],
  renderRow,
  emptyMessage = 'No records logged.',
  className = '',
}) {
  return (
    <div className={`w-full overflow-hidden rounded-xl border border-[#E2E8F0] bg-white shadow-xs ${className}`}>
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-[#E2E8F0] bg-[#F8FAFC]">
              {columns.map((col, idx) => (
                <th
                  key={idx}
                  className={`py-3.5 px-4 uppercase text-[11px] font-bold tracking-wider text-[#64748B] ${
                    col.align === 'right'
                      ? 'text-right'
                      : col.align === 'center'
                      ? 'text-center'
                      : 'text-left'
                  } ${col.className || ''}`}
                >
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-[#E2E8F0] text-xs">
            {data.length === 0 ? (
              <tr>
                <td
                  colSpan={columns.length}
                  className="py-12 text-center text-[#64748B] text-xs"
                >
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              data.map((item, idx) => (
                <tr
                  key={item.id || idx}
                  className="hover:bg-[#F8FAFC] transition-colors group"
                >
                  {renderRow ? (
                    renderRow(item, idx)
                  ) : (
                    columns.map((col, cIdx) => (
                      <td
                        key={cIdx}
                        className={`py-3.5 px-4 text-[#0F172A] ${
                          col.align === 'right'
                            ? 'text-right'
                            : col.align === 'center'
                            ? 'text-center'
                            : 'text-left'
                        }`}
                      >
                        {item[col.accessor || col.key] || '—'}
                      </td>
                    ))
                  )}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
