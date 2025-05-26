import React from 'react';
import { useNavigate } from 'react-router-dom';

const GoToCareerPathwaysButton: React.FC = () => {
  const navigate = useNavigate();

  const handleClick = () => {
    navigate('/learning-pathways?tab=career&career=data%20analyst');
  };

  return (
    <button
      onClick={handleClick}
      className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition"
    >
      Go to Career Pathways
    </button>
  );
};

export default GoToCareerPathwaysButton;
