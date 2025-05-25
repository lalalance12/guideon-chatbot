import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Home from "./pages/Home";
import Chat from "./pages/Chat";
import Auth from "./pages/Auth";
import LearningPathways from "./pages/LearningPathways";
import Courses from "./pages/Courses";
import Sidebar from "./components/Sidebar";
import { authService } from "./services/auth";
import "typeface-muli";

// Protected Route component
const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  if (!authService.isAuthenticated()) {
    return <Navigate to="/auth" replace />;
  }
  return <>{children}</>;
};

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
        <Route path="/auth" element={<Auth />} />
        <Route
          path="/chat"
          element={
            <ProtectedRoute>
              <DashboardLayout>
                <Chat />
              </DashboardLayout>
            </ProtectedRoute>
          }
        />
        <Route
          path="/learning-pathways"
          element={
            <ProtectedRoute>
              <DashboardLayout>
                <LearningPathways />
              </DashboardLayout>
            </ProtectedRoute>
          }
        />
        <Route
          path="/courses"
          element={
            <ProtectedRoute>
              <DashboardLayout>
                <Courses />
              </DashboardLayout>
            </ProtectedRoute>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
};

export default App;
