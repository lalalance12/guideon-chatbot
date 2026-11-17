import api from '../api';

export interface UserPreferences {
  id?: number;
  course_level: 'beginner' | 'intermediate' | 'advanced' | 'all';
  programming_languages: string[];
  development_areas: string[];
  created_at?: string;
  updated_at?: string;
}

// Default preferences if none exist
export const defaultPreferences: UserPreferences = {
  course_level: 'all',
  programming_languages: [],
  development_areas: []
};

export const preferenceService = {
  async getPreferences(): Promise<UserPreferences> {
    try {
      const { data } = await api.get<UserPreferences>('/api/preferences/');
      return {
        ...defaultPreferences,
        ...data,
        // Ensure these are arrays even if they come back as null or undefined from the API
        programming_languages: Array.isArray(data.programming_languages) ? data.programming_languages : [],
        development_areas: Array.isArray(data.development_areas) ? data.development_areas : []
      };
    } catch (error) {
      console.error('Error fetching preferences:', error);
      return defaultPreferences;
    }
  },

  async updatePreferences(preferences: Partial<UserPreferences>): Promise<UserPreferences> {
    const { data } = await api.post<UserPreferences>('/api/preferences/', preferences);
    return data;
  },

  checkFirstLogin: async () => {
    try {
      const response = await api.get('/api/preferences/check/');
      return response.data;
    } catch (error) {
      console.error('Error checking first login status:', error);
      throw error;
    }
  }
};