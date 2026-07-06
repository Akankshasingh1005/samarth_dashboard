import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Eye, EyeOff, AlertCircle, Leaf, Video, TrendingUp } from 'lucide-react';
import { authApi } from '@/api';
import { useAuthStore } from '@/stores/authStore';
import { toast } from 'sonner';
import type { User } from '@/types';

export default function RegisterPage() {
  const navigate = useNavigate();
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPass, setShowPass] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const validatePassword = (value: string) => {
    if (value.length < 8) return 'Password must be at least 8 characters long.';
    if (!/[a-z]/.test(value)) return 'Password must contain at least one lowercase letter.';
    if (!/[A-Z]/.test(value)) return 'Password must contain at least one uppercase letter.';
    if (!/[0-9]/.test(value)) return 'Password must contain at least one number.';
    if (!/[!@#$%^&*()_+\-=[\]{};:'",.<>?/\\|`~]/.test(value)) return 'Password must contain at least one special character.';
    return '';
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    const passwordError = validatePassword(password);
    if (passwordError) {
      setError(passwordError);
      return;
    }
    setLoading(true);
    try {
      const { setAuth } = useAuthStore.getState();
      const data = await authApi.register({
        email: email.trim(),
        password,
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        role: 'patient',
      });
      const user: User = {
        id: data.user_id,
        email: email.trim(),
        role: data.role as User['role'],
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        full_name: data.full_name,
        is_active: true,
        created_at: new Date().toISOString(),
      };
      setAuth(data, user);
      toast.success('Welcome to Samarth!');
      navigate('/dashboard');
    } catch (err: any) {
      let message = 'Registration failed. Please try again.';
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
        message = err.response.data?.message || err.response.statusText || 'Registration failed. Please try again.';
      }
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const features = [
    { Icon: Leaf,       text: 'Free setup & custom exercise plans' },
    { Icon: Video,      text: 'Record or stream sessions for analysis' },
    { Icon: TrendingUp, text: 'Detailed joint ROM recovery analytics' },
  ];

  return (
    <div className="min-h-screen bg-[#F8FAFC] flex">
      {/* Left panel */}
      <div className="hidden lg:flex lg:w-1/2 bg-navy relative overflow-hidden">
        <div className="absolute top-20 left-20 w-64 h-64 bg-white/5 rounded-full blur-3xl" />
        <div className="absolute bottom-20 right-20 w-48 h-48 bg-white/5 rounded-full blur-3xl" />

        <div className="relative z-10 flex flex-col justify-center px-16 text-white">
          <div className="flex items-center gap-3 mb-12">
            <img src="/logo.jpeg" alt="Samarth" className="w-12 h-12 rounded-full object-cover" />
            <span className="text-3xl font-display font-bold">Samarth</span>
          </div>

          <h1 className="text-4xl font-display font-bold leading-tight mb-6">
            Join the AI-Guided<br />Rehabilitation<br />Journey
          </h1>
          <p className="text-white/75 text-lg leading-relaxed mb-10">
            Create an account to start your customized physiotherapy exercises and get instant biomechanical feedback.
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
            <h2 className="text-3xl font-display font-bold text-[#0F172A]">Create your account</h2>
            <p className="text-slate-500 mt-2">Get started with your rehabilitation program</p>
          </div>

          {error && (
            <div className="mb-6 flex items-center gap-3 p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm">
              <AlertCircle className="w-5 h-5 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleRegister} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-1.5">First name</label>
                <input
                  id="firstName"
                  type="text"
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                  className="samarth-input"
                  placeholder="John"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-1.5">Last name</label>
                <input
                  id="lastName"
                  type="text"
                  value={lastName}
                  onChange={(e) => setLastName(e.target.value)}
                  className="samarth-input"
                  placeholder="Doe"
                  required
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-1.5">Email address</label>
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
              <label className="block text-sm font-semibold text-slate-700 mb-1.5">Password</label>
              <div className="relative">
                <input
                  id="password"
                  type={showPass ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="samarth-input pr-12"
                  placeholder="Create a strong password"
                  required
                  autoComplete="new-password"
                />
                <button
                  type="button"
                  onClick={() => setShowPass(!showPass)}
                  className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition-colors"
                >
                  {showPass ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
              <p className="text-xs text-slate-500 mt-2">
                Password must contain: uppercase, lowercase, number & special character (!@#$%)
              </p>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full py-3 text-base mt-2"
              id="register-submit"
            >
              {loading ? (
                <span className="flex items-center gap-2 justify-center">
                  <svg className="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Creating account...
                </span>
              ) : 'Register'}
            </button>
          </form>

          <div className="mt-6 text-center text-sm text-slate-500">
            Already have an account?{' '}
            <Link to="/login" className="text-brand font-semibold hover:underline">
              Sign In
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
