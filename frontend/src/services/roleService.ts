import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export interface RoleSkill {
  skill: string;
  level: string;
}

export interface RoleKnowledgeResponse {
  role: string;
  skills: RoleSkill[];
  courses?: any[];
}

export interface RoleInfoResponse {
  role_info: string[];
  followup: string;
}

export const getRoleInfo = async (role: string): Promise<RoleInfoResponse> => {
  const response = await axios.post(
    `${API_URL}/api/role-info/`,
    { role }
  );
  return response.data;
}

export const getRoleKnowledge = async (role: string, wantCourses = false, token?: string): Promise<RoleKnowledgeResponse> => {
  const response = await axios.post(
    `${API_URL}/api/role-knowledge/`,
    { role, want_courses: wantCourses },
    token ? { headers: { Authorization: `Bearer ${token}` } } : undefined
  );
  return response.data;
};
