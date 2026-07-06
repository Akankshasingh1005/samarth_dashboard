import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Eye, EyeOff, AlertCircle, Target, BarChart2, Bot } from 'lucide-react';
import { authApi } from '@/api';
import { useAuthStore } from '@/stores/authStore';
import { toast } from 'sonner';
import type { User } from '@/types';

export default function LoginPage() {
  const navigate = useNavigate();
  const { setAuth } = useAuthStore();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPass, setShowPass] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const data = await authApi.login(email.trim(), password);
      const user: User = {
        id: data.user_id,
        email: email.trim(),
        role: data.role as User['role'],
        first_name: data.full_name.split(' ')[0],
        last_name: data.full_name.split(' ').slice(1).join(' '),
        full_name: data.full_name,
        is_active: true,
        created_at: new Date().toISOString(),
      };
      setAuth(data, user);
      toast.success(`Welcome back, ${user.first_name}!`);
      if (data.role === 'therapist' || data.role === 'admin') navigate('/therapist/dashboard');
      else navigate('/dashboard');
    } catch (err: any) {
      let message = 'Login failed. Please check your credentials.';
      if (!err.response) {
        message = 'Cannot reach the backend server. Please make sure it is running on http://localhost:8000.';
      } else if (err.response.status === 502 || err.response.status === 504) {
        message = 'Backend server is offline or proxy error. Please make sure it is running on http://localhost:8000.';
      } else if (err.response.data?.detail) {
        const detail = err.response.data.detail;
        if (typeof detail === 'string') {
          message = detail;
        } else if (Array.isArray(detail)) {
          message = detail
            .map((d: any) => {
              const field = d.loc && d.loc.length > 0 ? d.loc[d.loc.length - 1] : '';
              return field ? `${field}: ${d.msg}` : d.msg;
            })
            .join(', ');
        } else {
          message = typeof detail === 'object' ? JSON.stringify(detail) : String(detail);
        }
      } else {
        message = err.response.data?.message || err.response.statusText || 'Login failed. Please check your credentials.';
      }
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const features = [
    { Icon: Target,    text: 'Real-time joint angle tracking' },
    { Icon: BarChart2, text: 'Bilateral symmetry analysis' },
    { Icon: Bot,       text: 'AI-powered form feedback' },
  ];

  return (
    <div className="min-h-screen bg-[#F8FAFC] flex">
      {/* Left panel */}
      <div className="hidden lg:flex lg:w-1/2 bg-navy relative overflow-hidden">
        {/* subtle tonal circles, same hue */}
        <div className="absolute top-20 left-20 w-64 h-64 bg-white/5 rounded-full blur-3xl" />
        <div className="absolute bottom-20 right-20 w-48 h-48 bg-white/5 rounded-full blur-3xl" />

        <div className="relative z-10 flex flex-col justify-center px-16 text-white">
          {/* Logo */}
          <div className="flex items-center gap-3 mb-12">
            <img src="/logo.jpeg" alt="Samarth" className="w-12 h-12 rounded-full object-cover" />
            <span className="text-3xl font-display font-bold">SAMARTH</span>
          </div>

          <h1 className="text-4xl font-display font-bold leading-tight mb-6">
            AI-Guided<br />Physiotherapy<br />Rehabilitation
          </h1>
          <p className="text-white/75 text-lg leading-relaxed mb-10">
            Smart Augmented Mobility & Adaptive Rehabilitation Technologies for Humans
          </p>

          <div className="flex flex-col gap-4">
            {features.map(({ Icon, text }) => (
              <div key={text} className="flex items-center gap-3 text-white/90">
                <div className="w-8 h-8 rounded-lg bg-brand/30 flex items-center justify-center flex-shrink-0">
                  <Icon className="w-4 h-4 text-white" />
                </div>
                <span className="font-medium">{text}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Right panel */}
      <div className="w-full lg:w-1/2 flex items-center justify-center p-8 bg-[#F8FAFC]">
        <div className="w-full max-w-md">
          {/* Mobile logo */}
          <div className="flex items-center gap-3 mb-8 lg:hidden">
            <img src="/logo.jpeg" alt="Samarth" className="w-10 h-10 rounded-full object-cover" />
            <span className="text-2xl font-display font-bold text-[#0F172A]">Samarth</span>
          </div>

          <div className="mb-8">
            <h2 className="text-3xl font-display font-bold text-[#0F172A]">Welcome back</h2>
            <p className="text-slate-500 mt-2">Sign in to your account to continue your recovery</p>
          </div>

          {error && (
            <div className="mb-6 flex items-center gap-3 p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm">
              <AlertCircle className="w-5 h-5 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleLogin} className="space-y-5">
            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-2">Email address</label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="samarth-input"
                placeholder="you@example.com"
                required
                autoComplete="email"
              />
            </div>

            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-2">Password</label>
              <div className="relative">
                <input
                  id="password"
                  type={showPass ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="samarth-input pr-12"
                  placeholder="Enter your password"
                  required
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  onClick={() => setShowPass(!showPass)}
                  className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition-colors"
                >
                  {showPass ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full py-3 text-base"
              id="login-submit"
            >
              {loading ? (
                <span className="flex items-center gap-2">
                  <svg className="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Signing in...
                </span>
              ) : 'Sign In'}
            </button>
          </form>

          <div className="mt-6 text-center text-sm text-slate-500">
            Don't have an account?{' '}
            <Link to="/register" className="text-brand font-semibold hover:underline">
              Create one
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
