import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Activity, ArrowLeft, ArrowRight, Calendar, Clock,
  Target, Trophy, Search, Filter, ChevronDown, Trash2
} from 'lucide-react';
import { sessionApi } from '@/api';
import type { Session } from '@/types';

type FilterStatus = 'all' | 'completed' | 'in_progress';
type SortBy = 'newest' | 'oldest' | 'score_high' | 'score_low' | 'reps_high';

export default function AllSessionsPage() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterStatus, setFilterStatus] = useState<FilterStatus>('all');
  const [sortBy, setSortBy] = useState<SortBy>('newest');
  const [searchQuery, setSearchQuery] = useState('');
  const [showFilters, setShowFilters] = useState(false);

  const handleDeleteSession = async (e: React.MouseEvent, sessionId: string) => {
    e.preventDefault();
    e.stopPropagation();
    if (!window.confirm("Are you sure you want to delete this session and all of its data? This action cannot be undone.")) {
      return;
    }
    try {
      await sessionApi.delete(sessionId);
      setSessions(prev => prev.filter(s => s.id !== sessionId));
    } catch (err) {
      console.error("Failed to delete session:", err);
      alert("Failed to delete session. Please try again.");
    }
  };

  useEffect(() => {
    const load = async () => {
      try {
        const data = await sessionApi.list(100, 0);
        setSessions(data);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  // Filter sessions
  const filtered = sessions.filter((s) => {
    if (filterStatus !== 'all' && s.status !== filterStatus) return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      const dateStr = new Date(s.start_time).toLocaleDateString().toLowerCase();
      const statusStr = s.status.toLowerCase();
      if (!dateStr.includes(q) && !statusStr.includes(q)) return false;
    }
    return true;
  });

  // Sort sessions
  const sorted = [...filtered].sort((a, b) => {
    switch (sortBy) {
      case 'newest':
        return new Date(b.start_time).getTime() - new Date(a.start_time).getTime();
      case 'oldest':
        return new Date(a.start_time).getTime() - new Date(b.start_time).getTime();
      case 'score_high':
        return (b.session_score ?? 0) - (a.session_score ?? 0);
      case 'score_low':
        return (a.session_score ?? 0) - (b.session_score ?? 0);
      case 'reps_high':
        return b.total_reps - a.total_reps;
      default:
        return 0;
    }
  });

  // Summary stats
  const completedSessions = sessions.filter(s => s.status === 'completed');
  const totalReps = completedSessions.reduce((a, s) => a + s.total_reps, 0);
  const avgScore = completedSessions.filter(s => s.session_score).length
    ? completedSessions.reduce((a, s) => a + (s.session_score ?? 0), 0) / completedSessions.filter(s => s.session_score).length
    : 0;
  const totalDuration = completedSessions.reduce((a, s) => a + (s.duration_seconds ?? 0), 0);

  const statusConfig: Record<string, { bg: string; text: string; label: string }> = {
    completed: { bg: 'bg-green-50', text: 'text-green-700', label: 'Completed' },
    in_progress: { bg: 'bg-amber-50', text: 'text-amber-700', label: 'Not Completed' },
    abandoned: { bg: 'bg-red-50', text: 'text-red-700', label: 'Abandoned' },
  };

  return (
    <div className="min-h-screen bg-samarth-bg pb-12">
      {/* Header */}
      <div className="bg-white border-b border-slate-200 sticky top-0 z-20">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center gap-4">
            <Link
              to="/dashboard"
              className="flex items-center gap-2 text-slate-500 hover:text-brand transition-colors"
            >
              <ArrowLeft className="w-5 h-5" />
            </Link>
            <div>
              <h1 className="text-xl font-display font-bold text-samarth-text">All Sessions</h1>
              <p className="text-sm text-slate-500">{sessions.length} total sessions</p>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 pt-8 space-y-6">
        {/* Summary Stats */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div className="samarth-card p-5 flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-brand flex items-center justify-center">
              <Calendar className="w-5 h-5 text-white" />
            </div>
            <div>
              <div className="text-2xl font-display font-bold text-samarth-text">{completedSessions.length}</div>
              <div className="text-xs text-slate-500">Completed</div>
            </div>
          </div>
          <div className="samarth-card p-5 flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-accent flex items-center justify-center">
              <Target className="w-5 h-5 text-white" />
            </div>
            <div>
              <div className="text-2xl font-display font-bold text-samarth-text">{totalReps}</div>
              <div className="text-xs text-slate-500">Total Reps</div>
            </div>
          </div>
          <div className="samarth-card p-5 flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-purple-500 flex items-center justify-center">
              <Trophy className="w-5 h-5 text-white" />
            </div>
            <div>
              <div className="text-2xl font-display font-bold text-samarth-text">{(avgScore * 100).toFixed(0)}%</div>
              <div className="text-xs text-slate-500">Avg Score</div>
            </div>
          </div>
          <div className="samarth-card p-5 flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-amber-500 flex items-center justify-center">
              <Clock className="w-5 h-5 text-white" />
            </div>
            <div>
              <div className="text-2xl font-display font-bold text-samarth-text">
                {Math.floor(totalDuration / 3600) > 0
                  ? `${Math.floor(totalDuration / 3600)}h ${Math.floor((totalDuration % 3600) / 60)}m`
                  : `${Math.floor(totalDuration / 60)}m`
                }
              </div>
              <div className="text-xs text-slate-500">Total Time</div>
            </div>
          </div>
        </div>

        {/* Search & Filters Bar */}
        <div className="samarth-card p-4">
          <div className="flex flex-col sm:flex-row gap-3">
            {/* Search */}
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <input
                type="text"
                placeholder="Search by date or status..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="samarth-input pl-10"
                id="session-search-input"
              />
            </div>
            {/* Filter toggle */}
            <button
              onClick={() => setShowFilters(!showFilters)}
              className={`btn-secondary ${showFilters ? 'border-brand text-brand' : ''}`}
              id="toggle-filters-btn"
            >
              <Filter className="w-4 h-4" />
              Filters
              <ChevronDown className={`w-4 h-4 transition-transform ${showFilters ? 'rotate-180' : ''}`} />
            </button>
          </div>

          {/* Expanded Filters */}
          {showFilters && (
            <div className="mt-4 pt-4 border-t border-slate-100 flex flex-wrap gap-3">
              {/* Status filter */}
              <div>
                <label className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1.5 block">Status</label>
                <div className="flex gap-2">
                  {(['all', 'completed', 'in_progress'] as FilterStatus[]).map((status) => (
                    <button
                      key={status}
                      onClick={() => setFilterStatus(status)}
                      className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                        filterStatus === status
                          ? 'bg-brand text-white shadow-sm'
                          : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                      }`}
                    >
                      {status === 'all' ? 'All' : status === 'in_progress' ? 'Not Completed' : status.charAt(0).toUpperCase() + status.slice(1)}
                    </button>
                  ))}
                </div>
              </div>
              {/* Sort */}
              <div>
                <label className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1.5 block">Sort By</label>
                <select
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value as SortBy)}
                  className="samarth-input text-xs py-1.5 px-3"
                  id="sort-select"
                >
                  <option value="newest">Newest First</option>
                  <option value="oldest">Oldest First</option>
                  <option value="score_high">Highest Score</option>
                  <option value="score_low">Lowest Score</option>
                  <option value="reps_high">Most Reps</option>
                </select>
              </div>
            </div>
          )}
        </div>

        {/* Sessions List */}
        <div className="samarth-card overflow-hidden">
          {loading ? (
            <div className="p-6 space-y-3">
              {[1, 2, 3, 4, 5].map((i) => (
                <div key={i} className="h-20 skeleton rounded-xl" />
              ))}
            </div>
          ) : sorted.length === 0 ? (
            <div className="text-center py-16">
              <Activity className="w-14 h-14 text-slate-300 mx-auto mb-4" />
              <p className="text-lg font-semibold text-slate-500">No sessions found</p>
              <p className="text-slate-400 text-sm mt-1">
                {filterStatus !== 'all' || searchQuery
                  ? 'Try adjusting your filters or search query'
                  : 'Start your first session to see results here'}
              </p>
              {filterStatus === 'all' && !searchQuery && (
                <Link to="/exercises" className="btn-primary text-sm mt-4 inline-flex">
                  Begin First Session
                </Link>
              )}
            </div>
          ) : (
            <div className="divide-y divide-slate-100">
              {sorted.map((session, index) => {
                const config = statusConfig[session.status] || statusConfig.completed;
                const date = new Date(session.start_time);
                const durationMin = Math.floor((session.duration_seconds ?? 0) / 60);
                const durationSec = Math.round((session.duration_seconds ?? 0) % 60);

                return (
                  <Link
                    key={session.id}
                    to={`/session/summary/${session.id}`}
                    className="flex items-center gap-4 p-5 hover:bg-brand-50/30 transition-all group"
                    style={{ animationDelay: `${index * 30}ms` }}
                  >
                    {/* Session number / status icon */}
                    <div className={`w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0 ${
                      session.status === 'completed' ? 'bg-green-100' :
                      session.status === 'in_progress' ? 'bg-amber-100' : 'bg-red-100'
                    }`}>
                      <Activity className={`w-5 h-5 ${
                        session.status === 'completed' ? 'text-green-600' :
                        session.status === 'in_progress' ? 'text-amber-600' : 'text-red-600'
                      }`} />
                    </div>

                    {/* Session info */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-0.5">
                        <span className="font-semibold text-samarth-text text-sm">
                          Session — {date.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' })}
                        </span>
                      </div>
                      <div className="flex items-center gap-4 text-xs text-slate-400">
                        <span className="flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          {date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}
                        </span>
                        <span className="flex items-center gap-1">
                          <Target className="w-3 h-3" />
                          {session.total_reps} reps
                        </span>
                        <span>
                          {durationMin}m {durationSec}s
                        </span>
                        {session.session_score != null && (
                          <span className="flex items-center gap-1">
                            <Trophy className="w-3 h-3" />
                            {(session.session_score * 100).toFixed(0)}% score
                          </span>
                        )}
                      </div>
                    </div>

                    {/* ROM info */}
                    <div className="hidden sm:flex items-center gap-4 text-xs text-slate-500">
                      <div className="text-center">
                        <div className="font-bold text-samarth-text">{session.avg_left_rom.toFixed(1)}°</div>
                        <div className="text-slate-400">L ROM</div>
                      </div>
                      <div className="text-center">
                        <div className="font-bold text-samarth-text">{session.avg_right_rom.toFixed(1)}°</div>
                        <div className="text-slate-400">R ROM</div>
                      </div>
                    </div>

                    {/* Status badge + arrow */}
                    <div className="flex items-center gap-3">
                      <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold border ${
                        session.status === 'completed' ? 'bg-green-50 text-green-700 border-green-200' :
                        session.status === 'in_progress' ? 'bg-amber-50 text-amber-700 border-amber-200' :
                        'bg-red-50 text-red-700 border-red-200'
                      }`}>
                        {config.label}
                      </span>
                      <button
                        onClick={(e) => handleDeleteSession(e, session.id)}
                        className="p-1.5 text-slate-400 hover:text-red-600 rounded-lg hover:bg-red-50/50 transition-colors z-10"
                        title="Delete Session"
                        id={`delete-btn-${session.id}`}
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                      <ArrowRight className="w-4 h-4 text-slate-300 group-hover:text-brand transition-colors" />
                    </div>
                  </Link>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
