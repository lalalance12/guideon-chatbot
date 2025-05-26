import React, { useState } from 'react';
import { useLocation } from 'react-router-dom';
import PathwaySelector from '@/components/PathwaySelector';
import { PathwayType } from '@/types/pathways';
import SkillPathwayCard from '@/components/SkillPathwayCard';
import CareerPathwayCard from '@/components/CareerPathwayCard';
import { skillPathways, careerPathways } from '@/data/pathwayData'; // Updated import
import Header from '@/components/Header'; // Import Header

const LearningPathways: React.FC = () => {
  const location = useLocation();
  const params = new URLSearchParams(location.search);
  const initialTab = params.get('tab') === 'career' ? 'career' : 'skill';
  const [activePathwayType, setActivePathwayType] = useState<PathwayType>(initialTab);
  const careerToExpand = params.get('career');

  return (
    <div className="flex-1 flex flex-col bg-guideon-bg min-h-screen">
      <Header /> {/* Add Header component */}
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
              {careerToExpand
                ? careerPathways
                    .filter((pathway) => pathway.title.toLowerCase() === careerToExpand.toLowerCase())
                    .map((pathway) => (
                      <CareerPathwayCard
                        key={pathway.id}
                        pathway={pathway}
                        autoExpand={true}
                      />
                    ))
                : careerPathways.map((pathway) => (
                    <CareerPathwayCard
                      key={pathway.id}
                      pathway={pathway}
                    />
                  ))}
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default LearningPathways;
