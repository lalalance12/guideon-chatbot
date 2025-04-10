import axios from "axios";
import { useState } from "react";
import api from "../api";

/**
 * Sends a query to the backend which communicates with Ollama
 * @param userPrompt - The user's input prompt
 * @returns The response from the backend API
 */
export const queryOllama = async (userPrompt: string): Promise<string> => {
  try {
    console.log("Frontend: Sending request to backend API");
    console.log("Request data:", { prompt: userPrompt });
    
    const response = await api.post('/api/chat/', {
      prompt: userPrompt,
    });
    
    console.log("Frontend: Received response from backend");
    console.log("Response data:", response.data);
    
    return response.data.response;
  } catch (error) {
    console.error("Error querying backend:", error);
    if (axios.isAxiosError(error)) {
      console.error("Status:", error.response?.status);
      console.error("Response data:", error.response?.data);
      console.error("Request config:", error.config);
    }
    return "I'm having trouble connecting to my knowledge base right now. Please try again later.";
  }
};

/**
 * Custom hook for using Ollama API with loading state
 */
export const useOllamaQuery = () => {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sendQuery = async (prompt: string): Promise<string> => {
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await queryOllama(prompt);
      return response;
    } catch (err) {
      const errorMessage = "Failed to get a response.";
      setError(errorMessage);
      return errorMessage;
    } finally {
      setIsLoading(false);
    }
  };

  return { sendQuery, isLoading, error };
}; 