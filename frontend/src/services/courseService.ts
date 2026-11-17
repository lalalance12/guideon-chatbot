import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export interface Course {
  title: string;
  provider: string;
  rating: number;
  price: string;
  description: string;
  url: string;
}

export const searchCourses = async (query: string, token: string, chatId?: string | null): Promise<Course[]> => {
  try {
    const response = await axios.get(`${API_URL}/api/course-search/`, {
      params: { q: query, chat_id: chatId },
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    if (response.data.error) {
      throw new Error(response.data.error);
    }

    if (!response.data.courses || response.data.courses.length === 0) {
      throw new Error("No courses found. Try a different search term.");
    }

    return response.data.courses;
  } catch (error) {
    console.error('Error searching courses:', error);
    if (axios.isAxiosError(error)) {
      if (error.response?.status === 400) {
        throw new Error(error.response.data.error || "Invalid search query. Please try again.");
      } else if (error.response?.status === 500) {
        throw new Error("Server error. Please try again later.");
      }
    }
    throw error;
  }
}; 