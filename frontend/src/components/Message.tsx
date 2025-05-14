// components/Message.tsx
import React from "react";
import { Bot, User } from "lucide-react";

interface MessageProps {
  text: string;
  type: "user" | "guideon";
  showAvatar?: boolean;
}

const Message: React.FC<MessageProps> = ({ text, type, showAvatar = true }) => {
  const isUser = type === "user";

  // Function to convert newlines to <br> and render HTML content
  const formatMessage = (message: string) => {
    const lines = message.split('\n');
    return lines.map((line, index) => (
      <React.Fragment key={index}>
        <span dangerouslySetInnerHTML={{ __html: line }} />
        {index < lines.length - 1 && <br />}
      </React.Fragment>
    ));
  };

  return (
    <div
      className={`flex items-start gap-3 ${
        isUser ? "flex-row-reverse" : "flex-row"
      }`}
    >
      {showAvatar && (
        <div
          className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center
          ${isUser ? "bg-indigo-600" : "bg-indigo-100"}`}
        >
          {isUser ? (
            <User size={14} className="text-white" />
          ) : (
            <Bot size={14} className="text-indigo-600" />
          )}
        </div>
      )}
      <div
        className={`${
          isUser
            ? "chat-bubble chat-bubble-user"
            : "chat-bubble chat-bubble-bot"
        }`}
      >
        {formatMessage(text)}
      </div>
    </div>
  );
};

export default Message;
