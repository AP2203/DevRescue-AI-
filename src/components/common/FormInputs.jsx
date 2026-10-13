import React from 'react';
import { Search } from 'lucide-react';

export function Input({
  label,
  helper,
  error,
  type = 'text',
  value,
  onChange,
  placeholder,
  required = false,
  disabled = false,
  className = '',
  icon: Icon,
  ...props
}) {
  return (
    <div className={`space-y-1.5 ${className}`}>
      {label && (
        <label className="block text-xs font-semibold text-[#0F172A] uppercase tracking-wider">
          {label} {required && <span className="text-[#DC2626]">*</span>}
        </label>
      )}
      <div className="relative">
        {Icon && (
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-[#64748B]">
            <Icon className="w-4 h-4" />
          </div>
        )}
        <input
          type={type}
          value={value}
          onChange={onChange}
          placeholder={placeholder}
          required={required}
          disabled={disabled}
          className={`w-full rounded-lg bg-white border ${
            error ? 'border-[#DC2626]' : 'border-[#E2E8F0]'
          } ${
            Icon ? 'pl-9' : 'pl-3.5'
          } pr-3.5 py-2 text-sm text-[#0F172A] placeholder-[#94A3B8] transition-colors focus:outline-none focus:ring-2 focus:ring-[#2563EB]/20 focus:border-[#2563EB] disabled:bg-[#F8FAFC] disabled:cursor-not-allowed`}
          {...props}
        />
      </div>
      {error && <p className="text-xs text-[#DC2626]">{error}</p>}
      {!error && helper && <p className="text-xs text-[#64748B]">{helper}</p>}
    </div>
  );
}

export function Textarea({
  label,
  helper,
  error,
  value,
  onChange,
  placeholder,
  rows = 4,
  required = false,
  disabled = false,
  className = '',
  ...props
}) {
  return (
    <div className={`space-y-1.5 ${className}`}>
      {label && (
        <label className="block text-xs font-semibold text-[#0F172A] uppercase tracking-wider">
          {label} {required && <span className="text-[#DC2626]">*</span>}
        </label>
      )}
      <textarea
        rows={rows}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        required={required}
        disabled={disabled}
        className={`w-full rounded-lg bg-white border ${
          error ? 'border-[#DC2626]' : 'border-[#E2E8F0]'
        } px-3.5 py-2 text-sm text-[#0F172A] placeholder-[#94A3B8] transition-colors focus:outline-none focus:ring-2 focus:ring-[#2563EB]/20 focus:border-[#2563EB] disabled:bg-[#F8FAFC] disabled:cursor-not-allowed`}
        {...props}
      />
      {error && <p className="text-xs text-[#DC2626]">{error}</p>}
      {!error && helper && <p className="text-xs text-[#64748B]">{helper}</p>}
    </div>
  );
}

export function Select({
  label,
  helper,
  error,
  value,
  onChange,
  options = [],
  required = false,
  disabled = false,
  className = '',
  ...props
}) {
  return (
    <div className={`space-y-1.5 ${className}`}>
      {label && (
        <label className="block text-xs font-semibold text-[#0F172A] uppercase tracking-wider">
          {label} {required && <span className="text-[#DC2626]">*</span>}
        </label>
      )}
      <select
        value={value}
        onChange={onChange}
        required={required}
        disabled={disabled}
        className={`w-full rounded-lg bg-white border ${
          error ? 'border-[#DC2626]' : 'border-[#E2E8F0]'
        } px-3.5 py-2 text-sm text-[#0F172A] transition-colors focus:outline-none focus:ring-2 focus:ring-[#2563EB]/20 focus:border-[#2563EB] disabled:bg-[#F8FAFC] disabled:cursor-not-allowed cursor-pointer`}
        {...props}
      >
        {options.map((opt) => {
          const val = typeof opt === 'object' ? opt.value : opt;
          const labelText = typeof opt === 'object' ? opt.label : opt;
          return (
            <option key={val} value={val}>
              {labelText}
            </option>
          );
        })}
      </select>
      {error && <p className="text-xs text-[#DC2626]">{error}</p>}
      {!error && helper && <p className="text-xs text-[#64748B]">{helper}</p>}
    </div>
  );
}

export function SearchInput({
  value,
  onChange,
  placeholder = 'Search repositories...',
  className = '',
  ...props
}) {
  return (
    <div className={`relative ${className}`}>
      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-[#64748B]">
        <Search className="w-4 h-4" />
      </div>
      <input
        type="text"
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        className="w-full rounded-lg bg-white border border-[#E2E8F0] pl-9 pr-3.5 py-2 text-sm text-[#0F172A] placeholder-[#94A3B8] transition-colors focus:outline-none focus:ring-2 focus:ring-[#2563EB]/20 focus:border-[#2563EB]"
        {...props}
      />
    </div>
  );
}

export default Input;
