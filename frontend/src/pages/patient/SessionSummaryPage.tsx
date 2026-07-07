import { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  Trophy, ArrowLeft, TrendingUp, TrendingDown, Minus,
  Target, Activity, BarChart3, ChevronRight,
  CheckCircle2, XCircle, Repeat, Clock, Ruler, Scale,
  Maximize2, Zap, Hourglass, AlertTriangle, GitCompare, UserCircle,
  MessageCircle, Film, ThumbsUp, AlertCircle
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

function ScoreMeter({ score, totalReps }: { score: number; totalReps?: number }) {
  const pct = score * 100;
  const color = totalReps === 0 ? '#94A3B8' : pct >= 80 ? '#22C55E' : pct >= 60 ? '#F59E0B' : '#EF4444';
  const label = totalReps === 0 ? 'No Data' : pct >= 80 ? 'Excellent' : pct >= 60 ? 'Good' : 'Needs Work';
  const circumference = 157;
  return (
    <div className="relative flex flex-col items-center animate-fade-in">
      <svg viewBox="0 0 120 70" className="w-48">
        <path d="M10,60 A50,50 0 0,1 110,60" fill="none" stroke="#E2E8F0" strokeWidth="10" strokeLinecap="round" />
        <path
          d="M10,60 A50,50 0 0,1 110,60"
          fill="none"
          stroke={color}
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={`${totalReps === 0 ? 0 : (pct / 100) * circumference} ${circumference}`}
          style={{ transition: 'stroke-dasharray 1s ease' }}
        />
        <text x="60" y="58" textAnchor="middle" fill={color} fontSize="20" fontWeight="700">
          {totalReps === 0 ? '—' : `${pct.toFixed(0)}%`}
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
    let cancelled = false;
    let retries = 0;
    const MAX_RETRIES = 8;
    const RETRY_INTERVAL_MS = 1500;

    const load = async () => {
      if (!sessionId) return;
      try {
        const sess = await sessionApi.get(sessionId);
        if (!cancelled) setSession(sess);

        // Check if the session has meaningful data from the WS handler.
        // The WS handler sets total_reps, session_score, and ps1_processed
        // via an atomic $set. If these haven't landed yet, retry.
        const hasData = (sess?.total_reps ?? 0) > 0 && sess?.ps1_processed;
        if (!hasData && retries < MAX_RETRIES) {
          retries++;
          setTimeout(load, RETRY_INTERVAL_MS);
          return;
        }

        // Load PS2 results independently — may not be available yet
        // even if session data is. Retry a few times if needed.
        let ps2Loaded = false;
        for (let ps2Try = 0; ps2Try < 3 && !ps2Loaded && !cancelled; ps2Try++) {
          try {
            const ps2 = await sessionApi.getPS2Results(sessionId);
            if (!cancelled) {
              setPs2Result(ps2);
              ps2Loaded = true;
            }
          } catch {
            // PS2 results not ready yet — wait and retry
            if (ps2Try < 2) {
              await new Promise(r => setTimeout(r, 1000));
            }
          }
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    load();
    return () => { cancelled = true; };
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
    <div className="min-h-screen bg-samarth-bg pb-12 overflow-y-auto">
      {/* Header */}
      <div className="bg-white border-b border-slate-200 sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <button onClick={() => navigate('/dashboard')} className="flex items-center gap-2 text-slate-500 hover:text-slate-800 transition-colors">
            <ArrowLeft className="w-5 h-5" />
            <span className="font-medium">Back to Dashboard</span>
          </button>
          <div className="flex items-center gap-3">
            <Link to={`/progress`} className="btn-secondary text-sm px-4 py-2">
              <BarChart3 className="w-4 h-4" /> View Analytics
            </Link>
          </div>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-6 pt-8 space-y-6">
        {/* Hero card */}
        <div className="samarth-card p-8 animate-slide-up">
          <div className="flex flex-col lg:flex-row items-center gap-8">
            <div className="flex-shrink-0">
              <ScoreMeter
                score={session?.session_score ?? ps2Result?.overall_session_score ?? 0}
                totalReps={session?.total_reps ?? ps2Result?.total_reps_analyzed ?? 0}
              />
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
                  { label: 'Duration', value: `${Math.floor((session?.duration_seconds ?? 0) / 60)}m ${Math.round((session?.duration_seconds ?? 0) % 60)}s`, Icon: Clock },
                  { label: 'Left ROM', value: `${(session?.avg_left_rom ?? 0).toFixed(1)}°`, Icon: Ruler },
                  { label: 'Symmetry', value: `${(session?.symmetry_score ?? 0).toFixed(1)}%`, Icon: Scale },
                ].map((stat) => (
                  <div key={stat.label} className="text-center p-4 bg-brand-50 rounded-xl">
                    <div className="flex justify-center mb-1"><stat.Icon className="w-5 h-5 text-brand" /></div>
                    <div className="text-xl font-bold text-samarth-text">{stat.value}</div>
                    <div className="text-xs text-slate-500">{stat.label}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* Quality Trend */}
            <div className="flex-shrink-0 text-center p-6 rounded-2xl bg-brand-50 border border-brand-100">
              <TrendIcon className={`w-10 h-10 mx-auto mb-2 ${trendColor}`} />
              <div className={`text-lg font-bold capitalize ${trendColor}`}>{trend}</div>
              <div className="text-xs text-slate-400 mt-1">Quality Trend</div>
              <span className={`mt-2 inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${ps2Result?.ps2_mode === 'real' ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-500'}`}>
                {ps2Result?.ps2_mode === 'real' ? 'AI Model' : 'Analysis unavailable'}
              </span>
            </div>
          </div>
        </div>

        {/* Human-Readable Rehabilitation Feedback */}
        {ps2Result && (
          <div className="samarth-card p-6 animate-slide-up">
            <div className="flex items-center gap-3 mb-5">
              <div className="w-10 h-10 bg-brand-50 rounded-xl flex items-center justify-center">
                <MessageCircle className="w-5 h-5 text-brand" />
              </div>
              <div>
                <h2 className="font-display font-bold text-samarth-text text-lg">Your Rehabilitation Report</h2>
                <p className="text-sm text-slate-500">AI-powered feedback on your exercise performance</p>
              </div>
            </div>

            {(() => {
              const score = (session?.session_score ?? ps2Result.overall_session_score) * 100;
              const totalReps = ps2Result.total_reps_analyzed;
              const errors = ps2Result.rep_results.reduce((acc, rep) => {
                Object.entries(rep.error_flags).forEach(([key, val]) => {
                  if (val === 1) acc[key] = (acc[key] ?? 0) + 1;
                });
                return acc;
              }, {} as Record<string, number>);
              const issueKeys = totalReps > 0 ? Object.entries(errors).filter(([_, count]) => count / totalReps > 0.3).map(([k]) => k) : [];
              const cleanKeys = totalReps > 0 ? Object.keys(ERROR_FLAG_CONFIG).filter(k => !issueKeys.includes(k)) : [];

              const qualityLabel = totalReps === 0 ? 'No Repetitions Detected' : score >= 80 ? 'Excellent' : score >= 60 ? 'Good' : score >= 40 ? 'Fair' : 'Needs Improvement';
              const qualityColor = totalReps === 0 ? 'text-slate-700 bg-slate-50 border-slate-200' : score >= 80 ? 'text-green-700 bg-green-50 border-green-200' : score >= 60 ? 'text-amber-700 bg-amber-50 border-amber-200' : 'text-red-700 bg-red-50 border-red-200';

              const issueExplanations: Record<string, string> = {
                insufficient_ROM: 'Your joints did not reach the full target range of motion during some repetitions. Try to extend through the complete movement arc while maintaining control.',
                too_fast: 'Some movements were performed too quickly, which can reduce muscle engagement and increase injury risk. Focus on slow, controlled movements - count to 3 on each phase.',
                too_slow: 'Your movement tempo was slower than recommended. While controlled movement is good, aim for a steady rhythm to maintain muscle activation throughout the set.',
                knee_valgus: 'Your knees collapsed inward during some reps (valgus). Focus on pushing your knees outward in line with your toes. Strengthening your hip abductors can help.',
                asymmetric: 'There was a noticeable difference between your left and right sides. Try to distribute weight evenly and perform the movement symmetrically.',
                trunk_comp: 'Excessive trunk lean or tilt was detected. Keep your core engaged and your torso upright throughout the exercise to prevent compensation patterns.',
              };

              const strengthMessages: string[] = [];
              if (totalReps > 0) {
                if (cleanKeys.includes('knee_valgus')) strengthMessages.push('Good knee alignment - your knees tracked well over your toes.');
                if (cleanKeys.includes('asymmetric')) strengthMessages.push('Excellent bilateral symmetry - both sides are working evenly.');
                if (cleanKeys.includes('insufficient_ROM')) strengthMessages.push('Great range of motion - you\'re reaching the target movement arc.');
                if (cleanKeys.includes('trunk_comp')) strengthMessages.push('Stable trunk posture - your core engagement is solid.');
                if (cleanKeys.includes('too_fast') && cleanKeys.includes('too_slow')) strengthMessages.push('Good movement tempo - your pacing is within the recommended range.');
                if (strengthMessages.length === 0) strengthMessages.push('You completed all repetitions - keep practicing for improvement!');
              }

              return (
                <div className="space-y-5">
                  {/* Quality Badge */}
                  <div className={`inline-flex items-center gap-2 px-4 py-2 rounded-xl border font-semibold text-sm ${qualityColor}`}>
                    {totalReps === 0 ? <AlertCircle className="w-4 h-4 text-slate-500" /> : score >= 60 ? <ThumbsUp className="w-4 h-4" /> : <AlertCircle className="w-4 h-4" />}
                    Exercise Quality: {qualityLabel} {totalReps > 0 && `(${score.toFixed(0)}%)`}
                  </div>

                  {/* Strengths */}
                  {strengthMessages.length > 0 && (
                    <div className="bg-green-50 border border-green-100 rounded-xl p-4">
                      <h3 className="font-semibold text-green-800 mb-2 flex items-center gap-2">
                        <CheckCircle2 className="w-4 h-4" />
                        What You Did Well
                      </h3>
                      <ul className="space-y-1.5">
                        {strengthMessages.map((msg, i) => (
                          <li key={i} className="text-sm text-green-700 flex items-start gap-2">
                            <span className="mt-0.5 text-green-500">✓</span>{msg}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Issues Detected */}
                  {issueKeys.length > 0 && (
                    <div className="bg-amber-50 border border-amber-100 rounded-xl p-4">
                      <h3 className="font-semibold text-amber-800 mb-2 flex items-center gap-2">
                        <AlertTriangle className="w-4 h-4" />
                        Areas for Improvement
                      </h3>
                      <div className="space-y-3">
                        {issueKeys.map((key) => {
                          const config = ERROR_FLAG_CONFIG[key as keyof typeof ERROR_FLAG_CONFIG];
                          const count = errors[key];
                          return (
                            <div key={key} className="text-sm">
                              <div className="font-semibold text-amber-900 mb-0.5">
                                {config?.label} - detected in {count} of {totalReps} reps
                              </div>
                              <p className="text-amber-700 leading-relaxed">
                                {issueExplanations[key] ?? config?.desc ?? 'An issue was detected during your exercise.'}
                              </p>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {/* Summary narrative */}
                  <p className="text-sm text-slate-600 leading-relaxed">
                    {totalReps === 0
                      ? 'No repetitions were detected or analyzed during this session. Please position your camera correctly and try again.'
                      : issueKeys.length === 0
                      ? `Great job! You completed ${totalReps} repetitions with excellent form. Your movement quality is consistent and your technique is solid. Keep up the good work!`
                      : `You completed ${totalReps} repetitions. Focus on the areas noted above in your next session. Small improvements in technique will significantly enhance your rehabilitation progress.`
                    }
                  </p>
                </div>
              );
            })()}
          </div>
        )}

        {/* Annotated Video */}
        {session?.video_url && (
          <div className="samarth-card p-6 animate-slide-up">
            <div className="flex items-center gap-3 mb-4">
              <Film className="w-5 h-5 text-brand" />
              <h2 className="font-display font-bold text-samarth-text text-lg">Annotated Exercise Video</h2>
            </div>
            <div className="bg-slate-900 rounded-2xl overflow-hidden">
              <video
                src={session.video_url}
                controls
                className="w-full"
                style={{ maxHeight: '500px' }}
                playsInline
              />
            </div>
            <p className="text-xs text-slate-400 mt-2">Video with AI pose overlay showing detected skeleton, joint angles, and repetition markers.</p>
          </div>
        )}

        {/* PS2 Error Analysis */}
        {ps2Result && ps2Result.total_reps_analyzed > 0 && (
          <div className="samarth-card p-6 animate-slide-up">
            <div className="flex items-center justify-between mb-5">
              <h2 className="font-display font-bold text-samarth-text text-lg">Movement Analysis</h2>
              <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold ${ps2Result.ps2_mode === 'real' ? 'bg-green-100 text-green-700 border border-green-200' : 'bg-slate-100 text-slate-500 border border-slate-200'}`}>
                {ps2Result.ps2_mode === 'real' ? 'RehabNet AI Analysis' : 'Analysis unavailable'}
              </span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-6">
              {Object.entries(ERROR_FLAG_CONFIG).map(([key, config]) => {
                const count = errorSummary?.[key] ?? 0;
                const total = ps2Result.total_reps_analyzed;
                const rate = total > 0 ? count / total : 0;
                const hasIssue = rate > 0.3;
                const FlagIcon = config.icon;

                let cardClass = '';
                let statusIcon = null;
                let statusText = '';
                let flagIconColor = '';

                if (total === 0) {
                  cardClass = 'border-slate-200 bg-slate-50 opacity-60';
                  statusIcon = <Minus className="w-4 h-4 text-slate-400" />;
                  statusText = 'No data';
                  flagIconColor = 'text-slate-400';
                } else if (hasIssue) {
                  cardClass = 'border-red-200 bg-red-50';
                  statusIcon = <XCircle className="w-4 h-4 text-red-500" />;
                  statusText = `${count}/${total} reps`;
                  flagIconColor = 'text-red-500';
                } else {
                  cardClass = 'border-green-200 bg-green-50';
                  statusIcon = <CheckCircle2 className="w-4 h-4 text-green-500" />;
                  statusText = 'No errors';
                  flagIconColor = 'text-green-600';
                }

                return (
                  <div
                    key={key}
                    className={`p-4 rounded-xl border transition-all ${cardClass}`}
                  >
                    <div className="flex items-start justify-between mb-2">
                      <FlagIcon className={`w-4 h-4 ${flagIconColor}`} />
                      {statusIcon}
                    </div>
                    <div className={`font-semibold text-sm ${total === 0 ? 'text-slate-500' : hasIssue ? 'text-red-800' : 'text-green-800'}`}>
                      {config.label}
                    </div>
                    <div className={`text-xs mt-1 ${total === 0 ? 'text-slate-400' : hasIssue ? 'text-red-600' : 'text-green-600'}`}>
                      {statusText}
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

        {/* PS3 Exoskeleton Hardware Report */}
        {session?.ps3_connected && (
          <div className="samarth-card p-6 animate-slide-up bg-slate-50/50 border border-slate-100 rounded-2xl">
            <div className="flex items-center justify-between mb-5">
              <div className="flex items-center gap-2">
                <Zap className="w-5 h-5 text-brand" />
                <h2 className="font-display font-bold text-samarth-text text-lg">PS3 Exoskeleton Summary</h2>
              </div>
              <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-brand-50 text-brand border border-brand-100">
                ESP32 Hardware Linked
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              {/* Force stats */}
              <div className="bg-white p-4 rounded-xl border border-slate-100 shadow-sm flex flex-col justify-between">
                <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">
                  Average Foot Force
                </div>
                <div className="flex items-baseline gap-1">
                  <span className="text-2xl font-extrabold text-samarth-text">
                    {(session.ps3_avg_acceleration ?? 0).toFixed(2)}
                  </span>
                  <span className="text-xs text-slate-500 font-medium">Newtons</span>
                </div>
                <p className="text-[11px] text-slate-500 mt-2">
                  Average pressure applied during active stance phases.
                </p>
              </div>

              {/* Peak force stats */}
              <div className="bg-white p-4 rounded-xl border border-slate-100 shadow-sm flex flex-col justify-between">
                <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">
                  Peak Foot Force
                </div>
                <div className="flex items-baseline gap-1">
                  <span className="text-2xl font-extrabold text-brand">
                    {(session.ps3_peak_acceleration ?? 0).toFixed(2)}
                  </span>
                  <span className="text-xs text-slate-500 font-medium">Newtons</span>
                </div>
                <p className="text-[11px] text-slate-500 mt-2">
                  Maximum loading weight detected on the foot rest.
                </p>
              </div>

              {/* Motor commands stats */}
              <div className="bg-white p-4 rounded-xl border border-slate-100 shadow-sm flex flex-col justify-between">
                <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">
                  Actuator Feedback Loop
                </div>
                <div className="flex items-baseline gap-1">
                  <span className="text-2xl font-extrabold text-accent">
                    {session.ps3_commands_sent ?? 0}
                  </span>
                  <span className="text-xs text-slate-500 font-medium">Commands</span>
                </div>
                <p className="text-[11px] text-slate-500 mt-2">
                  Active Mode: <strong className="text-slate-700">{session.ps3_last_mode || 'Standby'}</strong>
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Per-Rep Results Table */}
        {ps2Result?.rep_results && ps2Result.rep_results.length > 0 && (
          <div className="samarth-card p-6 animate-slide-up">
            <h2 className="font-display font-bold text-samarth-text text-lg mb-4">Per-Rep Breakdown</h2>
            <div className="overflow-x-auto max-h-[400px] overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-white">
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
                      <tr key={rep.rep_id} className="border-b border-slate-50 hover:bg-brand-50/30 transition-colors">
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
                              {errors.map(([k]) => {
                                const cfg = ERROR_FLAG_CONFIG[k as keyof typeof ERROR_FLAG_CONFIG];
                                const ErrIcon = cfg.icon;
                                return (
                                  <span key={k} className="badge-error text-xs" title={cfg.label}>
                                    <ErrIcon className="w-3 h-3" />
                                  </span>
                                );
                              })}
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
          </div>
        )}

        {/* Action buttons */}
        <div className="flex gap-4 justify-center flex-wrap py-4">
          <Link to="/exercises" className="btn-primary">
            <Activity className="w-4 h-4" />
            Start Another Session
          </Link>
          <Link to="/progress" className="btn-secondary">
            <BarChart3 className="w-4 h-4" />
            View Full Analytics
          </Link>
        </div>
      </div>
    </div>
  );
}
