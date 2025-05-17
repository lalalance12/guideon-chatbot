import React, { useState, useEffect, useRef } from "react";
import { Send, Sparkles, BookOpen, RotateCcw, AlertTriangle } from "lucide-react";
import { Message as MessageType } from "../types/models";
import { useOllamaQuery, checkApiConnection } from "../services/ollamaService";
import { searchCourses, Course } from "../services/courseService";
import Message from "../components/Message";
import CourseCard from "../components/CourseCard";
import { ACCESS_TOKEN } from "../constants";

const STORAGE_KEY = "guideon_chat_history";

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
      text: "Hi there! I'm Guideon, your learning assistant. I can answer your questions about PSF-AAI, search for a course that aligns with functional skill from PSF-AAI, or generate a learning pathway for you. How can I assist you today?",
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
    if (inputValue.trim() === "" || isLoading || isSearchingCourses) return;

    // Add user message
    const userMessage: MessageType = {
      id: Date.now(),
      text: inputValue,
      isUser: true,
    };
    setMessages((prevMessages) => [...prevMessages, userMessage]);

    const userPrompt = inputValue;
    setInputValue("");

    // Check if the message is a course search request
    if (userPrompt.toLowerCase().includes("find courses") || 
        userPrompt.toLowerCase().includes("search courses") ||
        userPrompt.toLowerCase().includes("look for courses")) {
      await handleCourseSearch(userPrompt);
      return;
    }

    try {
      // Get response from Ollama using our hook
      const botResponse = await sendQuery(userPrompt);
      
      // Check if botResponse is an object with courses
      let responseText;
      let courses;
      
      if (typeof botResponse === 'object' && botResponse !== null) {
        responseText = botResponse.response || '';
        courses = botResponse.courses;
      } else {
        // If botResponse is a string
        responseText = botResponse;
      }

      // Add bot message
      const botMessage: MessageType = {
        id: Date.now() + 1,
        text: responseText,
        isUser: false,
        courses: courses
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
      localStorage.removeItem(STORAGE_KEY);
      setMessages([]);
      addWelcomeMessage();
      // Refresh page to reset hook state
      window.location.reload();
    }
  };

  // Group messages by sender to show avatars only for the first message in a group
  const renderMessages = () => {
    return messages.map((message, index) => {
      // Check if this message is the first in a group from the same sender
      const isFirstInGroup =
        index === 0 || messages[index - 1].isUser !== message.isUser;

      return (
        <div key={message.id} className="mb-4">
          <Message
            text={message.text}
            type={message.isUser ? "user" : "guideon"}
            showAvatar={isFirstInGroup}
            courses={message.courses}
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
