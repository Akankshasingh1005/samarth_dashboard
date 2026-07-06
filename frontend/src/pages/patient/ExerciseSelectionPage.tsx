import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Activity, Clock, Target, Shield, ChevronRight,
  ArrowLeft, Play, Upload, Loader2, Repeat, Ruler, ClipboardList, X as XIcon,
  Dumbbell, Eye
} from 'lucide-react';
import { exerciseApi, sessionApi } from '@/api';
import type { Exercise } from '@/types';
import { toast } from 'sonner';

const CATEGORY_COLORS: Record<string, string> = {
  full_leg: 'bg-brand-50 text-brand border-brand-100',
  knee: 'bg-purple-50 text-purple-700 border-purple-200',
  hip: 'bg-accent-50 text-accent border-accent/30',
  ankle: 'bg-amber-50 text-amber-700 border-amber-200',
};

const CATEGORY_ICONS: Record<string, React.ElementType> = {
  full_leg: Dumbbell,
  knee: Activity,
  hip: Target,
  ankle: Ruler,
};

const API_BASE = 'http://localhost:8000';

function ExerciseCard({ exercise, onSelect }: { exercise: Exercise; onSelect: () => void }) {
  const [imgError, setImgError] = useState(false);
  const CategoryIcon = CATEGORY_ICONS[exercise.category] ?? Activity;
  const gifSrc = exercise.gif_url ? `${API_BASE}${exercise.gif_url}` : null;
  const thumbSrc = exercise.thumbnail_url ? `${API_BASE}${exercise.thumbnail_url}` : null;
  const displaySrc = gifSrc || thumbSrc;

  return (
    <div
      onClick={onSelect}
      className="samarth-card p-5 cursor-pointer exercise-card-hover group"
      id={`exercise-${exercise.slug}`}
    >
      <div className="flex items-start justify-between mb-4">
        <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border ${CATEGORY_COLORS[exercise.category] ?? 'bg-slate-50 text-slate-600 border-slate-200'}`}>
          <CategoryIcon className="w-3 h-3" />
          {exercise.category.replace('_', ' ')}
        </div>
        <span className={`text-xs font-medium px-2 py-1 rounded-lg ${exercise.difficulty === 'beginner' ? 'bg-green-50 text-green-600' : exercise.difficulty === 'intermediate' ? 'bg-amber-50 text-amber-600' : 'bg-red-50 text-red-600'}`}>
          {exercise.difficulty}
        </span>
      </div>

      {/* Exercise GIF/Image preview */}
      <div className="w-full h-40 bg-white border border-slate-100 rounded-xl mb-4 overflow-hidden flex items-center justify-center relative group/img">
        {displaySrc && !imgError ? (
          <>
            <img
              src={displaySrc}
              alt={exercise.name}
              className="w-full h-full object-contain p-2 transition-transform duration-500 group-hover:scale-105"
              onError={() => setImgError(true)}
            />
            <div className="absolute inset-0 bg-black/0 group-hover/img:bg-black/20 transition-all flex items-center justify-center">
              <Eye className="w-6 h-6 text-white opacity-0 group-hover/img:opacity-100 transition-opacity" />
            </div>
          </>
        ) : (
          <div className="flex flex-col items-center gap-2 text-brand/40">
            <CategoryIcon className="w-12 h-12" />
            <span className="text-xs font-medium">Demo Coming Soon</span>
          </div>
        )}
      </div>

      <h3 className="font-display font-bold text-samarth-text text-lg mb-2 group-hover:text-brand transition-colors">
        {exercise.name}
      </h3>
      <p className="text-slate-500 text-sm mb-4 line-clamp-2">{exercise.description}</p>

      <div className="flex items-center gap-4 text-xs text-slate-500 mb-4">
        <span className="flex items-center gap-1"><Target className="w-3 h-3" />{exercise.target_reps} reps</span>
        <span className="flex items-center gap-1"><Clock className="w-3 h-3" />{Math.round(exercise.estimated_duration_seconds / 60)}m</span>
        <span className="flex items-center gap-1"><Activity className="w-3 h-3" />{exercise.target_rom_degrees}° ROM</span>
      </div>

      <button className="w-full btn-primary text-sm group-hover:shadow-[0_4px_14px_0_rgba(13,115,119,0.3)]">
        <Play className="w-4 h-4" />
        Select Exercise
        <ChevronRight className="w-4 h-4" />
      </button>
    </div>
  );
}

function ExerciseDetailModal({ exercise, onClose, onStart }: {
  exercise: Exercise; onClose: () => void; onStart: (mode: 'live' | 'upload') => void;
}) {
  const [starting, setStarting] = useState<'live' | 'upload' | null>(null);
  const [imgError, setImgError] = useState(false);
  const gifSrc = exercise.gif_url ? `${API_BASE}${exercise.gif_url}` : null;

  const handleStart = async (mode: 'live' | 'upload') => {
    setStarting(mode);
    await onStart(mode);
  };

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-end sm:items-center justify-center p-4">
      <div className="bg-white w-full max-w-2xl rounded-3xl shadow-2xl max-h-[90vh] overflow-y-auto">
        <div className="p-6 border-b border-slate-100">
          <div className="flex items-start justify-between">
            <div>
              <h2 className="text-2xl font-display font-bold text-samarth-text">{exercise.name}</h2>
              <p className="text-slate-500 text-sm mt-1">{exercise.category.replace('_', ' ')} · {exercise.difficulty}</p>
            </div>
            <button onClick={onClose} className="w-8 h-8 rounded-xl bg-slate-100 flex items-center justify-center hover:bg-slate-200 transition-colors">
              <XIcon className="w-4 h-4 text-slate-600" />
            </button>
          </div>
        </div>

        <div className="p-6 space-y-6">
          {/* Demo Animation (large) */}
          {gifSrc && !imgError && (
            <div className="w-full aspect-video bg-white border border-slate-100 rounded-2xl overflow-hidden shadow-inner">
              <img
                src={gifSrc}
                alt={`${exercise.name} demonstration`}
                className="w-full h-full object-contain"
                onError={() => setImgError(true)}
              />
            </div>
          )}

          <p className="text-slate-600 leading-relaxed">{exercise.description}</p>

          <div className="grid grid-cols-3 gap-4">
            {[
              { label: 'Target Reps', value: exercise.target_reps, Icon: Repeat },
              { label: 'Target Sets', value: exercise.target_sets, Icon: ClipboardList },
              { label: 'Target ROM', value: `${exercise.target_rom_degrees}°`, Icon: Ruler },
            ].map((stat) => (
              <div key={stat.label} className="text-center p-3 bg-slate-50 rounded-xl">
                <div className="flex justify-center mb-1"><stat.Icon className="w-4 h-4 text-brand" /></div>
                <div className="font-bold text-samarth-text">{stat.value}</div>
                <div className="text-xs text-slate-500">{stat.label}</div>
              </div>
            ))}
          </div>

          {exercise.safety_instructions.length > 0 && (
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-2 font-semibold text-amber-800">
                <Shield className="w-4 h-4" />
                Safety Instructions
              </div>
              <ul className="space-y-1">
                {exercise.safety_instructions.map((inst, i) => (
                  <li key={i} className="text-sm text-amber-700 flex items-start gap-2">
                    <span className="mt-0.5 text-amber-500">&ndash;</span>{inst}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {exercise.contraindications.length > 0 && (
            <div className="bg-red-50 border border-red-200 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-2 font-semibold text-red-800">
                <Shield className="w-4 h-4" />
                Do Not Perform If
              </div>
              <ul className="space-y-1">
                {exercise.contraindications.map((ci, i) => (
                  <li key={i} className="text-sm text-red-700 flex items-start gap-2">
                    <span className="mt-0.5 text-red-400">&ndash;</span>{ci}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <button
              onClick={() => handleStart('live')}
              disabled={!!starting}
              className="btn-primary py-4 flex-col h-auto gap-1"
            >
              {starting === 'live' ? <Loader2 className="w-5 h-5 animate-spin" /> : <Play className="w-5 h-5" />}
              <span>Live Session</span>
              <span className="text-xs opacity-80 font-normal">Camera + Real-time</span>
            </button>
            <button
              onClick={() => handleStart('upload')}
              disabled={!!starting}
              className="btn-secondary py-4 flex-col h-auto gap-1"
            >
              {starting === 'upload' ? <Loader2 className="w-5 h-5 animate-spin" /> : <Upload className="w-5 h-5" />}
              <span>Upload Video</span>
              <span className="text-xs opacity-80 font-normal">Analyze recorded video</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function ExerciseSelectionPage() {
  const navigate = useNavigate();
  const [exercises, setExercises] = useState<Exercise[]>([]);
  const [selected, setSelected] = useState<Exercise | null>(null);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    const load = async () => {
      try {
        const exs = await exerciseApi.list();
        if (exs.length === 0) {
          // Auto-seed on first run
          await exerciseApi.seed().catch(() => {});
          const reloaded = await exerciseApi.list();
          setExercises(reloaded);
        } else {
          setExercises(exs);
        }
      } catch {
        toast.error('Failed to load exercises');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const handleStart = async (mode: 'live' | 'upload') => {
    if (!selected || creating) return;
    setCreating(true);
    try {
      const session = await sessionApi.create(selected.id, mode);
      if (mode === 'live') {
        navigate(`/camera/${selected.id}/${session.id}`);
      } else {
        navigate(`/session/upload/${session.id}/${selected.id}`);
      }
    } catch {
      toast.error('Failed to create session. Please try again.');
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="min-h-screen bg-samarth-bg pb-12">
      <div className="bg-white border-b border-slate-200">
        <div className="max-w-7xl mx-auto px-6 py-5">
          <button onClick={() => navigate('/dashboard')} className="flex items-center gap-2 text-slate-400 hover:text-slate-700 mb-4 transition-colors">
            <ArrowLeft className="w-4 h-4" />
            <span className="text-sm">Dashboard</span>
          </button>
          <h1 className="text-2xl font-display font-bold text-samarth-text">Select Exercise</h1>
          <p className="text-slate-500 mt-1">Choose an exercise to begin your session.</p>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 pt-8">
        {loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="h-80 skeleton rounded-2xl" />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {exercises.map((ex) => (
              <ExerciseCard key={ex.id} exercise={ex} onSelect={() => setSelected(ex)} />
            ))}
          </div>
        )}
      </div>

      {selected && (
        <ExerciseDetailModal
          exercise={selected}
          onClose={() => setSelected(null)}
          onStart={handleStart}
        />
      )}
    </div>
  );
}
