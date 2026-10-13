import React, { useState } from 'react';

export default function Tooltip({
  content,
  children,
  position = 'top', // top | bottom | left | right
  className = '',
}) {
  const [visible, setVisible] = useState(false);

  const positionStyles = {
    top: 'bottom-full left-1/2 -translate-x-1/2 mb-2',
    bottom: 'top-full left-1/2 -translate-x-1/2 mt-2',
    left: 'right-full top-1/2 -translate-y-1/2 mr-2',
    right: 'left-full top-1/2 -translate-y-1/2 ml-2',
  };

  return (
    <div
      className={`relative inline-flex items-center ${className}`}
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={() => setVisible(false)}
      onFocus={() => setVisible(true)}
      onBlur={() => setVisible(false)}
    >
      {children}
      {visible && content && (
        <div
          role="tooltip"
          className={`absolute z-50 px-2.5 py-1 text-xs font-medium text-white bg-[#0F172A] rounded-md shadow-md whitespace-nowrap pointer-events-none transition-opacity duration-150 ${
            positionStyles[position] || positionStyles.top
          }`}
        >
          {content}
        </div>
      )}
    </div>
  );
}
