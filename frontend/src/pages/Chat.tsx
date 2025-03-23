import React, { useState, useEffect, useRef } from "react";
import { Send, Sparkles } from "lucide-react";
import { Message as MessageType } from "../types/models";
import { useOllamaQuery } from "../services/ollamaService";
import Message from "../components/Message";

const Chat: React.FC = () => {
  const [messages, setMessages] = useState<MessageType[]>([]);
  const [inputValue, setInputValue] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const { sendQuery, isLoading } = useOllamaQuery();

  useEffect(() => {
    // Add welcome message when the chat loads
    setMessages([
      {
        id: 1,
        text: "Hi there! I'm Guideon, your learning assistant. How can I help you today?",
        isUser: false,
      },
    ]);
  }, []);

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

  const handleSendMessage = async () => {
    if (inputValue.trim() === "" || isLoading) return;

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
      // Get response from Ollama using our hook
      const botResponse = await sendQuery(userPrompt);

      // Add bot message
      const botMessage: MessageType = {
        id: Date.now() + 1,
        text: botResponse,
        isUser: false,
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
              </p>
            </div>
          </div>
        </div>
      </header>

      {/* Chat Messages Container */}
      <div className="flex-1 overflow-y-auto py-6 px-4">
        <div className="max-w-4xl mx-auto space-y-6">
          {renderMessages()}

          {isLoading && (
            <div className="flex items-start gap-3">
              <div className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center bg-indigo-100">
                <Sparkles size={14} className="text-indigo-600" />
              </div>
              <div className="chat-bubble chat-bubble-bot">
                <div className="flex items-center space-x-2">
                  <div className="w-2 h-2 bg-indigo-600 rounded-full animate-pulse"></div>
                  <div className="w-2 h-2 bg-indigo-600 rounded-full animate-pulse delay-75"></div>
                  <div className="w-2 h-2 bg-indigo-600 rounded-full animate-pulse delay-150"></div>
                  <span className="text-gray-500 text-sm">
                    Guideon is thinking...
                  </span>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input Area */}
      <div className="p-4 bg-white border-t border-gray-200">
        <div className="max-w-4xl mx-auto">
          <div className="flex items-end space-x-2 input-area p-3 shadow-sm">
            <textarea
              ref={textareaRef}
              placeholder="Ask Guideon about learning paths, courses, or any educational topic..."
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyPress={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSendMessage();
                }
              }}
              className="flex-1 px-3 py-2 bg-transparent outline-none resize-none min-h-[40px] max-h-[120px] focus-ring"
              disabled={isLoading}
            />
            <button
              onClick={handleSendMessage}
              disabled={isLoading || inputValue.trim() === ""}
              className={`btn flex items-center gap-1 ${
                isLoading || inputValue.trim() === ""
                  ? "bg-gray-300 text-gray-500 cursor-not-allowed"
                  : "btn-primary"
              }`}
            >
              <Send size={16} />
              <span>Send</span>
            </button>
          </div>
          <p className="text-xs text-gray-500 mt-2 text-center">
            Powered by Ollama's llama3.2 model running locally on your machine
          </p>
        </div>
      </div>
    </div>
  );
};

export default Chat;
