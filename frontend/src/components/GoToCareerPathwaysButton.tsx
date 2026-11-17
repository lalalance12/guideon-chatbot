import React from 'react';
import { useNavigate } from 'react-router-dom';

interface GoToCareerPathwaysButtonProps {
  role: string;
}

const GoToCareerPathwaysButton: React.FC<GoToCareerPathwaysButtonProps> = ({ role }) => {
  const navigate = useNavigate();
  
  // Convert role title to kebab-case ID format (e.g., "data analyst" -> "data-analyst")
  const roleId = role.toLowerCase().trim().replace(/\s+/g, '-');
  const encodedRoleId = encodeURIComponent(roleId);

  const handleClick = () => {
    console.log(`Navigating to career path for role: ${role} (ID: ${roleId})`);
    navigate(`/learning-pathways?tab=career&career=${encodedRoleId}`);
  };

  return (
    <button
      onClick={handleClick}
      className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition"
    >
      {`Go to ${role} Career Pathway`}
    </button>
  );
};

export default GoToCareerPathwaysButton;
