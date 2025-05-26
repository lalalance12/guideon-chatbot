import React, { useEffect, useState } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Home from "./pages/Home";
import Chat from "./pages/Chat";
import Auth from "./pages/Auth";
import Preferences from "./pages/Preferences";
import LearningPathways from "./pages/LearningPathways";
import Courses from "./pages/Courses";
import Sidebar from "./components/Sidebar";
import { authService } from "./services/auth";
import { preferenceService } from "./services/preferences";
import "typeface-muli";

// Protected Route component with preferences check
const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const [checking, setChecking] = useState(true);
  const [hasPreferences, setHasPreferences] = useState(true);

  useEffect(() => {
    const checkPreferences = async () => {
      if (authService.isAuthenticated()) {
        try {
          const { has_preferences } = await preferenceService.checkFirstLogin();
          setHasPreferences(has_preferences);
        } catch (err) {
          console.error("Failed to check preferences status:", err);
        } finally {
          setChecking(false);
        }
      } else {
        setChecking(false);
      }
    };

    checkPreferences();
  }, []);

  if (checking) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="animate-pulse text-indigo-600 text-xl">Loading...</div>
      </div>
    );
  }

  if (!authService.isAuthenticated()) {
    return <Navigate to="/auth" replace />;
  }

  if (!hasPreferences) {
    return <Navigate to="/preferences" replace />;
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
          path="/preferences"
          element={
            authService.isAuthenticated() ? (
              <Preferences />
            ) : (
              <Navigate to="/auth" replace />
            )
          }
        />
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
