import React, { useState, useEffect, useRef } from "react";
import axios from "axios";
import Message from "./Message";
import { Course } from "../services/courseService";

interface ChatMessage {
  id: number;
  text: string;
  type: "user" | "guideon";
  courses?: Course[];
}

const Dashboard: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages]);

  useEffect(() => {
    if (textareaRef.current) {
      const textarea = textareaRef.current;
      textarea.style.height = "auto";
      textarea.style.height = `${Math.min(textarea.scrollHeight, 240)}px`;
      textarea.style.overflowY = textarea.scrollHeight > 240 ? "auto" : "hidden";
    }
  }, [inputValue]);

  const handleSendMessage = async () => {
    if (inputValue.trim() === "") return;

    const userMessage: ChatMessage = { 
      id: messages.length + 1, 
      text: inputValue, 
      type: "user" 
    };
    setMessages((prevMessages) => [...prevMessages, userMessage]);
    setInputValue("");
    setLoading(true);

    try {
      const response = await axios.post("http://localhost:8000/api/chat/", { 
        prompt: inputValue 
      });

      console.log('API Response:', response.data);

      const courses = response.data.courses || [];
      console.log('Courses from API:', courses);

      const chatbotMessage: ChatMessage = {
        id: messages.length + 2,
        text: response.data.response || response.data.message,
        type: "guideon",
        courses: courses.length > 0 ? courses : undefined
      };

      console.log('Chatbot Message:', chatbotMessage);
      console.log('Courses in message:', chatbotMessage.courses);

      setMessages((prevMessages) => [...prevMessages, chatbotMessage]);
    } catch (error) {
      console.error('Error:', error);
      setMessages((prevMessages) => [...prevMessages, { 
        id: messages.length + 2, 
        text: "Error processing your request.", 
        type: "guideon" 
      }]);
    }
    setLoading(false);
  };

  return (
    <div className="flex flex-col h-screen w-screen pl-[220px] py-8">
      <div className="flex-1 overflow-y-auto p-4 px-36">
        {messages.map((message) => {
          console.log('Rendering message:', message);
          return (
            <Message
              key={message.id}
              text={message.text}
              type={message.type}
              courses={message.courses}
            />
          );
        })}
        <div ref={messagesEndRef} />
      </div>

      <div className="p-4 bg-surface-a10 rounded-lg mx-36 text-light-a0">
        <div className="flex flex-col">
          <textarea
            ref={textareaRef}
            placeholder="Ask me anything..."
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyPress={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSendMessage();
              }
            }}
            className="w-full px-4 py-2 bg-sur rounded-md outline-none resize-none"
            rows={1}
            style={{ maxHeight: "240px" }}
          />
          <button
            onClick={handleSendMessage}
            disabled={loading}
            className="mt-2 px-6 h-12 bg-primary-a0 text-white rounded-md hover:bg-primary-a10 focus:outline-none focus:ring-2 focus:ring-indigo-200 self-end"
          >
            {loading ? "Thinking..." : "Send"}
          </button>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
