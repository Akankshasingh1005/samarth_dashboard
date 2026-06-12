import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Activity, Calendar, Trophy, ArrowRight,
  Plus, Repeat, Target, Bell, BarChart3, Zap
} from 'lucide-react';
import { useAuthStore } from '@/stores/authStore';
import { sessionApi, notificationApi } from '@/api';
import type { Session, Notification } from '@/types';

function StatCard({ label, value, subtitle, icon: Icon, color }: {
  label: string; value: string | number; subtitle?: string;
  icon: React.ElementType; color: string;
}) {
  return (
    <div className="stat-card">
      <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${color}`}>
        <Icon className="w-5 h-5 text-white" />
      </div>
      <div>
        <div className="text-2xl font-display font-bold text-samarth-text">{value}</div>
        <div className="text-sm font-semibold text-slate-600">{label}</div>
        {subtitle && <div className="text-xs text-slate-400 mt-0.5">{subtitle}</div>}
      </div>
    </div>
  );
}

export default function PatientDashboard() {
  const { user } = useAuthStore();
  const [sessions, setSessions] = useState<Session[]>([]);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const [sess, notes] = await Promise.all([
          sessionApi.list(5, 0),
          notificationApi.list(),
        ]);
        setSessions(sess);
        setNotifications(notes.slice(0, 3));
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const completedSessions = sessions.filter(s => s.status === 'completed');
  const totalReps = completedSessions.reduce((a, s) => a + s.total_reps, 0);
  const avgROM = completedSessions.length
    ? completedSessions.reduce((a, s) => a + (s.avg_left_rom + s.avg_right_rom) / 2, 0) / completedSessions.length
    : 0;
  const avgScore = completedSessions.filter(s => s.session_score).length
    ? completedSessions.reduce((a, s) => a + (s.session_score ?? 0), 0) / completedSessions.filter(s => s.session_score).length
    : 0;

  const timeOfDay = () => {
    const h = new Date().getHours();
    if (h < 12) return 'Good morning';
    if (h < 17) return 'Good afternoon';
    return 'Good evening';
  };

  return (
    <div className="min-h-screen bg-samarth-bg pb-12">
      {/* Top nav */}
      <nav className="bg-white border-b border-slate-200 sticky top-0 z-20">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <img src="/logo.jpeg" alt="Samarth" className="w-9 h-9 rounded-full object-cover" />
            <span className="text-xl font-display font-bold text-samarth-text">Samarth</span>
          </div>
          <div className="flex items-center gap-4">
            <Link to="/analytics" className="text-slate-500 hover:text-brand transition-colors">
              <BarChart3 className="w-5 h-5" />
            </Link>
            <div className="relative">
              <Bell className="w-5 h-5 text-slate-500" />
              {notifications.some(n => !n.is_read) && (
                <div className="absolute -top-1 -right-1 w-2 h-2 bg-red-500 rounded-full" />
              )}
            </div>
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 bg-brand rounded-full flex items-center justify-center text-white text-sm font-bold">
                {user?.first_name?.[0] ?? 'U'}
              </div>
              <span className="text-sm font-medium text-slate-700 hidden sm:block">{user?.full_name}</span>
            </div>
          </div>
        </div>
      </nav>

      <div className="max-w-7xl mx-auto px-6 pt-8 space-y-8">
        {/* Welcome hero */}
        <div className="relative overflow-hidden rounded-2xl bg-brand p-8 text-white">
          <div className="absolute top-0 right-0 w-64 h-64 bg-white/5 rounded-full -translate-y-1/2 translate-x-1/2" />
          <div className="relative z-10">
            <p className="text-white/70 font-medium mb-1">{timeOfDay()},</p>
            <h1 className="text-3xl font-display font-bold mb-3">{user?.first_name ?? 'Patient'}</h1>
            <p className="text-white/70 mb-6 max-w-md">
              Ready for today's session? Your consistency is the key to recovery.
            </p>
            <Link to="/exercises" className="inline-flex items-center gap-2 bg-white text-brand px-6 py-3 rounded-xl font-bold text-sm hover:bg-[#E2E8F0] transition-all">
              <Plus className="w-4 h-4" />
              Start New Session
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </div>

        {/* Stats grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <StatCard label="Sessions" value={completedSessions.length} subtitle="Completed" icon={Calendar} color="bg-brand" />
          <StatCard label="Total Reps" value={totalReps} subtitle="All sessions" icon={Repeat} color="bg-accent" />
          <StatCard label="Avg ROM" value={`${avgROM.toFixed(1)}°`} subtitle="Left + Right" icon={Target} color="bg-purple-500" />
          <StatCard label="Avg Score" value={`${(avgScore * 100).toFixed(0)}%`} subtitle="Quality" icon={Trophy} color="bg-amber-500" />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Recent sessions */}
          <div className="lg:col-span-2 samarth-card p-6">
            <div className="flex items-center justify-between mb-5">
              <h2 className="font-display font-bold text-samarth-text">Recent Sessions</h2>
              <Link to="/sessions" className="text-sm text-brand hover:underline font-medium">View all</Link>
            </div>

            {loading ? (
              <div className="space-y-3">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="h-16 skeleton rounded-xl" />
                ))}
              </div>
            ) : sessions.length === 0 ? (
              <div className="text-center py-12">
                <Activity className="w-12 h-12 text-slate-300 mx-auto mb-3" />
                <p className="text-slate-500 font-medium">No sessions yet</p>
                <p className="text-slate-400 text-sm mb-4">Start your first session to see results here</p>
                <Link to="/exercises" className="btn-primary text-sm">Begin First Session</Link>
              </div>
            ) : (
              <div className="space-y-3">
                {sessions.map((session) => (
                  <Link
                    key={session.id}
                    to={`/session/summary/${session.id}`}
                    className="flex items-center gap-4 p-4 rounded-xl border border-slate-100 hover:border-brand/30 hover:bg-brand-50/30 transition-all group"
                  >
                    <div className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0
                      ${session.status === 'completed' ? 'bg-green-100' : 'bg-amber-100'}`}>
                      <Activity className={`w-5 h-5 ${session.status === 'completed' ? 'text-green-600' : 'text-amber-600'}`} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="font-semibold text-samarth-text text-sm truncate">
                        Session {new Date(session.start_time).toLocaleDateString()}
                      </div>
                      <div className="text-xs text-slate-400">
                        {session.total_reps} reps · {Math.round((session.duration_seconds ?? 0) / 60)}m
                        {session.session_score && ` · ${(session.session_score * 100).toFixed(0)}% score`}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={session.status === 'completed' ? 'badge-success' : 'badge-warning'}>
                        {session.status}
                      </span>
                      <ArrowRight className="w-4 h-4 text-slate-300 group-hover:text-brand transition-colors" />
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </div>

          {/* Side widgets */}
          <div className="space-y-4">
            {/* PS3 sensor widget */}
            <div className="integration-stub">
              <div className="flex items-center gap-2 mb-3">
                <Zap className="w-5 h-5 text-slate-400" />
                <h3 className="font-display font-semibold text-slate-600">PS3 Sensor</h3>
                <span className="badge-mock">Simulated</span>
              </div>
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div className="bg-white/60 rounded-xl p-3 text-center">
                  <div className="font-bold text-slate-700">--</div>
                  <div className="text-slate-400">Heart Rate</div>
                </div>
                <div className="bg-white/60 rounded-xl p-3 text-center">
                  <div className="font-bold text-slate-700">0%</div>
                  <div className="text-slate-400">Battery</div>
                </div>
              </div>
              <p className="text-xs text-slate-400 mt-3">Connect PS3 wearable sensor to see live biometric data.</p>
            </div>

            {/* Quick actions */}
            <div className="samarth-card p-5">
              <h3 className="font-display font-bold text-samarth-text mb-4">Quick Actions</h3>
              <div className="space-y-2">
                <Link to="/exercises" className="flex items-center gap-3 p-3 rounded-xl hover:bg-brand-50 transition-colors group">
                  <div className="w-8 h-8 bg-brand-50 rounded-lg flex items-center justify-center group-hover:bg-brand/20">
                    <Plus className="w-4 h-4 text-brand" />
                  </div>
                  <span className="text-sm font-medium text-slate-700">New Session</span>
                  <ArrowRight className="w-4 h-4 text-slate-300 ml-auto" />
                </Link>
                <Link to="/analytics" className="flex items-center gap-3 p-3 rounded-xl hover:bg-brand-50 transition-colors group">
                  <div className="w-8 h-8 bg-brand-50 rounded-lg flex items-center justify-center group-hover:bg-brand/20">
                    <BarChart3 className="w-4 h-4 text-brand" />
                  </div>
                  <span className="text-sm font-medium text-slate-700">View Analytics</span>
                  <ArrowRight className="w-4 h-4 text-slate-300 ml-auto" />
                </Link>
                <Link to="/reports" className="flex items-center gap-3 p-3 rounded-xl hover:bg-brand-50 transition-colors group">
                  <div className="w-8 h-8 bg-brand-50 rounded-lg flex items-center justify-center group-hover:bg-brand/20">
                    <Trophy className="w-4 h-4 text-brand" />
                  </div>
                  <span className="text-sm font-medium text-slate-700">Download Report</span>
                  <ArrowRight className="w-4 h-4 text-slate-300 ml-auto" />
                </Link>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
