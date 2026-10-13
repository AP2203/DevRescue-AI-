import React from 'react';

export default function Badge({
  children,
  variant = 'default', // default | blue | success | warning | error | demo | purple
  size = 'md', // sm | md
  dot = false,
  className = '',
  ...props
}) {
  const sizeStyles = {
    sm: 'text-[11px] px-2 py-0.5 font-medium',
    md: 'text-xs px-2.5 py-1 font-medium',
  };

  const variantStyles = {
    default: 'bg-[#F1F5F9] text-[#475569] border border-[#E2E8F0]',
    blue: 'bg-[#EFF6FF] text-[#2563EB] border border-[#BFDBFE]',
    success: 'bg-[#F0FDF4] text-[#16A34A] border border-[#BBF7D0]',
    warning: 'bg-[#FFFBEB] text-[#D97706] border border-[#FDE68A]',
    error: 'bg-[#FEF2F2] text-[#DC2626] border border-[#FECACA]',
    demo: 'bg-[#EFF6FF] text-[#2563EB] border border-[#93C5FD] font-mono tracking-wide uppercase',
    purple: 'bg-[#F5F3FF] text-[#7C3AED] border border-[#DDD6FE]',
  };

  const dotColors = {
    default: 'bg-[#64748B]',
    blue: 'bg-[#2563EB]',
    success: 'bg-[#16A34A]',
    warning: 'bg-[#D97706]',
    error: 'bg-[#DC2626]',
    demo: 'bg-[#2563EB]',
    purple: 'bg-[#7C3AED]',
  };

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full select-none ${
        sizeStyles[size] || sizeStyles.md
      } ${variantStyles[variant] || variantStyles.default} ${className}`}
      {...props}
    >
      {dot && (
        <span
          className={`w-1.5 h-1.5 rounded-full ${
            dotColors[variant] || dotColors.default
          }`}
        />
      )}
      {children}
    </span>
  );
}

export function StatusBadge({ status, className = '' }) {
  const normalized = String(status || '').toUpperCase().replace(/[\s-]/g, '_');

  switch (normalized) {
    case 'COMPLETE':
    case 'PASSED':
    case 'FIXED':
    case 'MERGED':
    case 'SUCCESS':
      return (
        <Badge variant="success" dot={true} className={className}>
          {status === 'MERGED' ? 'Merged' : status === 'FIXED' ? 'Fixed' : 'Passed'}
        </Badge>
      );

    case 'IN_PROGRESS':
    case 'RUNNING':
    case 'INVESTIGATING':
      return (
        <span
          className={`inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full bg-[#EFF6FF] text-[#2563EB] border border-[#BFDBFE] ${className}`}
        >
          <span className="w-1.5 h-1.5 rounded-full bg-[#2563EB] animate-ping" />
          <span>In Progress</span>
        </span>
      );

    case 'TESTING':
      return (
        <span
          className={`inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full bg-[#EFF6FF] text-[#2563EB] border border-[#BFDBFE] ${className}`}
        >
          <span className="w-1.5 h-1.5 rounded-full bg-[#2563EB] animate-pulse" />
          <span>Testing</span>
        </span>
      );

    case 'READY_FOR_REVIEW':
    case 'PR_READY':
      return (
        <Badge variant="blue" dot={true} className={className}>
          PR Ready
        </Badge>
      );

    case 'OPEN':
      return (
        <Badge variant="blue" dot={true} className={className}>
          Open
        </Badge>
      );

    case 'FAILED':
    case 'ERROR':
    case 'REJECTED':
      return (
        <Badge variant="error" dot={true} className={className}>
          {status === 'REJECTED' ? 'Rejected' : 'Failed'}
        </Badge>
      );

    case 'PENDING':
    case 'QUEUED':
    default:
      return (
        <Badge variant="default" dot={true} className={className}>
          {status || 'Pending'}
        </Badge>
      );
  }
}
