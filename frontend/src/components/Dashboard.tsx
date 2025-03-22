import React, { useState, useEffect, useRef } from "react";

interface Message {
  id: number;
  text: string;
  isUser: boolean;
}

const Dashboard: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

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
      const lineHeight = 24; // Approximate line height in pixels
      const maxLines = 10;
      const maxHeight = lineHeight * maxLines;

      // Reset height to auto to calculate the new height
      textarea.style.height = "auto";
      const newHeight = Math.min(textarea.scrollHeight, maxHeight);

      // Set the new height
      textarea.style.height = `${newHeight}px`;

      // Enable or disable scrollbar based on content height
      if (textarea.scrollHeight > maxHeight) {
        textarea.style.overflowY = "auto"; // Show scrollbar
      } else {
        textarea.style.overflowY = "hidden"; // Hide scrollbar
      }
    }
  }, [inputValue]);

  const handleSendMessage = () => {
    if (inputValue.trim() === "") return;

    // Add user message
    const newMessage: Message = {
      id: messages.length + 1,
      text: inputValue,
      isUser: true,
    };
    setMessages((prevMessages) => [...prevMessages, newMessage]);
    setInputValue("");

    // Simulate chatbot response
    setTimeout(() => {
      const chatbotMessage: Message = {
        id: messages.length + 2,
        text: `You said: ${inputValue}`,
        isUser: false,
      };
      setMessages((prevMessages) => [...prevMessages, chatbotMessage]);
    }, 1000);
  };

  return (
    <div className="flex flex-col h-screen w-screen pl-[220px] py-8">
      {/* Chat Messages Container */}
      <div className="flex-1 overflow-y-auto p-4 px-36">
        {messages.map((message) => (
          <div
            key={message.id}
            className={`flex ${
              message.isUser ? "justify-end" : "justify-start"
            } mb-4`}
          >
            <div
              className={`break-words my-4 ${
                message.isUser
                  ? "bg-surface-tonal-a30 text-light-a0 max-w-full p-3 rounded-lg ml-4"
                  : " text-light-a0 w-full mr-4"
              }`}
              style={{ whiteSpace: "pre-wrap" }} // Preserve line breaks and wrap text
            >
              {message.text}
            </div>
          </div>
        ))}
        {/* Empty div to scroll into view */}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="p-4 bg-surface-a10 rounded-lg mx-36 text-light-a0">
        <div className="flex flex-col">
          {" "}
          {/* Stack textarea and button vertically */}
          <div className="flex-1">
            {" "}
            {/* Wrap textarea in a flex-1 container */}
            <textarea
              ref={textareaRef}
              placeholder="Enter chat message..."
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyPress={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault(); // Prevent new line on Enter
                  handleSendMessage();
                }
              }}
              className="w-full px-4 py-2 bg-sur rounded-md outline-none resize-none" // Remove flex-1 from textarea
              rows={1} // Start with a single row
              style={{ maxHeight: "240px" }} // 10 lines * 24px line height
            />
          </div>
          <button
            onClick={handleSendMessage}
            className="mt-2 px-6 h-12 bg-primary-a0 text-white rounded-md hover:bg-primary-a10 focus:outline-none focus:ring-2 focus:ring-indigo-200 self-end" // Align button to the bottom
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
