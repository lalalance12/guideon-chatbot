// components/Message.tsx
import { cn } from "@/lib/utils";
import { Bot, User } from "lucide-react";
import React from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import CourseCard from "./CourseCard";
import { Course } from "../services/courseService";

interface MessageProps {
  text: string;
  type: "user" | "guideon";
  showAvatar?: boolean;
  courses?: Course[];
}

const Message: React.FC<MessageProps> = ({ text, type, showAvatar = true, courses }) => {
  const isUser = type === "user";

  return (
    <div className={cn("flex items-start gap-3", isUser ? "flex-row-reverse" : "flex-row")}>
      {showAvatar && (
        <div
          className={cn(
            "flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center shadow-sm",
            isUser ? "bg-indigo-600" : "bg-indigo-100"
          )}
        >
          {isUser ? <User size={16} className="text-white" /> : <Bot size={16} className="text-indigo-600" />}
        </div>
      )}

      <div
        className={cn(
          "prose prose-sm max-w-none prose-headings:font-semibold prose-headings:text-gray-800 prose-p:leading-relaxed prose-p:my-2 prose-ul:my-2 prose-ol:my-2 prose-li:my-1 prose-code:rounded prose-code:bg-gray-100 prose-code:px-1 prose-code:py-0.5 prose-code:text-sm prose-code:font-mono prose-code:before:content-none prose-code:after:content-none p-4 rounded-2xl shadow-sm",
          isUser 
            ? "chat-bubble-user bg-indigo-600 text-white prose-headings:text-white prose-strong:text-white prose-code:bg-indigo-500/30 prose-code:text-white" 
            : "chat-bubble-bot bg-white text-gray-700 border border-gray-100"
        )}
      >
        <Markdown
          remarkPlugins={[remarkGfm]}
          components={{
            h1: ({node, ...props}) => <h1 className="text-xl font-bold mt-4 mb-2" {...props} />,
            h2: ({node, ...props}) => <h2 className="text-lg font-bold mt-3 mb-2" {...props} />,
            h3: ({node, ...props}) => <h3 className="text-base font-semibold mt-3 mb-1" {...props} />,
            p: ({ node, ...props }) => <p className="mb-2 leading-relaxed" {...props} />,
            ul: ({ node, ...props }) => <ul className="my-2 pl-4" {...props} />,
            ol: ({ node, ...props }) => <ol className="my-2 pl-4" {...props} />,
            li: ({ node, ...props }) => (
              <li className="ml-2 mb-1 list-disc" {...props} />
            ),
            a: ({node, ...props}) => <a className={cn("underline", isUser ? "text-blue-100" : "text-indigo-600")} {...props} />,
            code: ({node, ...props}: {node?: any; inline?: boolean}) => 
              props.inline ? (
                <code className={cn("px-1 py-0.5 rounded font-mono text-sm", isUser ? "bg-indigo-500/30 text-white" : "bg-gray-100 text-gray-800")} {...props} />
              ) : (
                <div className={cn("rounded-md my-2 p-3 text-sm font-mono overflow-x-auto", isUser ? "bg-indigo-500/30 text-white" : "bg-gray-100 text-gray-800")}>
                  <code {...(props as React.HTMLAttributes<HTMLElement>)} />
                </div>
              ),
          }}
        >
          {text}
        </Markdown>
        
        {courses && courses.length > 0 && (
          <div className="mt-6 space-y-4">
            <h3 className={cn("font-medium text-base border-t pt-3", isUser ? "text-white border-indigo-500/30" : "text-gray-700 border-gray-100")}>
              Recommended Courses:
            </h3>
            {courses.map((course, index) => (
              <CourseCard key={index} course={course} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default Message;
