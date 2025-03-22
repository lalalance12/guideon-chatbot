import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Sidebar, { SidebarItem } from "./components/Sidebar";
import { MessageSquarePlus, Settings } from "lucide-react";
import Dashboard from "./components/Dashboard";
import "typeface-muli";

const App = (): React.ReactElement => {
  return (
    <main className="flex gap-4 h-screen font-muli bg-surface-a0">
      <Sidebar>
        <SidebarItem
          icon={<MessageSquarePlus size={20} />}
          text="New Message"
        />
        <SidebarItem icon={<Settings size={20} />} text="Settings" active />
      </Sidebar>
      <Dashboard />
    </main>
  );
};

export default App;
