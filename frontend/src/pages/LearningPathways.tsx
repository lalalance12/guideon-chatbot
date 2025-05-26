import React, { useState } from 'react';
import { useLocation } from 'react-router-dom';
import PathwaySelector from '@/components/PathwaySelector';
import { PathwayType } from '@/types/pathways';
import SkillPathwayCard from '@/components/SkillPathwayCard';
import CareerPathwayCard from '@/components/CareerPathwayCard';
import { skillPathways, careerPathways } from '@/data/pathwayData';
import Header from '@/components/Header';

const LearningPathways: React.FC = () => {
  const location = useLocation();
  const params = new URLSearchParams(location.search);
  const initialTab = params.get('tab') === 'career' ? 'career' : 'skill';
  const [activePathwayType, setActivePathwayType] = useState<PathwayType>(initialTab);
  const careerToExpand = params.get('career'); // This is the kebab-case ID (e.g., "data-analyst")

  // Log the search parameter to debug
  console.log('Career ID to expand:', careerToExpand);
  
  // Find matching pathways by career pathway ID, not level titles
  const matchingPathways = careerToExpand 
    ? careerPathways.filter(pathway => pathway.id === careerToExpand)
    : [];
  
  console.log('Found matching pathways:', matchingPathways.length);
  console.log('Matching pathways:', matchingPathways.map(p => p.id));

  return (
    <div className="flex-1 flex flex-col bg-guideon-bg min-h-screen">
      <Header />
      <div className="bg-[#f6f8ff] p-6 flex-1">
        <div className="max-w-4xl mx-auto">
          <PathwaySelector 
            activeType={activePathwayType} 
            setActiveType={setActivePathwayType} 
          />
          
          {activePathwayType === 'skill' ? (
            <>
              <h2 className="text-xl font-medium text-gray-800 mb-4">Skill-based Learning Pathways</h2>
              <p className="text-gray-600 mb-6">
                Select a learning pathway to develop a specific skill through structured courses
              </p>
              {skillPathways.map((pathway) => (
                <SkillPathwayCard key={pathway.id} pathway={pathway} />
              ))}
            </>
          ) : (
            <>
              <h2 className="text-xl font-medium text-gray-800 mb-4">Career Progression Pathways</h2>
              <p className="text-gray-600 mb-6">
                Explore career paths and the skills required at each level
              </p>
              
              {/* If we have a specific career to show, filter and highlight it */}
              {careerToExpand && matchingPathways.length > 0 ? (
                <>
                  <div className="mb-4 p-3 bg-blue-50 border border-blue-100 rounded-lg">
                    <p className="text-blue-800">
                      Showing career pathway for: <strong>{matchingPathways[0].title}</strong>
                    </p>
                  </div>
                  {matchingPathways.map((pathway) => (
                    <CareerPathwayCard
                      key={pathway.id}
                      pathway={pathway}
                      autoExpand={true}
                      highlightRole={careerToExpand} // Pass the ID for highlighting
                    />
                  ))}
                </>
              ) : (
                // Show all pathways if no specific career or no matches
                careerPathways.map((pathway) => (
                  <CareerPathwayCard
                    key={pathway.id}
                    pathway={pathway}
                  />
                ))
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default LearningPathways;
