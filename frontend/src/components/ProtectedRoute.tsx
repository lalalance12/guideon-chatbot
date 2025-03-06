import React, { ReactNode, useState, useEffect } from 'react';
import { Navigate } from 'react-router-dom';
import { jwtDecode } from 'jwt-decode';
import api from '../api';
import { ACCESS_TOKEN, REFRESH_TOKEN } from '../constants';

interface ProtectedRouteProps {
  children: ReactNode;
}

interface JwtPayload {
  exp: number;
  [key: string]: any;
}

const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children }) => {
  const [isAuthorized, setIsAuthorized] = useState<boolean | null>(null);

  useEffect(() => {
    auth().catch(() => setIsAuthorized(false));
  }, []);

  const refreshToken = async (): Promise<void> => {
    const refreshTokenValue = localStorage.getItem(REFRESH_TOKEN);
    if (!refreshTokenValue) {
      setIsAuthorized(false);
      return;
    }

    try {
      const response = await api.post('/api/token/refresh/', {
        refresh: refreshTokenValue,
      });
      
      if (response.status === 200) {
        localStorage.setItem(ACCESS_TOKEN, response.data.access);
        setIsAuthorized(true);
      } else {
        setIsAuthorized(false);
      }
    } catch (error) {
      console.error(error);
      setIsAuthorized(false);
    }
  };

  const auth = async (): Promise<void> => {
    const token = localStorage.getItem(ACCESS_TOKEN);
    if (!token) {
      setIsAuthorized(false);
      return;
    }

    try {
      const decoded = jwtDecode<JwtPayload>(token);
      const tokenExpiration = decoded.exp;
      const now = Date.now() / 1000;

      if (tokenExpiration < now) {
        await refreshToken();
      } else {
        // Token is still valid
        setIsAuthorized(true);
      }
    } catch (error) {
      console.error('Token decoding error:', error);
      setIsAuthorized(false);
    }
  };

  if (isAuthorized === null) {
    return null;
  }

  return isAuthorized ? <>{children}</> : <Navigate to="/login" />;
};

export default ProtectedRoute;