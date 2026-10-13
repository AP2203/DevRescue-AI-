import React from 'react';

export default function UnderlineSelect({
  label,
  value,
  onChange,
  options = [],
  disabled = false,
  className = '',
  id,
  name,
  required = false,
  error,
}) {
  const selectId = id || name || (label ? label.toLowerCase().replace(/\s+/g, '-') : undefined);

  return (
    <div className={`w-full flex flex-col ${className}`}>
      {label && (
        <label
          htmlFor={selectId}
          className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-[#0F172A] select-none flex items-center justify-between"
        >
          <span>{label}</span>
          {required && <span className="text-[#DC2626] font-normal text-xs">*Required</span>}
        </label>
      )}
      <div className="relative flex items-center">
        <select
          id={selectId}
          name={name}
          value={value}
          onChange={onChange}
          disabled={disabled}
          className={`w-full bg-white border ${
            error ? 'border-[#DC2626]' : 'border-[#E2E8F0]'
          } rounded-lg py-2.5 px-3.5 text-sm text-[#0F172A] focus:outline-none focus:ring-2 focus:ring-[#2563EB]/20 focus:border-[#2563EB] transition-all disabled:bg-[#F8FAFC] disabled:opacity-50 cursor-pointer appearance-none pr-9`}
        >
          {options.map((opt) => {
            const val = typeof opt === 'object' ? opt.value : opt;
            const labelText = typeof opt === 'object' ? opt.label : opt;
            return (
              <option key={val} value={val} className="text-[#0F172A] bg-white">
                {labelText}
              </option>
            );
          })}
        </select>
        <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-[#64748B]">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </div>
      {error && <p className="text-xs text-[#DC2626] mt-1">{error}</p>}
    </div>
  );
}
