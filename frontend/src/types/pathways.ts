export type PathwayType = 'skill' | 'career';

export interface Skill {
  id: string;
  name: string;
  level: string;
  description: string;
}

export interface Level {
  title: string;
  level: string;
  description?: string;
  requiredSkills: Skill[];
}

export interface CareerPathway {
  id: string;
  title: string;
  description: string;
  field: string;
  levels: Level[];
}

export interface Course {
  id: string;
  title: string;
  description: string;
  duration: string;
  level: string;
}

export interface SkillPathway {
  id: string;
  title: string;
  description: string;
  courses: Course[];
}