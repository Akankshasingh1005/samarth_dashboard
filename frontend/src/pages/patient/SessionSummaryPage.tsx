import { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  Trophy, ArrowLeft, TrendingUp, TrendingDown, Minus,
  Target, Activity, BarChart3, ChevronRight,
  CheckCircle2, XCircle, Repeat, Clock, Ruler, Scale,
  Maximize2, Zap, Hourglass, AlertTriangle, GitCompare, UserCircle
} from 'lucide-react';
import { sessionApi } from '@/api';
import type { Session, PS2SessionResult } from '@/types';

const ERROR_FLAG_CONFIG = {
  insufficient_ROM: { label: 'Insufficient ROM', icon: Maximize2, desc: 'Range of motion was below target' },
  too_fast: { label: 'Too Fast', icon: Zap, desc: 'Movement speed exceeded safe limit' },
  too_slow: { label: 'Too Slow', icon: Hourglass, desc: 'Movement speed was below recommended' },
  knee_valgus: { label: 'Knee Valgus', icon: AlertTriangle, desc: 'Inward knee collapse detected' },
  asymmetric: { label: 'Asymmetric', icon: GitCompare, desc: 'Bilateral imbalance present' },
  trunk_comp: { label: 'Trunk Compensation', icon: UserCircle, desc: 'Excessive trunk lean/tilt' },
};

function ScoreMeter({ score }: { score: number }) {
  const pct = score * 100;
  const color = pct >= 80 ? '#22C55E' : pct >= 60 ? '#F59E0B' : '#EF4444';
  const label = pct >= 80 ? 'Excellent' : pct >= 60 ? 'Good' : 'Needs Work';
  return (
    <div className="relative flex flex-col items-center">
      <svg viewBox="0 0 120 70" className="w-48">
        <path d="M10,60 A50,50 0 0,1 110,60" fill="none" stroke="#E2E8F0" strokeWidth="10" strokeLinecap="round" />
        <path
          d="M10,60 A50,50 0 0,1 110,60"
          fill="none"
          stroke={color}
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={`${(pct / 100) * 157} 157`}
          style={{ transition: 'stroke-dasharray 1s ease' }}
        />
        <text x="60" y="58" textAnchor="middle" fill={color} fontSize="20" fontWeight="700">
          {pct.toFixed(0)}%
        </text>
      </svg>
      <span className="text-sm font-semibold mt-1" style={{ color }}>{label}</span>
    </div>
  );
}

export default function SessionSummaryPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const [session, setSession] = useState<Session | null>(null);
  const [ps2Result, setPs2Result] = useState<PS2SessionResult | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      if (!sessionId) return;
      try {
        const [sess] = await Promise.all([sessionApi.get(sessionId)]);
        setSession(sess);
        // Poll for PS2 results (may still be processing)
        try {
          const ps2 = await sessionApi.getPS2Results(sessionId);
          setPs2Result(ps2);
        } catch {}
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [sessionId]);

  const trend = session?.quality_trend ?? 'stable';
  const trendIcon = trend === 'improving' ? TrendingUp : trend === 'declining' ? TrendingDown : Minus;
  const TrendIcon = trendIcon;
  const trendColor = trend === 'improving' ? 'text-green-600' : trend === 'declining' ? 'text-red-600' : 'text-amber-600';

  if (loading) {
    return (
      <div className="min-h-screen bg-samarth-bg flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 border-4 border-brand border-t-transparent rounded-full animate-spin" />
          <p className="text-slate-500">Loading session results...</p>
        </div>
      </div>
    );
  }

  const errorSummary = ps2Result?.rep_results.reduce(
    (acc, rep) => {
      Object.entries(rep.error_flags).forEach(([key, val]) => {
        if (val === 1) acc[key as keyof typeof acc] = (acc[key as keyof typeof acc] ?? 0) + 1;
      });
      return acc;
    },
    {} as Record<string, number>
  );

  return (
    <div className="min-h-screen bg-samarth-bg pb-12">
      {/* Header */}
      <div className="bg-white border-b border-slate-200 sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <button onClick={() => navigate('/dashboard')} className="flex items-center gap-2 text-slate-500 hover:text-slate-800 transition-colors">
            <ArrowLeft className="w-5 h-5" />
            <span className="font-medium">Back to Dashboard</span>
          </button>
          <div className="flex items-center gap-3">
            <Link to={`/analytics`} className="btn-secondary text-sm px-4 py-2">
              <BarChart3 className="w-4 h-4" /> View Analytics
            </Link>
          </div>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-6 pt-8 space-y-6">
        {/* Hero card */}
        <div className="samarth-card p-8">
          <div className="flex flex-col lg:flex-row items-center gap-8">
            <div className="flex-shrink-0">
              <ScoreMeter score={session?.session_score ?? ps2Result?.overall_session_score ?? 0} />
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-3 mb-2">
                <Trophy className="w-6 h-6 text-amber-500" />
                <h1 className="text-2xl font-display font-bold text-samarth-text">Session Complete!</h1>
              </div>
              <p className="text-slate-500 mb-6">
                {new Date(session?.start_time ?? '').toLocaleDateString('en-IN', {
                  weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
                })}
              </p>

              {/* Stats row */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                {[
                  { label: 'Total Reps', value: session?.total_reps ?? 0, Icon: Repeat },
                  { label: 'Duration', value: `${Math.round((session?.duration_seconds ?? 0) / 60)}m`, Icon: Clock },
                  { label: 'Left ROM', value: `${(session?.avg_left_rom ?? 0).toFixed(1)}°`, Icon: Ruler },
                  { label: 'Symmetry', value: `${(session?.symmetry_score ?? 0).toFixed(1)}%`, Icon: Scale },
                ].map((stat) => (
                  <div key={stat.label} className="text-center p-4 bg-slate-50 rounded-xl">
                    <div className="flex justify-center mb-1"><stat.Icon className="w-5 h-5 text-brand" /></div>
                    <div className="text-xl font-bold text-samarth-text">{stat.value}</div>
                    <div className="text-xs text-slate-500">{stat.label}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* Quality Trend */}
            <div className="flex-shrink-0 text-center p-6 rounded-2xl bg-slate-50">
              <TrendIcon className={`w-10 h-10 mx-auto mb-2 ${trendColor}`} />
              <div className={`text-lg font-bold capitalize ${trendColor}`}>{trend}</div>
              <div className="text-xs text-slate-400 mt-1">Quality Trend</div>
              <span className="mt-2 badge-mock">PS2 Mock</span>
            </div>
          </div>
        </div>

        {/* PS2 Error Analysis */}
        {ps2Result && (
          <div className="samarth-card p-6">
            <div className="flex items-center justify-between mb-5">
              <h2 className="font-display font-bold text-samarth-text text-lg">Movement Analysis</h2>
              <span className="badge-mock">PS2 {ps2Result.ps2_mode}</span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-6">
              {Object.entries(ERROR_FLAG_CONFIG).map(([key, config]) => {
                const count = errorSummary?.[key] ?? 0;
                const total = ps2Result.total_reps_analyzed;
                const rate = total > 0 ? count / total : 0;
                const hasIssue = rate > 0.3;
                const FlagIcon = config.icon;
                return (
                  <div
                    key={key}
                    className={`p-4 rounded-xl border transition-all ${hasIssue ? 'border-red-200 bg-red-50' : 'border-green-200 bg-green-50'}`}
                  >
                    <div className="flex items-start justify-between mb-2">
                      <FlagIcon className={`w-4 h-4 ${hasIssue ? 'text-red-500' : 'text-green-600'}`} />
                      {hasIssue
                        ? <XCircle className="w-4 h-4 text-red-500" />
                        : <CheckCircle2 className="w-4 h-4 text-green-500" />}
                    </div>
                    <div className={`font-semibold text-sm ${hasIssue ? 'text-red-800' : 'text-green-800'}`}>
                      {config.label}
                    </div>
                    <div className={`text-xs mt-1 ${hasIssue ? 'text-red-600' : 'text-green-600'}`}>
                      {count > 0 ? `${count}/${total} reps` : 'No errors'}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Recommendations */}
            {ps2Result.recommendations.length > 0 && (
              <div className="bg-brand-50 border border-brand-100 rounded-xl p-5">
                <h3 className="font-semibold text-brand mb-3 flex items-center gap-2">
                  <Target className="w-4 h-4" />
                  Recommendations for Next Session
                </h3>
                <ul className="space-y-2">
                  {ps2Result.recommendations.map((rec, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-slate-700">
                      <ChevronRight className="w-4 h-4 text-brand flex-shrink-0 mt-0.5" />
                      {rec}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {/* Per-Rep Results Table */}
        {ps2Result?.rep_results && ps2Result.rep_results.length > 0 && (
          <div className="samarth-card p-6 overflow-x-auto">
            <h2 className="font-display font-bold text-samarth-text text-lg mb-4">Per-Rep Breakdown</h2>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200">
                  <th className="text-left py-2 px-3 text-slate-500 font-semibold">Rep</th>
                  <th className="text-left py-2 px-3 text-slate-500 font-semibold">Score</th>
                  <th className="text-left py-2 px-3 text-slate-500 font-semibold">Errors</th>
                  <th className="text-left py-2 px-3 text-slate-500 font-semibold">Mode</th>
                </tr>
              </thead>
              <tbody>
                {ps2Result.rep_results.map((rep) => {
                  const errors = Object.entries(rep.error_flags).filter(([_, v]) => v === 1);
                  const score = rep.session.session_score;
                  return (
                    <tr key={rep.rep_id} className="border-b border-slate-50 hover:bg-slate-50 transition-colors">
                      <td className="py-3 px-3 font-semibold text-samarth-text">#{rep.rep_id}</td>
                      <td className="py-3 px-3">
                        <span className={`font-bold ${score >= 0.8 ? 'text-green-600' : score >= 0.6 ? 'text-amber-600' : 'text-red-600'}`}>
                          {(score * 100).toFixed(0)}%
                        </span>
                      </td>
                      <td className="py-3 px-3">
                        {errors.length === 0 ? (
                          <span className="badge-success">Clean</span>
                        ) : (
                          <div className="flex flex-wrap gap-1">
                            {errors.map(([k]) => (
                              <span key={k} className="badge-error text-xs">
                                {(() => { const I = ERROR_FLAG_CONFIG[k as keyof typeof ERROR_FLAG_CONFIG].icon; return <I className="w-3 h-3" />; })()}
                              </span>
                            ))}
                          </div>
                        )}
                      </td>
                      <td className="py-3 px-3 text-slate-400 text-xs">
                        {rep.mode_command.mode_name} ({rep.mode_command.target_torque}Nm)
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Action buttons */}
        <div className="flex gap-4 justify-center flex-wrap">
          <Link to="/exercises" className="btn-primary">
            <Activity className="w-4 h-4" />
            Start Another Session
          </Link>
          <Link to="/analytics" className="btn-secondary">
            <BarChart3 className="w-4 h-4" />
            View Full Analytics
          </Link>
        </div>
      </div>
    </div>
  );
}
