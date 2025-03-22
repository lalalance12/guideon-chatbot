import axios from "axios";
import { useState } from "react";
import { OllamaResponse } from "../types/models";

const OLLAMA_API_URL = "http://localhost:11434/api/generate";

/**
 * Sends a query to the locally running Ollama model
 * @param userPrompt - The user's input prompt
 * @returns The response from the Ollama API
 */
export const queryOllama = async (userPrompt: string): Promise<string> => {
  try {
    const headers = { "Content-Type": "application/json" };
    const data = {
      model: "llama3.2", // Using the specified model
      prompt: buildPrompt(userPrompt),
      stream: false, // Not streaming responses
    };

    const response = await axios.post<OllamaResponse>(OLLAMA_API_URL, data, { headers });
    return response.data.response;
  } catch (error) {
    console.error("Error querying Ollama:", error);
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
      const errorMessage = "Failed to get a response from Ollama.";
      setError(errorMessage);
      return errorMessage;
    } finally {
      setIsLoading(false);
    }
  };

  return { sendQuery, isLoading, error };
};

/**
 * Builds a prompt with context for the Ollama model
 * @param userPrompt - The user's input prompt
 * @returns A formatted prompt with system context
 */
const buildPrompt = (userPrompt: string): string => {
  return `You are Guideon, a helpful AI assistant focused on education and learning.
You provide guidance on courses, learning paths, and educational resources.
You're friendly, supportive, and knowledgeable about various academic subjects.
You help students, scholars, and lifelong learners achieve their educational goals.

${userPrompt}`;
}; 