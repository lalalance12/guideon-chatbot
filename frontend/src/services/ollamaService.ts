import axios from "axios";
import { useState, useEffect } from "react";
import api from "../api";

const STORAGE_KEY = "guideon_chat_history";
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

/**
 * Check if the backend API is available
 */
export const checkApiConnection = async (): Promise<boolean> => {
  try {
    console.log(`Checking API connection to: ${API_URL}`);
    // Try a simple request to verify the backend is reachable
    await axios.get(`${API_URL}/api/chats/`);
    console.log('API connection successful');
    return true;
  } catch (error) {
    console.error('API connection failed:', error);
    return false;
  }
};

/**
 * Sends a query to the backend which communicates with Ollama
 * @param userPrompt - The user's input prompt
 * @param chatId - Optional chat ID for continuing a conversation
 * @returns The response from the backend API including chat_id
 */
export const queryOllama = async (userPrompt: string, chatId?: string): Promise<{response: string, chat_id: string, courses?: any[]}> => {
  try {
    console.log("Frontend: Sending request to backend API");
    const requestData = chatId 
      ? { prompt: userPrompt, chat_id: chatId }
      : { prompt: userPrompt };
      
    console.log("Request data:", requestData);
    
    const response = await api.post('/api/chat/', requestData);
    
    console.log("Frontend: Received response from backend");
    console.log("Response data:", response.data);
    
    // Extract the response and courses if they exist
    const responseText = response.data.response;
    const courses = response.data.courses;
    
    return {
      response: responseText,
      chat_id: response.data.chat_id,
      courses: courses
    };
  } catch (error) {
    console.error("Error querying backend:", error);
    if (axios.isAxiosError(error)) {
      console.error("Status:", error.response?.status);
      console.error("Response data:", error.response?.data);
      console.error("Request config:", error.config);
    }
    // Return a default error response
    return {
      response: "I'm having trouble connecting to my knowledge base right now. Please try again later.",
      chat_id: "", // Empty string to indicate error
      courses: []
    };
  }
};

/**
 * Custom hook for using Ollama API with loading state and chat history
 */
export const useOllamaQuery = () => {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentChatId, setCurrentChatId] = useState<string | null>(null);
  
  // Initialize chat ID from local storage if available
  useEffect(() => {
    try {
      const savedChat = localStorage.getItem(STORAGE_KEY);
      if (savedChat) {
        try {
          const parsedData = JSON.parse(savedChat);
          if (parsedData && parsedData.chatId && typeof parsedData.chatId === 'string') {
            console.log(`Restored chat ID ${parsedData.chatId} from local storage`);
            setCurrentChatId(parsedData.chatId);
          } else {
            console.warn("No valid chatId found in local storage");
          }
        } catch (err) {
          console.error("Error parsing saved chat:", err);
        }
      }
    } catch (error) {
      console.error("Error accessing localStorage:", error);
    }
  }, []);

  const sendQuery = async (prompt: string): Promise<any> => {
    setIsLoading(true);
    setError(null);
    
    try {
      console.log(`Sending query with prompt: "${prompt.substring(0, 30)}..." and chatId: ${currentChatId || 'none'}`);
      const result = await queryOllama(prompt, currentChatId || undefined);
      
      // Store the chat ID for future requests
      if (result.chat_id) {
        console.log(`Received and saved chat ID: ${result.chat_id}`);
        setCurrentChatId(result.chat_id);
        
        // Save to localStorage for persistence
        try {
          localStorage.setItem(STORAGE_KEY, JSON.stringify({chatId: result.chat_id}));
        } catch (e) {
          console.warn("Could not save chat ID to localStorage:", e);
        }
      }
      
      // Return the full result including courses if available
      if (result.courses && result.courses.length > 0) {
        return {
          response: result.response,
          courses: result.courses
        };
      }
      
      // Otherwise just return the response string
      return result.response;
        
    } catch (err) {
      console.error("Error in sendQuery:", err);
      const errorMessage = "Failed to get a response.";
      setError(errorMessage);
      return errorMessage;
    } finally {
      setIsLoading(false);
    }
  };

  return { sendQuery, isLoading, error, currentChatId };
};