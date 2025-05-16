// components/Message.tsx
import { cn } from "@/lib/utils";
import { Bot, User } from "lucide-react";
import React from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface MessageProps {
  text: string;
  type: "user" | "guideon";
  showAvatar?: boolean;
}

const Message: React.FC<MessageProps> = ({ text, type, showAvatar = true }) => {
  const isUser = type === "user";

  return (
    <div className={cn("flex items-start gap-3", isUser ? "flex-row-reverse" : "flex-row")}>
      {showAvatar && (
        <div
          className={cn(
            "flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center",
            isUser ? "bg-indigo-600" : "bg-indigo-100"
          )}
        >
          {isUser ? <User size={14} className="text-white" /> : <Bot size={14} className="text-indigo-600" />}
        </div>
      )}

      <div
        className={cn(
          // Option A: tightened prose
          "prose prose-sm !max-w-none !prose-p:my-1 !prose-ul:my-1 !prose-ol:my-1 leading-snug p-3",
          // Option B: custom spacing instead of prose
          // "leading-snug !max-w-none p-3 space-y-1",
          isUser ? "chat-bubble-user" : "chat-bubble-bot"
        )}
      >
        <Markdown
          remarkPlugins={[remarkGfm]}
          components={{
            // Optionally override child spacing even further:
            p: ({ node, ...props }) => <p className="mb-1">{props.children}</p>,
            li: ({ node, ...props }) => (
              <li className="ml-4 mb-1 list-disc">{props.children}</li>
            ),
          }}
        >
          {text}
        </Markdown>
      </div>
    </div>
  );
};

export default Message;
