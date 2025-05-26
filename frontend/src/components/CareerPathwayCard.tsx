import React, { useState, useEffect } from 'react';
import { CareerPathway } from '@/types/pathways';
import { Button } from '@/components/ui/button';
import { ChevronDown, ChevronUp, ExternalLink } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { Tooltip } from '@/components/ui/tooltip';

interface CourseData {
  skill: string;
  course_info: {
    course_title: string;
    course_provider: string;
    course_rating: number;
    course_description: string;
    price: string;
    course_url: string;
  }[];
}

interface CareerPathwayCardProps {
  pathway: CareerPathway;
  autoExpand?: boolean;
  highlightRole?: string; // This will now be the career ID (kebab-case)
}

const CareerPathwayCard: React.FC<CareerPathwayCardProps> = ({ 
  pathway, 
  autoExpand,
  highlightRole 
}) => {
  const [expanded, setExpanded] = useState(!!autoExpand);
  const [skillCourses, setSkillCourses] = useState<Record<string, string>>({});
  
  // Check if this pathway should be highlighted based on career ID
  const shouldHighlight = highlightRole && pathway.id === highlightRole;
  
  // Automatically expand when this pathway is highlighted
  useEffect(() => {
    if (autoExpand || shouldHighlight) {
      setExpanded(true);
    }
  }, [autoExpand, shouldHighlight, pathway.id]);

  // Load skill courses data
  useEffect(() => {
    const fetchSkillCourses = async () => {
      try {
        // Fetch from our new API endpoint
        const response = await fetch('/api/skill-courses/');
        
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data: CourseData[] = await response.json();
        
        // Create a map of skill names to their first course URL
        const skillMap: Record<string, string> = {};
        data.forEach(item => {
          if (item.course_info && item.course_info.length > 0) {
            skillMap[item.skill.toLowerCase()] = item.course_info[0].course_url;
          }
        });
        
        setSkillCourses(skillMap);
      } catch (error) {
        console.error('Failed to load skill courses:', error);
        
        // Fallback to hardcoded data if API fails
        setSkillCourses({
          "python programming": "https://www.coursera.org/specializations/python",
          "data analysis": "https://www.coursera.org/learn/data-analysis-with-python",
          "machine learning": "https://www.coursera.org/learn/machine-learning",
          "data science": "https://www.edx.org/professional-certificate/ibm-data-science",
          "applications development": "https://www.classcentral.com/course/androidpart2-3076"
        });
      }
    };

    fetchSkillCourses();
  }, []);

  // Function to check if a skill has a matching course
  const getSkillCourseUrl = (skillName: string): string | null => {
    return skillCourses[skillName.toLowerCase()] || null;
  };

  return (
    <div className={cn(
      "bg-white rounded-lg border border-gray-100 overflow-hidden mb-4 transition-shadow hover:shadow-md",
      shouldHighlight ? "ring-2 ring-blue-300 shadow-lg" : ""
    )}>
      <div className="p-5">
        <div className="flex justify-between items-start">
          <div>
            <h3 className="font-medium text-lg text-gray-900">{pathway.title}</h3>
            {/* <p className="text-gray-600 text-sm mt-1">{pathway.description}</p> */}
          </div>
          <Button
            variant="ghost"
            size="sm"
            className="h-8 w-8 p-0"
            onClick={() => setExpanded(!expanded)}
          >
            {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </Button>
        </div>
        <div className="flex mt-3 items-center">
          <Badge variant="outline" className="mr-2 text-xs bg-guideon-light border-none text-guideon-purple">
            {pathway.field}
          </Badge>
          <Badge variant="outline" className="mr-2 text-xs bg-guideon-light border-none text-guideon-purple">
            {pathway.levels.length} Career Levels
          </Badge>
          {shouldHighlight && (
            <Badge variant="outline" className="text-xs bg-blue-100 border-none text-blue-700">
              Selected Career
            </Badge>
          )}
        </div>
      </div>

      <div
        className={cn(
          "overflow-auto transition-all duration-300 ease-in-out",
          expanded ? "max-h-[2000px] border-t border-gray-100" : "max-h-0"
        )}
      >
        <div className="p-5 space-y-4">
          {pathway.levels.map((level, index) => (
            <div 
              key={index} 
              className={cn(
                "flex",
                shouldHighlight ? "bg-blue-50 p-2 rounded-lg -mx-2" : ""
              )}
            >
              <div className="mr-4 flex flex-col items-center">
                <div className={cn(
                  "rounded-full w-6 h-6 flex items-center justify-center text-xs font-medium",
                  shouldHighlight 
                    ? "bg-blue-200 text-blue-800" 
                    : "bg-guideon-light text-guideon-purple"
                )}>
                  {index + 1}
                </div>
                {index < pathway.levels.length - 1 && (
                  <div className="w-0.5 h-full bg-gray-200 my-1" />
                )}
              </div>
              <div className={cn(
                "rounded-lg p-3 flex-1",
                shouldHighlight ? "bg-white" : "bg-guideon-light"
              )}>
                <div className="flex justify-between items-start">
                  <h4 className="font-medium text-gray-900">{level.title}</h4>
                  <Badge variant="outline" className="text-xs border-none bg-white/60 text-gray-600">
                    {level.level}
                  </Badge>
                </div>
                {level.description && (
                  <p className="text-sm text-gray-600 mt-1">{level.description}</p>
                )}
                <div className="mt-3">
                  <h5 className="text-sm font-medium text-gray-700 mb-2">Required Skills:</h5>
                  <div className="space-y-2">
                    {level.requiredSkills.slice(0, 10).map((skill) => {
                      const courseUrl = getSkillCourseUrl(skill.name);
                      return (
                        <div key={skill.id} className="bg-white p-2 rounded-md">
                          <div className="flex justify-between">
                            {courseUrl ? (
                              <Tooltip content={`View courses for ${skill.name}`}>
                                <a 
                                  href={courseUrl} 
                                  target="_blank" 
                                  rel="noopener noreferrer"
                                  className="text-sm font-medium text-guideon-purple hover:text-guideon-purple/80 flex items-center"
                                >
                                  {skill.name} <ExternalLink size={12} className="ml-1" />
                                </a>
                              </Tooltip>
                            ) : (
                              <span className="text-sm font-medium">{skill.name}</span>
                            )}
                            <Badge variant="outline" className="text-xs border-none bg-guideon-light/50 text-gray-600">
                              {skill.level}
                            </Badge>
                          </div>
                          <p className="text-xs text-gray-500 mt-1">{skill.description}</p>
                        </div>
                      );
                    })}
                    {level.requiredSkills.length > 10 && (
                      <p className="text-xs text-gray-500 italic">
                        +{level.requiredSkills.length - 10} more skills
                      </p>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ))}
          <div className="flex justify-end pt-2">
            <Button className="bg-guideon-purple hover:bg-guideon-purple/90 text-white">Explore Career</Button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default CareerPathwayCard;