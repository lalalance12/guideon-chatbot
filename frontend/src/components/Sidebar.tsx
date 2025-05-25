import {
  MoreVertical,
  BookOpen,
  MessageSquare,
  Compass,
  Settings,
  LogOut,
} from "lucide-react";
import { createContext, useContext, ReactNode, useEffect, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { authService, User } from "../services/auth";

interface SidebarContextProps {
  expanded: boolean;
}

const SidebarContext = createContext<SidebarContextProps | undefined>(
  undefined
);

interface SidebarProps {
  children?: ReactNode;
}

export default function Sidebar({ children }: SidebarProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const [currentUser, setCurrentUser] = useState<User | null>(null);

  useEffect(() => {
    const fetchUser = async () => {
      try {
        const user = await authService.getCurrentUser();
        setCurrentUser(user);
      } catch (error) {
        console.error('Failed to fetch user:', error);
      }
    };

    fetchUser();
  }, []);

  const handleLogout = () => {
    authService.logout();
    navigate('/auth');
  };

  const handleNavigateToLearningPaths = () => {
    navigate('/learning-pathways');
  };

  const handleNavigateToCourses = () => {
    navigate('/courses');
  };

  const handleNavigateToChat = () => {
    navigate('/chat');
  };

  return (
    <aside className="h-screen w-64 fixed left-0">
      <nav className="h-full flex flex-col bg-white border-r border-gray-200 shadow-sm">
        <div className="p-4 pb-2 flex justify-center items-center border-b border-gray-100">
          <h1 className="text-2xl font-bold text-indigo-600">Guideon</h1>
        </div>

        <div className="px-4 py-8">
          <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
            Learning Hub
          </h2>
          <SidebarContext.Provider value={{ expanded: true }}>
            <ul className="space-y-2">
              <SidebarItem
                icon={<MessageSquare size={18} />}
                text="Chat with Guideon"
                active={location.pathname === '/chat' || location.pathname === '/'}
                onClick={handleNavigateToChat}
              />
              <SidebarItem
                icon={<Compass size={18} />}
                text="Courses"
                onClick={handleNavigateToCourses}
                active={location.pathname === '/courses'}
              />
              <SidebarItem
                icon={<BookOpen size={18} />}
                text="Learning Paths"
                alert
                onClick={handleNavigateToLearningPaths}
                active={location.pathname === '/learning-pathways'}
              />
            </ul>
          </SidebarContext.Provider>
        </div>

        <div className="mt-auto px-4 py-6 border-t border-gray-100">
          <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
            Account
          </h2>
          <ul className="space-y-2">
            <SidebarItem icon={<Settings size={18} />} text="Settings" />
            <SidebarItem 
              icon={<LogOut size={18} />} 
              text="Logout" 
              onClick={handleLogout}
            />
          </ul>
        </div>

        <div className="flex p-4 border-t border-gray-100">
          <img
            src={`https://ui-avatars.com/api/?name=${encodeURIComponent(currentUser?.fullName || '')}&background=eef2ff&color=4f46e5&bold=true`}
            alt="User Avatar"
            className="w-10 h-10 rounded-full"
          />
          <div className="flex justify-between items-center w-full ml-3">
            <div className="leading-4">
              <h4 className="font-semibold text-gray-800">{currentUser?.fullName || '-'}</h4>
              <span className="text-xs text-gray-500">{currentUser?.email || ''}</span>
            </div>
            <button
              className="p-1 rounded-full hover:bg-gray-100 transition-smooth"
              aria-label="User menu options"
            >
              <MoreVertical size={18} className="text-gray-500" />
            </button>
          </div>
        </div>
      </nav>
    </aside>
  );
}

interface SidebarItemProps {
  icon: ReactNode;
  text: string;
  active?: boolean;
  alert?: boolean;
  onClick?: () => void;
}

export function SidebarItem({
  icon,
  text,
  active = false,
  alert = false,
  onClick,
}: SidebarItemProps) {
  return (
    <li
      onClick={onClick}
      className={`
        relative flex items-center py-2 px-3 my-1
        font-medium rounded-md cursor-pointer
        transition-smooth
        ${
          active
            ? "bg-indigo-50 text-indigo-600"
            : "hover:bg-gray-50 text-gray-700"
        }
      `}
    >
      <span className={`${active ? "text-indigo-600" : "text-gray-500"}`}>
        {icon}
      </span>
      <span className="ml-3 overflow-hidden">{text}</span>
      {alert && (
        <div className="absolute right-2 w-2 h-2 rounded-full bg-indigo-600" />
      )}
    </li>
  );
}
