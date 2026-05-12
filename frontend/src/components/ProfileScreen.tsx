/**
 * Profile Screen - User profile and authentication
 */
import React, { useState } from 'react';
import { 
  User, LogOut, Settings, ChevronRight, 
  Shield, Edit3, Camera, Mail, Phone, UserCircle,
  X, Eye, EyeOff, Loader2
} from 'lucide-react';
import { useUser } from '../contexts/UserContext';

interface ProfileScreenProps {
  onNavigate?: (tab: string) => void;
}

export default function ProfileScreen({ onNavigate }: ProfileScreenProps) {
  const { user, isAuthenticated, isLoading, login, register, logout, updateProfile } = useUser();
  
  // Auth modal states
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [authMode, setAuthMode] = useState<'login' | 'register'>('login');
  const [authLoading, setAuthLoading] = useState(false);
  const [authError, setAuthError] = useState('');
  
  // Form states
  const [loginAccount, setLoginAccount] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  
  const [regUsername, setRegUsername] = useState('');
  const [regEmail, setRegEmail] = useState('');
  const [regPhone, setRegPhone] = useState('');
  const [regPassword, setRegPassword] = useState('');
  const [regNickname, setRegNickname] = useState('');
  
  // Edit profile states
  const [showEditModal, setShowEditModal] = useState(false);
  const [editNickname, setEditNickname] = useState(user?.nickname || '');
  const [editLoading, setEditLoading] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthError('');
    setAuthLoading(true);
    
    try {
      await login(loginAccount, loginPassword);
      setShowAuthModal(false);
      setLoginAccount('');
      setLoginPassword('');
    } catch (error: any) {
      setAuthError(error.message || '登录失败');
    } finally {
      setAuthLoading(false);
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthError('');
    setAuthLoading(true);
    
    // Validate at least one identifier
    if (!regUsername && !regEmail && !regPhone) {
      setAuthError('请至少填写用户名、邮箱或手机号中的一项');
      setAuthLoading(false);
      return;
    }
    
    try {
      await register({
        username: regUsername || undefined,
        email: regEmail || undefined,
        phone: regPhone || undefined,
        password: regPassword,
        nickname: regNickname || undefined
      });
      setShowAuthModal(false);
      setRegUsername('');
      setRegEmail('');
      setRegPhone('');
      setRegPassword('');
      setRegNickname('');
    } catch (error: any) {
      setAuthError(error.message || '注册失败');
    } finally {
      setAuthLoading(false);
    }
  };

  const handleUpdateProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setEditLoading(true);
    
    try {
      await updateProfile({ nickname: editNickname });
      setShowEditModal(false);
    } catch (error: any) {
      alert(error.message || '更新失败');
    } finally {
      setEditLoading(false);
    }
  };

  const handleLogout = async () => {
    if (confirm('确定要退出登录吗？')) {
      await logout();
    }
  };

  // Get display name
  const getDisplayName = () => {
    if (user?.nickname) return user.nickname;
    if (user?.username) return user.username;
    if (user?.phone) return user.phone.slice(0, 3) + '****' + user.phone.slice(-4);
    if (user?.email) return user.email.split('@')[0];
    return '匿名用户';
  };

  // Get account info
  const getAccountInfo = () => {
    if (user?.username) return `@${user.username}`;
    if (user?.phone) return user.phone;
    if (user?.email) return user.email;
    return '游客模式';
  };

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center h-full bg-gray-50">
        <Loader2 size={32} className="animate-spin text-blue-600 mb-4" />
        <p className="text-gray-500">加载中...</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full w-full bg-gray-50">
      {/* Header */}
      <header className="bg-white px-4 py-4 border-b border-gray-100">
        <h1 className="text-lg font-semibold text-gray-900">我的</h1>
      </header>

      {/* Scrollable Content */}
      <div className="flex-1 overflow-y-auto">
        {/* User Card */}
        <div className="bg-white mx-4 mt-4 rounded-2xl p-6 shadow-sm">
          <div className="flex items-center gap-4">
            {/* Avatar */}
            <div className="relative">
              <div className="w-20 h-20 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-white text-2xl font-bold">
                {user?.avatar ? (
                  <img src={user.avatar} alt="avatar" className="w-full h-full rounded-full object-cover" />
                ) : (
                  getDisplayName().charAt(0).toUpperCase()
                )}
              </div>
              {isAuthenticated && (
                <div className="absolute -bottom-1 -right-1 w-6 h-6 bg-green-500 rounded-full flex items-center justify-center">
                  <Shield size={14} className="text-white" />
                </div>
              )}
            </div>
            
            {/* User Info */}
            <div className="flex-1">
              <h2 className="text-xl font-bold text-gray-900">{getDisplayName()}</h2>
              <p className="text-sm text-gray-500 mt-1">{getAccountInfo()}</p>
              <div className="flex items-center gap-2 mt-2">
                <span className={`text-xs px-2 py-1 rounded-full ${
                  isAuthenticated 
                    ? 'bg-blue-100 text-blue-600' 
                    : 'bg-gray-100 text-gray-500'
                }`}>
                  {isAuthenticated ? '已登录' : '游客'}
                </span>
              </div>
            </div>
            
            {/* Edit Button */}
            {isAuthenticated && (
              <button 
                onClick={() => {
                  setEditNickname(user?.nickname || '');
                  setShowEditModal(true);
                }}
                className="p-2 hover:bg-gray-100 rounded-full transition-colors"
              >
                <Edit3 size={20} className="text-gray-400" />
              </button>
            )}
          </div>
          
          {/* Login/Register Buttons for anonymous users */}
          {!isAuthenticated && (
            <div className="flex gap-3 mt-6">
              <button 
                onClick={() => {
                  setAuthMode('login');
                  setShowAuthModal(true);
                  setAuthError('');
                }}
                className="flex-1 bg-blue-600 text-white py-3 rounded-xl font-medium hover:bg-blue-700 transition-colors"
              >
                登录
              </button>
              <button 
                onClick={() => {
                  setAuthMode('register');
                  setShowAuthModal(true);
                  setAuthError('');
                }}
                className="flex-1 bg-gray-100 text-gray-700 py-3 rounded-xl font-medium hover:bg-gray-200 transition-colors"
              >
                注册
              </button>
            </div>
          )}
        </div>

        {/* Menu Items */}
        <div className="mx-4 mt-4 bg-white rounded-2xl overflow-hidden shadow-sm">
          {/* Account Security */}
          <div className="px-4 py-3 border-b border-gray-50">
            <h3 className="text-sm font-medium text-gray-400">账号安全</h3>
          </div>
          
          {isAuthenticated ? (
            <>
              <MenuItem 
                icon={<UserCircle size={20} className="text-blue-500" />}
                title="账号信息"
                subtitle={user?.username || '未设置'}
              />
              <MenuItem 
                icon={<Mail size={20} className="text-green-500" />}
                title="邮箱绑定"
                subtitle={user?.email ? '已绑定' : '未绑定'}
              />
              <MenuItem 
                icon={<Phone size={20} className="text-purple-500" />}
                title="手机绑定"
                subtitle={user?.phone ? '已绑定' : '未绑定'}
              />
            </>
          ) : (
            <div className="px-4 py-6 text-center text-gray-400">
              <p className="text-sm">登录后可查看账号安全信息</p>
            </div>
          )}
        </div>

        {/* Settings */}
        <div className="mx-4 mt-4 bg-white rounded-2xl overflow-hidden shadow-sm">
          <div className="px-4 py-3 border-b border-gray-50">
            <h3 className="text-sm font-medium text-gray-400">设置</h3>
          </div>
          
          <MenuItem 
            icon={<Settings size={20} className="text-gray-500" />}
            title="通用设置"
            showArrow
          />
          
          {isAuthenticated && (
            <button 
              onClick={handleLogout}
              className="w-full flex items-center gap-3 px-4 py-4 hover:bg-gray-50 transition-colors text-red-500"
            >
              <LogOut size={20} />
              <span className="flex-1 text-left font-medium">退出登录</span>
            </button>
          )}
        </div>

        {/* Version Info */}
        <div className="text-center py-8 text-gray-400 text-xs">
          <p>MixCut v1.0.0</p>
          <p className="mt-1">用户ID: {user?.id.slice(0, 8)}...</p>
        </div>
      </div>

      {/* Auth Modal */}
      {showAuthModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-end sm:items-center justify-center">
          <div className="bg-white w-full sm:w-[400px] sm:rounded-2xl rounded-t-2xl max-h-[90vh] overflow-hidden">
            {/* Modal Header */}
            <div className="flex items-center justify-between px-4 py-4 border-b border-gray-100">
              <h2 className="text-lg font-semibold">
                {authMode === 'login' ? '登录' : '注册'}
              </h2>
              <button 
                onClick={() => setShowAuthModal(false)}
                className="p-2 hover:bg-gray-100 rounded-full"
              >
                <X size={20} />
              </button>
            </div>
            
            {/* Modal Content */}
            <div className="p-4 overflow-y-auto max-h-[70vh]">
              {/* Toggle */}
              <div className="flex bg-gray-100 rounded-xl p-1 mb-6">
                <button
                  onClick={() => { setAuthMode('login'); setAuthError(''); }}
                  className={`flex-1 py-2 text-sm font-medium rounded-lg transition-colors ${
                    authMode === 'login' ? 'bg-white text-blue-600 shadow-sm' : 'text-gray-500'
                  }`}
                >
                  登录
                </button>
                <button
                  onClick={() => { setAuthMode('register'); setAuthError(''); }}
                  className={`flex-1 py-2 text-sm font-medium rounded-lg transition-colors ${
                    authMode === 'register' ? 'bg-white text-blue-600 shadow-sm' : 'text-gray-500'
                  }`}
                >
                  注册
                </button>
              </div>
              
              {/* Error Message */}
              {authError && (
                <div className="mb-4 p-3 bg-red-50 text-red-600 text-sm rounded-lg">
                  {authError}
                </div>
              )}
              
              {authMode === 'login' ? (
                /* Login Form */
                <form onSubmit={handleLogin} className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      用户名/邮箱/手机号
                    </label>
                    <input
                      type="text"
                      value={loginAccount}
                      onChange={(e) => setLoginAccount(e.target.value)}
                      className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500"
                      placeholder="请输入"
                      required
                    />
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      密码
                    </label>
                    <div className="relative">
                      <input
                        type={showPassword ? 'text' : 'password'}
                        value={loginPassword}
                        onChange={(e) => setLoginPassword(e.target.value)}
                        className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 pr-12"
                        placeholder="请输入密码"
                        required
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400"
                      >
                        {showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
                      </button>
                    </div>
                  </div>
                  
                  <button
                    type="submit"
                    disabled={authLoading}
                    className="w-full bg-blue-600 text-white py-3 rounded-xl font-medium hover:bg-blue-700 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
                  >
                    {authLoading && <Loader2 size={18} className="animate-spin" />}
                    登录
                  </button>
                </form>
              ) : (
                /* Register Form */
                <form onSubmit={handleRegister} className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      用户名 <span className="text-gray-400">(选填)</span>
                    </label>
                    <input
                      type="text"
                      value={regUsername}
                      onChange={(e) => setRegUsername(e.target.value)}
                      className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500"
                      placeholder="3-20位字母数字下划线"
                    />
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      邮箱 <span className="text-gray-400">(选填)</span>
                    </label>
                    <input
                      type="email"
                      value={regEmail}
                      onChange={(e) => setRegEmail(e.target.value)}
                      className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500"
                      placeholder="example@email.com"
                    />
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      手机号 <span className="text-gray-400">(选填)</span>
                    </label>
                    <input
                      type="tel"
                      value={regPhone}
                      onChange={(e) => setRegPhone(e.target.value)}
                      className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500"
                      placeholder="11位手机号"
                    />
                  </div>
                  
                  <p className="text-xs text-gray-400">
                    * 用户名、邮箱、手机号至少填写一项
                  </p>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      密码 <span className="text-red-500">*</span>
                    </label>
                    <div className="relative">
                      <input
                        type={showPassword ? 'text' : 'password'}
                        value={regPassword}
                        onChange={(e) => setRegPassword(e.target.value)}
                        className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 pr-12"
                        placeholder="至少6位字符"
                        required
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400"
                      >
                        {showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
                      </button>
                    </div>
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      昵称 <span className="text-gray-400">(选填)</span>
                    </label>
                    <input
                      type="text"
                      value={regNickname}
                      onChange={(e) => setRegNickname(e.target.value)}
                      className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500"
                      placeholder="显示名称"
                    />
                  </div>
                  
                  <button
                    type="submit"
                    disabled={authLoading}
                    className="w-full bg-blue-600 text-white py-3 rounded-xl font-medium hover:bg-blue-700 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
                  >
                    {authLoading && <Loader2 size={18} className="animate-spin" />}
                    注册
                  </button>
                </form>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Edit Profile Modal */}
      {showEditModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white w-full max-w-sm rounded-2xl overflow-hidden">
            <div className="flex items-center justify-between px-4 py-4 border-b border-gray-100">
              <h2 className="text-lg font-semibold">编辑资料</h2>
              <button 
                onClick={() => setShowEditModal(false)}
                className="p-2 hover:bg-gray-100 rounded-full"
              >
                <X size={20} />
              </button>
            </div>
            
            <form onSubmit={handleUpdateProfile} className="p-4">
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  昵称
                </label>
                <input
                  type="text"
                  value={editNickname}
                  onChange={(e) => setEditNickname(e.target.value)}
                  className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="请输入昵称"
                  maxLength={50}
                />
              </div>
              
              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={() => setShowEditModal(false)}
                  className="flex-1 py-3 border border-gray-200 rounded-xl font-medium text-gray-600 hover:bg-gray-50"
                >
                  取消
                </button>
                <button
                  type="submit"
                  disabled={editLoading}
                  className="flex-1 bg-blue-600 text-white py-3 rounded-xl font-medium hover:bg-blue-700 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
                >
                  {editLoading && <Loader2 size={18} className="animate-spin" />}
                  保存
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

// Menu Item Component
function MenuItem({ 
  icon, 
  title, 
  subtitle, 
  showArrow = false,
  onClick 
}: { 
  icon: React.ReactNode;
  title: string;
  subtitle?: string;
  showArrow?: boolean;
  onClick?: () => void;
}) {
  return (
    <button 
      onClick={onClick}
      className="w-full flex items-center gap-3 px-4 py-4 hover:bg-gray-50 transition-colors border-b border-gray-50 last:border-b-0"
    >
      {icon}
      <span className="flex-1 text-left font-medium text-gray-700">{title}</span>
      {subtitle && <span className="text-sm text-gray-400">{subtitle}</span>}
      {showArrow && <ChevronRight size={18} className="text-gray-300" />}
    </button>
  );
}
