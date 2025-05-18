import api from '../api';

export interface UserPreferences {
  id?: number;
  course_level: 'beginner' | 'intermediate' | 'advanced' | 'all';
  programming_languages: string[];
  development_areas: string[];
  created_at?: string;
  updated_at?: string;
}

export const preferenceService = {
  async getPreferences(): Promise<UserPreferences> {
    const { data } = await api.get<UserPreferences>('/api/preferences/');
    return data;
  },

  async updatePreferences(preferences: Partial<UserPreferences>): Promise<UserPreferences> {
    const { data } = await api.post<UserPreferences>('/api/preferences/', preferences);
    return data;
  },

  async checkFirstLogin(): Promise<{ has_preferences: boolean }> {
    const { data } = await api.get<{ has_preferences: boolean }>('/api/preferences/check/');
    return data;
  }
}; 