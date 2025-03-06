import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Home from './pages/Home';
// import Login from './pages/Login';
import ProtectedRoute from './components/ProtectedRoute';

const Logout = (): React.ReactElement => {
  localStorage.removeItem('token');
  return <Navigate to="/login" />;
};

const App = (): React.ReactElement => {
  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <Home />
            </ProtectedRoute>
          }
        />
        <Route
          path="/login"
          element={<Home />}
        />
      </Routes>
    </BrowserRouter>
  );
};

export default App;