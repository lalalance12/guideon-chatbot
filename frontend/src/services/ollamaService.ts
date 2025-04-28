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
export const queryOllama = async (userPrompt: string, chatId?: number): Promise<{response: string, chat_id: number}> => {
  try {
    console.log("Frontend: Sending request to backend API");
    const requestData = chatId 
      ? { prompt: userPrompt, chat_id: chatId }
      : { prompt: userPrompt };
      
    console.log("Request data:", requestData);
    
    const response = await api.post('/api/chat/', requestData);
    
    console.log("Frontend: Received response from backend");
    console.log("Response data:", response.data);
    
    return {
      response: response.data.response,
      chat_id: response.data.chat_id
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
      chat_id: -1 // Invalid chat ID to indicate error
    };
  }
};

/**
 * Custom hook for using Ollama API with loading state and chat history
 */
export const useOllamaQuery = () => {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentChatId, setCurrentChatId] = useState<number | null>(null);
  
  // Initialize chat ID from local storage if available
  useEffect(() => {
    try {
      const savedChat = localStorage.getItem(STORAGE_KEY);
      if (savedChat) {
        try {
          const parsedData = JSON.parse(savedChat);
          if (parsedData && parsedData.chatId && typeof parsedData.chatId === 'number' && parsedData.chatId > 0) {
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

  const sendQuery = async (prompt: string): Promise<string> => {
    setIsLoading(true);
    setError(null);
    
    try {
      console.log(`Sending query with prompt: "${prompt.substring(0, 30)}..." and chatId: ${currentChatId || 'none'}`);
      const result = await queryOllama(prompt, currentChatId || undefined);
      
      // Store the chat ID for future requests
      if (result.chat_id > 0) {
        console.log(`Received and saved chat ID: ${result.chat_id}`);
        setCurrentChatId(result.chat_id);
      }
      
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