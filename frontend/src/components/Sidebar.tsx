import { MoreVertical } from "lucide-react";
import { createContext, useContext, ReactNode } from "react";

interface SidebarContextProps {
  expanded: boolean;
}

const SidebarContext = createContext<SidebarContextProps | undefined>(
  undefined
);

interface SidebarProps {
  children: ReactNode;
}

export default function Sidebar({ children }: SidebarProps) {
  return (
    <aside className="h-screen w-56 absolute left-0">
      <nav className="h-full flex flex-col bg-surface-a0 text-light-a0 shadow-sm">
        <div className="p-4 pb-2 flex justify-center items-center">
          <h1 className="text-5xl text-primary-a0 "> LOGO </h1>
        </div>

        <SidebarContext.Provider value={{ expanded: true }}>
          <ul className="flex-1 px-3">{children}</ul>
        </SidebarContext.Provider>

        <div className="flex p-3">
          <img
            src="https://ui-avatars.com/api/?background=c7d2fe&color=3730a3&bold=true"
            alt="User Avatar"
            className="w-8 h-8 rounded-md"
          />
          <div className="flex justify-between items-center w-52 ml-3">
            <div className="leading-4">
              <h4 className="font-semibold">John Doe</h4>
              <span className="text-xs">johndoe@gmail.com</span>
            </div>
            <MoreVertical size={20} />
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
}

export function SidebarItem({
  icon,
  text,
  active = false,
  alert = false,
}: SidebarItemProps) {
  return (
    <li
      className={`
        relative flex items-center py-2 px-3 my-1
        font-medium rounded-md cursor-pointer
        transition-colors group
        ${
          active
            ? "bg-gradient-to-tr from-primary-a30 to-primary-a40 text-surface-tonal-a0"
            : "hover:bg-surface-tonal-a10 text-light-a0"
        }
      `}
    >
      {icon}
      <span className="w-36 ml-3 overflow-hidden transition-all">{text}</span>
      {alert && (
        <div className="absolute right-2 w-2 h-2 rounded bg-indigo-400" />
      )}
    </li>
  );
}
