import React, { useState, useEffect, useRef } from "react";
import axios from "axios";

interface Message {
  id: number;
  text: string;
  isUser: boolean;
}

interface Course {
  title: string;
  provider: string;
  rating: string;
  url: string;
}

const Dashboard: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([]);
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

    const userMessage: Message = { id: messages.length + 1, text: inputValue, isUser: true };
    setMessages((prevMessages) => [...prevMessages, userMessage]);
    setInputValue("");
    setLoading(true);

    try {
      const response = await axios.post("http://localhost:8000/api/search/", { query: inputValue });
      const courses: Course[] = response.data.courses;

      const chatbotMessage: Message = {
        id: messages.length + 2,
        text: courses.length
          ? courses.map((c, i) => `${i + 1}. 🎓 ${c.title}\n   🏫 ${c.provider}\n   ⭐ ${c.rating}\n   🔗 ${c.url}\n`).join("\n")
          : "No courses found.",
        isUser: false,
      };
      setMessages((prevMessages) => [...prevMessages, chatbotMessage]);
    } catch (error) {
      setMessages((prevMessages) => [...prevMessages, { id: messages.length + 2, text: "Error fetching courses.", isUser: false }]);
    }
    setLoading(false);
  };

  return (
    <div className="flex flex-col h-screen w-screen pl-[220px] py-8">
      <div className="flex-1 overflow-y-auto p-4 px-36">
        {messages.map((message) => (
          <div key={message.id} className={`flex ${message.isUser ? "justify-end" : "justify-start"} mb-4`}>
            <div className={`break-words my-4 ${message.isUser ? "bg-surface-tonal-a30 text-light-a0 p-3 rounded-lg" : "text-light-a0"}`} style={{ whiteSpace: "pre-wrap" }}>
              {message.text}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      <div className="p-4 bg-surface-a10 rounded-lg mx-36 text-light-a0">
        <div className="flex flex-col">
          <textarea
            ref={textareaRef}
            placeholder="Enter a course topic..."
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
            {loading ? "Searching..." : "Search"}
          </button>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
