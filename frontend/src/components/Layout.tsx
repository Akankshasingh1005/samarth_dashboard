import { useState, useEffect } from 'react';
import { Outlet, Link, useNavigate, useLocation } from 'react-router-dom';
import {
  LayoutDashboard, Dumbbell, BarChart3, FileText,
  LogOut, User as UserIcon, Menu, X
} from 'lucide-react';
import { useAuthStore } from '@/stores/authStore';

export default function Layout() {
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();
  const location = useLocation();
  const [dark] = useState(() => {
    return document.documentElement.classList.contains('dark') ||
      localStorage.getItem('theme') === 'dark';
  });
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    if (dark) {
      document.documentElement.classList.add('dark');
      localStorage.setItem('theme', 'dark');
    } else {
      document.documentElement.classList.remove('dark');
      localStorage.setItem('theme', 'light');
    }
  }, [dark]);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const patientNavigation = [
    { name: 'Dashboard', href: '/', icon: LayoutDashboard },
    { name: 'Start Exercise', href: '/exercises', icon: Dumbbell },
    { name: 'My Progress', href: '/progress', icon: BarChart3 },
    { name: 'Reports', href: '/reports', icon: FileText },
  ];

  const therapistNavigation = [
    { name: 'Patients', href: '/therapist/dashboard', icon: LayoutDashboard },
    { name: 'Reports', href: '/reports', icon: FileText },
  ];

  const navItems = user?.role === 'therapist' ? therapistNavigation : patientNavigation;

  return (
    <div className="min-h-screen bg-samarth-bg dark:bg-slate-950 flex transition-colors duration-200">
      
      {/* Mobile Navbar */}
      <div className="lg:hidden fixed top-0 left-0 right-0 h-16 bg-white/80 dark:bg-slate-900/80 backdrop-blur-md border-b border-slate-200 dark:border-slate-800 flex items-center justify-between px-6 z-50">
        <div className="flex items-center gap-2">
          <img src="/logo.jpeg" alt="Samarth" className="w-7 h-7 rounded-full object-cover" />
          <span className="font-display font-extrabold text-lg text-brand">
            Samarth
          </span>
        </div>
        <button
          onClick={() => setSidebarOpen(!sidebarOpen)}
          className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-300"
        >
          {sidebarOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
        </button>
      </div>

      {/* Sidebar Overlay (Mobile) */}
      {sidebarOpen && (
        <div
          className="lg:hidden fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-40"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar Navigation */}
      <aside
        className={`fixed lg:sticky top-0 bottom-0 left-0 w-64 bg-white/95 dark:bg-slate-900/95 border-r border-slate-200 dark:border-slate-800/80 flex flex-col p-6 z-40 transition-transform duration-300 lg:translate-x-0 ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        } h-screen`}
      >
        {/* Branding */}
        <div className="flex items-center gap-2.5 mb-8">
          <img src="/logo.jpeg" alt="Samarth" className="w-9 h-9 rounded-full object-cover flex-shrink-0" />
          <div>
            <h1 className="font-display font-black text-xl text-brand">
              Samarth
            </h1>
            <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-widest leading-none mt-1">
              AI Physiotherapy
            </p>
          </div>
        </div>

        {/* Navigation items */}
        <nav className="flex-1 space-y-1.5">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.href;
            return (
              <Link
                key={item.name}
                to={item.href}
                onClick={() => setSidebarOpen(false)}
                className={`flex items-center gap-3.5 px-4 py-3 rounded-xl text-sm font-semibold transition-all ${
                  isActive
                    ? 'bg-brand text-white shadow-[0_4px_12px_0_rgba(42,91,196,0.2)]'
                    : 'text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800/60 hover:text-slate-900 dark:hover:text-slate-200'
                }`}
              >
                <Icon className={`w-5 h-5 ${isActive ? 'text-white' : 'text-slate-400 dark:text-slate-500'}`} />
                {item.name}
              </Link>
            );
          })}
        </nav>

        {/* Sidebar Footer */}
        <div className="border-t border-slate-200 dark:border-slate-800/80 pt-5 space-y-4">
          {/* User profile */}
          <div className="flex items-center gap-3 px-2">
            {user?.avatar_url ? (
              <img src={user.avatar_url} alt="avatar" className="w-10 h-10 rounded-full object-cover border-2 border-brand/20" />
            ) : (
              <div className="w-10 h-10 rounded-full bg-brand-50 dark:bg-brand-900/30 text-brand dark:text-brand-100 flex items-center justify-center font-bold text-sm">
                <UserIcon className="w-4 h-4" />
              </div>
            )}
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-slate-800 dark:text-slate-200 truncate leading-snug">
                {user?.full_name}
              </p>
              <p className="text-xs text-slate-400 dark:text-slate-500 capitalize truncate">
                {user?.role}
              </p>
            </div>
          </div>

          {/* Logout button */}
          <button
            onClick={handleLogout}
            className="w-full flex items-center justify-center gap-2 p-2.5 rounded-xl border border-red-200 dark:border-red-900/30 bg-red-50/50 dark:bg-red-950/20 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/40 transition-colors"
            title="Log out"
            id="logout-btn"
          >
            <LogOut className="w-4 h-4" />
            <span className="text-xs font-semibold">Log out</span>
          </button>
        </div>
      </aside>

      {/* Main Workspace Area */}
      <main className="flex-1 flex flex-col min-w-0 pt-16 lg:pt-0">
        <div className="flex-1 p-6 lg:p-10 max-w-7xl w-full mx-auto">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
