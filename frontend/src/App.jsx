import React from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Home from './pages/Home.jsx'
// import Login from './pages/Login.jsx'
import ProtectedRoute from './components/ProtectedRoute.jsx'

function Logout() {
  localStorage.removeItem('token')
  return <Navigate to="/login" />
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/"
          element={
            // <ProtectedRoute>
              <Home />
            // </ProtectedRoute>
          }
        />
        <Route
          path="/login"
          element={<Home />}
        />
      </Routes>
    </BrowserRouter>
  )
}

export default App
