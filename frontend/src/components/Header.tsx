import React from 'react';
import { Search } from 'lucide-react';

const Header = () => {
  return (
    <div className="bg-white border-b border-gray-100 p-4">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-semibold text-gray-900">Learning Pathways</h1>
        <div className="relative w-64">
          {/* <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={16} />
         */}
        </div>
      </div>
    </div>
  );
};

export default Header;