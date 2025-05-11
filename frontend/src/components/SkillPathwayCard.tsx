import React, { useState } from 'react';
import { SkillPathway } from '@/types/pathways';
import { Button } from '@/components/ui/button';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

interface SkillPathwayCardProps {
  pathway: SkillPathway;
}

const SkillPathwayCard: React.FC<SkillPathwayCardProps> = ({ pathway }) => {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="bg-white rounded-lg border border-gray-100 overflow-hidden mb-4 transition-shadow hover:shadow-md">
      <div className="p-5">
        <div className="flex justify-between items-start">
          <div>
            <h3 className="font-medium text-lg text-gray-900">{pathway.title}</h3>
            <p className="text-gray-600 text-sm mt-1">{pathway.description}</p>
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
            {pathway.courses.length} Courses
          </Badge>
          <Badge variant="outline" className="text-xs bg-guideon-light border-none text-guideon-purple">
            Sequential
          </Badge>
        </div>
      </div>

      <div
        className={cn(
          "overflow-hidden transition-all duration-300 ease-in-out",
          expanded ? "max-h-[1000px] border-t border-gray-100" : "max-h-0"
        )}
      >
        <div className="p-5 space-y-4">
          {pathway.courses.map((course, index) => (
            <div key={course.id} className="flex">
              <div className="mr-4 flex flex-col items-center">
                <div className="bg-guideon-light text-guideon-purple rounded-full w-6 h-6 flex items-center justify-center text-xs font-medium">
                  {index + 1}
                </div>
                {index < pathway.courses.length - 1 && (
                  <div className="w-0.5 h-full bg-gray-200 my-1" />
                )}
              </div>
              <div className="bg-guideon-light rounded-lg p-3 flex-1">
                <h4 className="font-medium text-gray-900">{course.title}</h4>
                <p className="text-sm text-gray-600 mt-1">{course.description}</p>
                <div className="flex mt-2 justify-between items-center">
                  <Badge variant="outline" className="text-xs border-none bg-white/60 text-gray-600">
                    {course.duration}
                  </Badge>
                  <Badge variant="outline" className="text-xs border-none bg-white/60 text-gray-600">
                    {course.level}
                  </Badge>
                </div>
              </div>
            </div>
          ))}
          <div className="flex justify-end pt-2">
            <Button className="bg-guideon-purple hover:bg-guideon-purple/90 text-white">Start Pathway</Button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SkillPathwayCard;