import React from 'react';
import { cn } from '@/lib/utils';

interface NavItemProps {
  icon: React.ReactNode;
  label: string;
  isActive?: boolean;
  onClick?: () => void;
}

export const NavItem: React.FC<NavItemProps> = ({
  icon,
  label,
  isActive = false,
  onClick
}) => {
  return (
    <a
      href="#"
      className={cn(
        "flex items-center px-3 py-2 text-sm font-medium rounded-md",
        isActive
          ? "bg-guideon-light text-guideon-purple"
          : "text-gray-600 hover:bg-gray-50"
      )}
      onClick={(e) => {
        e.preventDefault();
        onClick && onClick();
      }}
    >
      <span className={cn("mr-3", isActive ? "text-guideon-purple" : "text-gray-500")}>
        {icon}
      </span>
      {label}
      {isActive && (
        <span className="ml-auto">
          <div className="w-2 h-2 rounded-full bg-guideon-purple"></div>
        </span>
      )}
    </a>
  );
};