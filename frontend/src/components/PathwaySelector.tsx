import React from 'react';
import { cn } from '@/lib/utils';
import { PathwayType } from '../types/pathways';

interface PathwaySelectorProps {
  activeType: PathwayType;
  setActiveType: (type: PathwayType) => void;
}

const PathwaySelector: React.FC<PathwaySelectorProps> = ({ activeType, setActiveType }) => {
  return (
    <div className="flex w-full max-w-md bg-white rounded-lg border border-gray-200 p-1 mb-6">
      <button
        className={cn(
          "flex-1 py-2 px-4 text-sm font-medium rounded-md transition-colors",
          activeType === 'skill'
            ? "bg-guideon-purple text-white"
            : "bg-white text-gray-700 hover:bg-gray-100"
        )}
        onClick={() => setActiveType('skill')}
      >
        Skill Pathways
      </button>
      <button
        className={cn(
          "flex-1 py-2 px-4 text-sm font-medium rounded-md transition-colors",
          activeType === 'career'
            ? "bg-guideon-purple text-white"
            : "bg-white text-gray-700 hover:bg-gray-100"
        )}
        onClick={() => setActiveType('career')}
      >
        Career Pathways
      </button>
    </div>
  );
};

export default PathwaySelector;