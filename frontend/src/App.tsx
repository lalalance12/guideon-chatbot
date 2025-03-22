import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Home from "./pages/Home";
import Chat from "./pages/Chat";
import Sidebar from "./components/Sidebar";
import "typeface-muli";

// Layout component with sidebar for authenticated pages
const DashboardLayout = ({ children }: { children: React.ReactNode }) => (
  <div className="flex h-screen font-muli">
    <Sidebar />
    <div className="flex-1 pl-64">{children}</div>
  </div>
);

const App = (): React.ReactElement => {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route
          path="/chat"
          element={
            <DashboardLayout>
              <Chat />
            </DashboardLayout>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
};

export default App;
