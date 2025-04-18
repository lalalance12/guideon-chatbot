import api from '../api';
import { ACCESS_TOKEN } from '../constants';

export interface LoginCredentials {
    email: string;
    password: string;
}

export interface RegisterData extends LoginCredentials {
    fullName: string;
}

export interface User {
    id: number;
    email: string;
    fullName: string;
}

export interface AuthResponse {
    user: User;
    token: string;
}

export const authService = {
    async login(credentials: LoginCredentials): Promise<AuthResponse> {
        const { data } = await api.post<AuthResponse>('/api/auth/login/', credentials);
        localStorage.setItem(ACCESS_TOKEN, data.token);
        return data;
    },

    async register(userData: RegisterData): Promise<AuthResponse> {
        const { data } = await api.post<AuthResponse>('/api/auth/register/', userData);
        localStorage.setItem(ACCESS_TOKEN, data.token);
        return data;
    },

    async getCurrentUser(): Promise<User> {
        const { data } = await api.get<User>('/api/auth/me/');
        return data;
    },

    logout() {
        localStorage.removeItem(ACCESS_TOKEN);
    },

    isAuthenticated(): boolean {
        return !!localStorage.getItem(ACCESS_TOKEN);
    }
}; 