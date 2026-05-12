/**
 * User Context - Manage user authentication and profile
 */
import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';

const API_BASE_URL = (import.meta as any).env?.VITE_API_URL || 'http://localhost:3002';

export interface User {
  id: string;
  type: 'anonymous' | 'registered';
  username?: string;
  email?: string;
  phone?: string;
  nickname?: string;
  avatar?: string;
  is_active: boolean;
  created_at: string;
  updated_at?: string;
  last_login_at?: string;
}

interface UserContextType {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (account: string, password: string) => Promise<void>;
  register: (data: RegisterData) => Promise<void>;
  logout: () => void;
  updateProfile: (data: Partial<User>) => Promise<void>;
  changePassword: (oldPassword: string, newPassword: string) => Promise<void>;
  refreshUser: () => Promise<void>;
  setOnLogoutCallback: (callback: (() => void) | undefined) => void;
}

interface RegisterData {
  username?: string;
  email?: string;
  phone?: string;
  password: string;
  nickname?: string;
}

const UserContext = createContext<UserContextType | undefined>(undefined);

export function UserProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  // 使用 ref 存储回调，避免触发重新渲染
  const onLogoutCallbackRef = useRef<(() => void) | undefined>(undefined);

  // Initialize user on mount
  useEffect(() => {
    initUser();
  }, []);

  const initUser = async () => {
    const storedUserId = localStorage.getItem('mixcut_user_id');
    
    if (storedUserId) {
      try {
        // Try to get user profile
        const response = await fetch(`${API_BASE_URL}/api/auth/profile?user_id=${storedUserId}`);
        if (response.ok) {
          const data = await response.json();
          setUser(data.user);
          setIsLoading(false);
          return;
        }
      } catch (e) {
        console.log('Failed to fetch user profile, trying legacy endpoint');
      }

      // Fallback to legacy user endpoint
      try {
        const response = await fetch(`${API_BASE_URL}/api/users/${storedUserId}`);
        if (response.ok) {
          const data = await response.json();
          setUser({
            id: data.id,
            type: data.type,
            nickname: data.nickname,
            is_active: true,
            created_at: data.created_at
          });
          setIsLoading(false);
          return;
        }
      } catch (e) {
        console.log('Failed to fetch user from legacy endpoint');
      }
      
      // User not found, clear localStorage
      localStorage.removeItem('mixcut_user_id');
    }
    
    // Create new anonymous user
    try {
      const response = await fetch(`${API_BASE_URL}/api/users`, {
        method: 'POST'
      });
      
      if (response.ok) {
        const newUser = await response.json();
        setUser({
          id: newUser.id,
          type: newUser.type,
          is_active: true,
          created_at: newUser.created_at
        });
        localStorage.setItem('mixcut_user_id', newUser.id);
      }
    } catch (e) {
      console.error('Failed to create user:', e);
    } finally {
      setIsLoading(false);
    }
  };

  const login = async (account: string, password: string) => {
    const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ account, password })
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || '登录失败');
    }

    const data = await response.json();
    setUser(data.user);
    localStorage.setItem('mixcut_user_id', data.user.id);
  };

  const register = async (data: RegisterData) => {
    const response = await fetch(`${API_BASE_URL}/api/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || '注册失败');
    }

    const result = await response.json();
    setUser(result.user);
    localStorage.setItem('mixcut_user_id', result.user.id);
  };

  const logout = async () => {
    try {
      await fetch(`${API_BASE_URL}/api/auth/logout`, {
        method: 'POST'
      });
    } catch (e) {
      console.log('Logout API call failed');
    }

    // Call the logout callback to clear app state (combinations, etc.)
    if (onLogoutCallbackRef.current) {
      onLogoutCallbackRef.current();
    }

    // Clear user state
    setUser(null);
    localStorage.removeItem('mixcut_user_id');
    
    // Create new anonymous user
    await initUser();
  };

  const updateProfile = async (data: Partial<User>) => {
    if (!user) throw new Error('用户未登录');

    const response = await fetch(`${API_BASE_URL}/api/auth/profile`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: user.id, ...data })
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || '更新失败');
    }

    const result = await response.json();
    setUser(result.user);
  };

  const changePassword = async (oldPassword: string, newPassword: string) => {
    if (!user) throw new Error('用户未登录');

    const response = await fetch(`${API_BASE_URL}/api/auth/change-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: user.id, old_password: oldPassword, new_password: newPassword })
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || '修改密码失败');
    }
  };

  const refreshUser = async () => {
    if (!user) return;

    try {
      const response = await fetch(`${API_BASE_URL}/api/auth/profile?user_id=${user.id}`);
      if (response.ok) {
        const data = await response.json();
        setUser(data.user);
      }
    } catch (e) {
      console.error('Failed to refresh user:', e);
    }
  };

  // 使用 ref 存储回调，直接修改 ref 不会触发重新渲染
  const setOnLogoutCallback = useCallback((callback: (() => void) | undefined) => {
    onLogoutCallbackRef.current = callback;
  }, []);

  const value: UserContextType = {
    user,
    isLoading,
    isAuthenticated: user?.type === 'registered',
    login,
    register,
    logout,
    updateProfile,
    changePassword,
    refreshUser,
    setOnLogoutCallback
  };

  return (
    <UserContext.Provider value={value}>
      {children}
    </UserContext.Provider>
  );
}

export function useUser() {
  const context = useContext(UserContext);
  if (context === undefined) {
    throw new Error('useUser must be used within a UserProvider');
  }
  return context;
}
