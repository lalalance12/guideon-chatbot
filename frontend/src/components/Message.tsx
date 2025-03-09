// components/Message.tsx
import React from "react";

interface MessageProps {
  text: string;
  type: "user" | "guideon";
}

const Message: React.FC<MessageProps> = ({ text, type }) => {
  const messageStyles = {
    user: "bg-blue-500 text-white self-end",
    guideon: "bg-green-500 text-white self-start",
  };

  return (
    <div className={`p-3 rounded-lg mb-2 max-w-xs ${messageStyles[type]}`}>
      {text}
    </div>
  );
};

export default Message;
