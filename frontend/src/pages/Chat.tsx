import React, { useState, useEffect, useRef } from "react";
import { Send, Sparkles, BookOpen, RotateCcw, AlertTriangle } from "lucide-react";
import { Message as MessageType } from "../types/models";
import { useOllamaQuery, checkApiConnection } from "../services/ollamaService";
import { searchCourses, Course } from "../services/courseService";
import Message from "../components/Message";
import CourseCard from "../components/CourseCard";
import GoToCareerPathwaysButton from '../components/GoToCareerPathwaysButton';
import { ACCESS_TOKEN } from "../constants";

const STORAGE_KEY = "guideon_chat_history";

interface MessageTypeWithCareer extends MessageType {
  goto_career_role?: string;
}

const Chat: React.FC = () => {
  const [messages, setMessages] = useState<MessageType[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [isSearchingCourses, setIsSearchingCourses] = useState(false);
  const [apiConnected, setApiConnected] = useState<boolean | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const { sendQuery, isLoading, error, currentChatId } = useOllamaQuery();

  // Check API connection on component mount
  useEffect(() => {
    const verifyConnection = async () => {
      try {
        const isConnected = await checkApiConnection();
        setApiConnected(isConnected);
        console.log(
          `API connection status: ${isConnected ? "Connected" : "Disconnected"}`
        );

        if (!isConnected) {
          setMessages([
            {
              id: Date.now(),
              text: "Unable to connect to the backend server. Please make sure the server is running and try again.",
              isUser: false,
            },
          ]);
        }
      } catch (error) {
        console.error("Error checking API connection:", error);
        setApiConnected(false);
      }
    };

    verifyConnection();
  }, []);

  // Load messages from localStorage
  useEffect(() => {
    try {
      const savedChat = localStorage.getItem(STORAGE_KEY);
      if (savedChat) {
        try {
          const parsedData = JSON.parse(savedChat);
          if (
            parsedData &&
            parsedData.messages &&
            Array.isArray(parsedData.messages)
          ) {
            console.log("Loaded saved messages:", parsedData.messages.length);
            setMessages(parsedData.messages);
          } else {
            console.warn("Invalid saved chat format, using welcome message");
            addWelcomeMessage();
          }
        } catch (e) {
          console.error("Error parsing saved chat:", e);
          addWelcomeMessage();
        }
      } else {
        console.log("No saved chat found, showing welcome message");
        addWelcomeMessage();
      }
    } catch (error) {
      console.error("Error accessing localStorage:", error);
      addWelcomeMessage();
    }
  }, [apiConnected]); // Only load from localStorage after API connection check

  // Save messages to localStorage when they change
  useEffect(() => {
    if (messages.length > 0) {
      try {
        localStorage.setItem(
          STORAGE_KEY,
          JSON.stringify({
            messages,
            chatId: currentChatId,
          })
        );
      } catch (error) {
        console.error("Error saving to localStorage:", error);
      }
    }
  }, [messages, currentChatId]);

  const addWelcomeMessage = () => {
    if (apiConnected === false) return; // Don't show welcome if API is disconnected

    setMessages([
      {
      id: 1,
      text: `
  **Hi there! I'm Guideon, your AI assistant specializing in the Philippine Skills Framework for Analytics & AI (PSF-AAI).**
  I'm here to help learners like you understand different roles, skills, and career pathways within analytics and AI.
  ##### What I Can Do
  - **PSF-AAI Knowledge Queries:** I can answer questions about the framework, roles, skills, and career tracks.
  - **Career Role Exploration:** If you're unsure about a specific role, I can introduce available roles with descriptions to help you decide which one aligns with your interests and goals.
  - **Role-Specific Skills:** When you mention a particular role, I'll display its functional and enabling skills requirements to ensure you understand what's needed for that career path.
  - **Course Recommendations:** If you're looking to upskill or reskill, I can provide recommendations based on the PSF-AAI framework.
  
  If you're unsure where to start, just ask me about the roles available in the PSF-AAI framework, and I'll guide you through the options.
      `,
      isUser: false,
      },
    ]);
  };

  // Scroll to the bottom of the chat when new messages are added
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages]);

  // Adjust textarea height based on content
  useEffect(() => {
    if (textareaRef.current) {
      const textarea = textareaRef.current;
      const lineHeight = 24;
      const maxLines = 5;
      const maxHeight = lineHeight * maxLines;

      textarea.style.height = "auto";
      const newHeight = Math.min(textarea.scrollHeight, maxHeight);
      textarea.style.height = `${newHeight}px`;

      if (textarea.scrollHeight > maxHeight) {
        textarea.style.overflowY = "auto";
      } else {
        textarea.style.overflowY = "hidden";
      }
    }
  }, [inputValue]);

  const handleCourseSearch = async (query: string) => {
    setIsSearchingCourses(true);
    try {
      const token = localStorage.getItem(ACCESS_TOKEN);
      if (!token) {
        throw new Error("Authentication required");
      }

      const courses = await searchCourses(query, token);
      
      if (courses.length > 0) {
        const botMessage: MessageType = {
          id: Date.now() + 1,
          text: `Here are some courses I found for "${query}":`,
          isUser: false,
          courses: courses
        };
        setMessages((prevMessages) => [...prevMessages, botMessage]);
      } else {
        const botMessage: MessageType = {
          id: Date.now() + 1,
          text: `I couldn't find any courses for "${query}". Try a different search term.`,
          isUser: false,
        };
        setMessages((prevMessages) => [...prevMessages, botMessage]);
      }
    } catch (error) {
      console.error("Error searching courses:", error);
      const errorMessage: MessageType = {
        id: Date.now() + 1,
        text: "Sorry, I encountered an error while searching for courses. Please try again later.",
        isUser: false,
      };
      setMessages((prevMessages) => [...prevMessages, errorMessage]);
    } finally {
      setIsSearchingCourses(false);
    }
  };

  const handleSendMessage = async () => {
    if (inputValue.trim() === "" || isLoading || isSearchingCourses)
      return;

    // Add user message
    const userMessage: MessageType = {
      id: Date.now(),
      text: inputValue,
      isUser: true,
    };
    setMessages((prevMessages) => [...prevMessages, userMessage]);

    const userPrompt = inputValue;
    setInputValue("");

    try {
      // This is where the response from the backend is processed
      const botResponse = await sendQuery(userPrompt);
      const responseText = botResponse.response || "I couldn't generate a response.";
      const courses = botResponse.courses || [];
      
      // Add bot message with ALL the properties from the response
      const botMessage: MessageType = {
        id: Date.now() + 1,
        text: responseText,
        isUser: false,
        courses: courses,
        // Add these special properties from the response
        goto_career_role: botResponse.goto_career_role,
        show_goto_career_button: botResponse.show_goto_career_button
      };
      
      setMessages((prevMessages) => [...prevMessages, botMessage]);
    } catch (error) {
      console.error("Error getting response:", error);

      // Add error message
      const errorMessage: MessageType = {
        id: Date.now() + 1,
        text: "Sorry, I encountered an error while processing your request. Please try again later.",
        isUser: false,
      };

      setMessages((prevMessages) => [...prevMessages, errorMessage]);
    }
  };

  // Clear current conversation and start a new one
  const startNewChat = () => {
    if (window.confirm("Are you sure you want to start a new conversation?")) {
      // First remove from localStorage to ensure clean slate
      localStorage.removeItem(STORAGE_KEY);
      
      // Clear state variables
      setMessages([]);
      
      // This is more reliable than page refresh
      // It ensures the hook resets without triggering localStorage saves
      window.location.href = window.location.pathname;
    }
  };
  // Group messages by sender to show avatars only for the first message in a group
  // Render chat messages and handle special backend signals (clarification, goto_career_role)
  const renderMessages = () => {
    return (messages as MessageTypeWithCareer[]).map((msg, idx) => {
      // Check if this message is the first in a group from the same sender
      const isFirstInGroup =
        idx === 0 || messages[idx - 1].isUser !== msg.isUser;

      // If the message has a special backend signal for goto_career_role AND show_goto_career_button, show the button
      if (msg.goto_career_role && msg.show_goto_career_button) {
        return (
          <div key={`goto-career-btn-${idx}`} className="my-4 flex justify-center">
            <GoToCareerPathwaysButton role={msg.goto_career_role} />
          </div>
        );
      }

      return (
        <div key={msg.id} className="mb-4">
          <Message
            text={msg.text}
            type={msg.isUser ? "user" : "guideon"}
            showAvatar={isFirstInGroup}
            courses={msg.courses}
          />
        </div>
      );
    });
  };

  return (
    <div className="flex flex-col h-screen bg-gradient-main">
      {/* Header */}
      <header className="px-6 py-4 bg-white border-b border-gray-200">
        <div className="max-w-4xl mx-auto">
          <div className="flex items-center justify-between">
            <div className="flex items-center">
              <div className="bg-indigo-100 p-2 rounded-lg">
                <Sparkles className="text-indigo-600" size={20} />
              </div>
              <div className="ml-3">
                <h1 className="text-xl font-bold text-gray-800">
                  Chat with Guideon
                </h1>
                <p className="text-sm text-gray-500">
                  Ask me anything about learning paths and courses
                  {currentChatId && (
                    <span className="ml-2 text-xs text-indigo-600 font-medium">
                      Chat #{currentChatId}
                    </span>
                  )}
                  {apiConnected === false && (
                    <span className="ml-2 text-xs text-red-600 flex items-center font-medium">
                      <AlertTriangle size={12} className="mr-1" />
                      Backend connection error
                    </span>
                  )}
                </p>
              </div>
            </div>
            <button
              onClick={startNewChat}
              className="btn-outline flex items-center gap-1 text-sm font-medium hover:bg-gray-100 px-3 py-2 rounded-md transition-all"
              title="Start a new conversation"
              disabled={apiConnected === false}
            >
              <RotateCcw size={14} />
              <span>New Chat</span>
            </button>
          </div>
        </div>
      </header>

      {/* Chat Messages Container */}
      <div className="flex-1 overflow-y-auto py-6 px-4 bg-gray-50">
        <div className="max-w-3xl mx-auto space-y-6">
          {messages.length > 0 ? (
            renderMessages()
          ) : (
            <div className="text-center text-gray-500 py-8 font-medium">Loading...</div>
          )}

          {(isLoading || isSearchingCourses) && (
            <div className="flex items-start gap-3">
              <div className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center bg-indigo-100">
                {isSearchingCourses ? (
                  <BookOpen size={14} className="text-indigo-600" />
                ) : (
                  <Sparkles size={14} className="text-indigo-600" />
                )}
              </div>
              <div className="chat-bubble chat-bubble-bot shadow-sm">
                <div className="flex items-center space-x-2">
                  <div className="w-2 h-2 bg-indigo-600 rounded-full animate-pulse"></div>
                  <div className="w-2 h-2 bg-indigo-600 rounded-full animate-pulse delay-75"></div>
                  <div className="w-2 h-2 bg-indigo-600 rounded-full animate-pulse delay-150"></div>
                  <span className="text-gray-500 text-sm font-medium">
                    {isSearchingCourses
                      ? "Searching for courses..."
                      : "Guideon is thinking..."}
                  </span>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input Area */}
      <div className="w-full px-4 md:px-8 lg:px-16 xl:px-32 mx-auto py-4 bg-white border-t border-gray-200">
        <div className="max-w-3xl mx-auto">
          <div className="flex items-end space-x-2 input-area p-3 shadow-sm rounded-lg border border-gray-200 focus-within:border-indigo-300 focus-within:ring-1 focus-within:ring-indigo-200 transition-all">
            <textarea
              ref={textareaRef}
              placeholder={
                  apiConnected === false
                    ? "Cannot connect to server"
                    : "Ask Guideon about learning paths, courses, or any educational topic..."
                }
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyPress={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSendMessage();
                }
              }}
              className="flex-1 px-3 py-2 bg-transparent outline-none resize-none min-h-[40px] max-h-[120px] focus:ring-0 text-gray-700 font-normal placeholder:text-gray-400"
              disabled={isLoading || isSearchingCourses || apiConnected === false}
            />
            <button
              onClick={handleSendMessage}
              disabled={
                  isLoading || isSearchingCourses || inputValue.trim() === "" || apiConnected === false
                }
              className={`btn flex items-center gap-1 py-2 px-4 rounded-md transition-all font-medium ${
                isLoading || isSearchingCourses || inputValue.trim() === "" || apiConnected === false
                  ? "bg-gray-200 text-gray-400 cursor-not-allowed"
                  : "bg-indigo-600 text-white hover:bg-indigo-700"
              }`}
            >
              <Send size={16} />
              <span>Send</span>
            </button>
          </div>
          <p className="text-xs text-gray-500 mt-2 text-center">
              {apiConnected === false ? (
                <span className="text-red-500 font-medium">
                  Backend server not connected. Please start the server and
                  refresh the page.
                </span>
              ) : (
                <>
                <span className="font-medium">Powered by Ollama's llama3.2</span> model running locally on your
                  machine
                  {currentChatId && (
                    <span className="ml-1">
                      • Conversation history is being saved
                    </span>
                  )}
                </>
              )}
          </p>
        </div>
      </div>
    </div>
  );
};

export default Chat;
