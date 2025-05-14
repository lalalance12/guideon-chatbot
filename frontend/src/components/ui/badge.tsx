import React from 'react';

interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: string;
}

const Badge: React.FC<BadgeProps> = ({ children, className, ...props }) => {
  return (
    <div className={`px-2 py-1 text-xs rounded ${className}`} {...props}>
      {children}
    </div>
  );
};

export { Badge };