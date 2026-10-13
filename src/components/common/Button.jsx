import React from 'react';
import { Link } from 'react-router-dom';

/**
 * Standard DevRescue AI Button components.
 * Supports primary, secondary, outline, ghost, danger, and icon variants.
 */
export default function Button({
  children,
  to,
  href,
  onClick,
  type = 'button',
  variant = 'primary', // primary | secondary | outline | ghost | danger | dark
  size = 'md', // sm | md | lg
  disabled = false,
  loading = false,
  className = '',
  icon: Icon,
  iconPosition = 'left',
  arrow = false,
  ...props
}) {
  const baseStyles =
    'inline-flex items-center justify-center font-medium rounded-lg transition-all duration-150 active:scale-[0.98] select-none focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:opacity-50 disabled:pointer-events-none disabled:active:scale-100 cursor-pointer';

  const sizeStyles = {
    sm: 'text-xs px-3 py-1.5 gap-1.5',
    md: 'text-sm px-4 py-2 gap-2',
    lg: 'text-base px-5 py-2.5 gap-2.5',
  };

  const variantStyles = {
    primary:
      'bg-[#2563EB] hover:bg-[#1D4ED8] text-white shadow-sm focus:ring-[#2563EB]',
    secondary:
      'bg-[#EFF6FF] hover:bg-blue-100 text-[#2563EB] border border-[#BFDBFE] focus:ring-[#2563EB]',
    outline:
      'bg-white hover:bg-[#F8FAFC] text-[#0F172A] border border-[#E2E8F0] shadow-sm hover:border-[#CBD5E1] focus:ring-[#2563EB]',
    ghost:
      'bg-transparent hover:bg-[#F1F5F9] text-[#64748B] hover:text-[#0F172A] focus:ring-slate-400',
    danger:
      'bg-[#DC2626] hover:bg-[#B91C1C] text-white shadow-sm focus:ring-[#DC2626]',
    dark:
      'bg-[#0F172A] hover:bg-[#1E293B] text-white shadow-sm focus:ring-slate-900',
  };

  const appliedClass = `${baseStyles} ${sizeStyles[size] || sizeStyles.md} ${
    variantStyles[variant] || variantStyles.primary
  } ${className}`;

  const content = (
    <>
      {loading && (
        <svg
          className="animate-spin -ml-0.5 mr-2 h-4 w-4 text-current"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
        >
          <circle
            className="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="4"
          />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8v8z"
          />
        </svg>
      )}
      {!loading && Icon && iconPosition === 'left' && (
        <Icon className={size === 'sm' ? 'w-3.5 h-3.5' : 'w-4 h-4'} />
      )}
      <span>{children}</span>
      {!loading && Icon && iconPosition === 'right' && (
        <Icon className={size === 'sm' ? 'w-3.5 h-3.5' : 'w-4 h-4'} />
      )}
      {!loading && arrow && (
        <span className="transition-transform group-hover:translate-x-0.5">→</span>
      )}
    </>
  );

  if (to) {
    return (
      <Link to={to} className={appliedClass} {...props}>
        {content}
      </Link>
    );
  }

  if (href) {
    return (
      <a href={href} className={appliedClass} {...props}>
        {content}
      </a>
    );
  }

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled || loading}
      className={appliedClass}
      {...props}
    >
      {content}
    </button>
  );
}

export function PrimaryButton(props) {
  return <Button variant="primary" {...props} />;
}

export function SecondaryButton(props) {
  return <Button variant="outline" {...props} />;
}

export function IconButton({
  icon: Icon,
  title,
  onClick,
  size = 'md',
  variant = 'ghost',
  className = '',
  disabled = false,
  ...props
}) {
  const sizeStyles = {
    sm: 'p-1.5',
    md: 'p-2',
    lg: 'p-2.5',
  };

  const iconSizes = {
    sm: 'w-3.5 h-3.5',
    md: 'w-4 h-4',
    lg: 'w-5 h-5',
  };

  const variantStyles = {
    ghost: 'hover:bg-[#F1F5F9] text-[#64748B] hover:text-[#0F172A]',
    outline: 'border border-[#E2E8F0] hover:bg-[#F8FAFC] text-[#0F172A]',
    primary: 'bg-[#2563EB] hover:bg-[#1D4ED8] text-white',
  };

  return (
    <button
      type="button"
      title={title}
      aria-label={title}
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex items-center justify-center rounded-lg transition-colors active:scale-95 disabled:opacity-50 disabled:pointer-events-none cursor-pointer ${
        sizeStyles[size] || sizeStyles.md
      } ${variantStyles[variant] || variantStyles.ghost} ${className}`}
      {...props}
    >
      {Icon && <Icon className={iconSizes[size] || iconSizes.md} />}
    </button>
  );
}
