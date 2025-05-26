import { Course } from '../services/courseService';

// Message type for chat interactions
export interface Message {
  id: number;
  text: string;
  isUser: boolean;
  courses?: Course[];
  goto_career_role?: string;
  show_goto_career_button?: boolean;
}

// API response from Ollama
export interface OllamaResponse {
  model: string;
  created_at: string;
  response: string;
  done: boolean;
  total_duration?: number;
  load_duration?: number;
  prompt_eval_count?: number;
  prompt_eval_duration?: number;
  eval_count?: number;
  eval_duration?: number;
} 

export interface ChatResponse {
  response: string;
  chat_id: string;
  courses?: Course[];
}