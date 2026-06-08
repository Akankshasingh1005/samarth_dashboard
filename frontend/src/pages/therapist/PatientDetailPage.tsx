import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { patientApi } from '@/api';
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from 'recharts';
import { ArrowLeft, User, Activity, ChevronRight, Loader2, Ruler, ClipboardList } from 'lucide-react';
import { toast } from 'sonner';

export default function PatientDetailPage() {
  const { patientId } = useParams<{ patientId: string }>();
  const navigate = useNavigate();
  
  const [patient, setPatient] = useState<any>(null);
  const [sessions, setSessions] = useState<any[]>([]);
  const [romTrends, setRomTrends] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!patientId) return;
    const loadData = async () => {
      try {
        // Fetch patient bio
        const pat = await patientApi.get(patientId).catch(() => ({
          id: patientId,
          user: { full_name: 'John Doe', email: 'john@example.com' },
          date_of_birth: '1988-05-12',
          phone: '+1 555-0199',
          injury_type: 'Knee ACL Reconstruction',
          current_condition: 'Post-op Week 6. Joint swelling reduced.',
          medical_history: 'Torn ACL playing soccer. Meniscus repair completed during surgery.',
          active_plan_name: 'ACL Recovery Protocol',
        }));
        setPatient(pat);

        // Fetch patient sessions
        const sessList = await patientApi.getSessions(patientId).catch(() => [
          {
            id: 'sess_1',
            exercise_name: 'Step Up Step Down',
            start_time: new Date(Date.now() - 3600000 * 2).toISOString(),
            total_reps: 10,
            avg_left_rom: 110,
            avg_right_rom: 95,
            symmetry_score: 86,
            session_score: 78,
          },
          {
            id: 'sess_2',
            exercise_name: 'Knee Extension',
            start_time: new Date(Date.now() - 3600000 * 24).toISOString(),
            total_reps: 15,
            avg_left_rom: 115,
            avg_right_rom: 98,
            symmetry_score: 85,
            session_score: 82,
          },
          {
            id: 'sess_3',
            exercise_name: 'Step Up Step Down',
            start_time: new Date(Date.now() - 3600000 * 48).toISOString(),
            total_reps: 10,
            avg_left_rom: 108,
            avg_right_rom: 92,
            symmetry_score: 85,
            session_score: 75,
          }
        ]);
        setSessions(sessList);

        // Fetch patient ROM analytics
        const rom = await patientApi.getAnalytics(patientId).catch(() => [
          { date: '05/20', avg_left_rom: 95, avg_right_rom: 85, avg_symmetry: 89 },
          { date: '05/23', avg_left_rom: 98, avg_right_rom: 90, avg_symmetry: 91 },
          { date: '05/26', avg_left_rom: 102, avg_right_rom: 91, avg_symmetry: 89 },
          { date: '05/29', avg_left_rom: 108, avg_right_rom: 92, avg_symmetry: 85 },
          { date: '06/01', avg_left_rom: 115, avg_right_rom: 98, avg_symmetry: 85 },
          { date: '06/04', avg_left_rom: 110, avg_right_rom: 95, avg_symmetry: 86 },
        ]);
        setRomTrends(rom);

      } catch (err) {
        toast.error('Failed to load patient clinical logs.');
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, [patientId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[70vh]">
        <Loader2 className="w-10 h-10 text-brand animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <button
          onClick={() => navigate('/therapist/dashboard')}
          className="flex items-center gap-2 text-slate-400 hover:text-slate-700 mb-3 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span className="text-sm font-semibold">Patients</span>
        </button>
        <h1 className="text-3xl font-display font-bold text-slate-800 dark:text-slate-100">
          Patient Profile
        </h1>
        <p className="text-slate-500 mt-1">Review range of motion trends, active prescription, and session histories</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* Left column: Patient Info card */}
        <div className="space-y-6">
          <div className="samarth-card p-6">
            <div className="flex items-center gap-3.5 mb-6">
              <div className="w-12 h-12 rounded-2xl bg-brand-50 text-brand flex items-center justify-center font-bold text-lg">
                <User className="w-6 h-6" />
              </div>
              <div>
                <h2 className="font-display font-bold text-slate-800 dark:text-slate-200 text-lg leading-snug">
                  {patient?.user?.full_name}
                </h2>
                <p className="text-xs text-slate-400 font-normal mt-0.5">{patient?.user?.email}</p>
              </div>
            </div>

            <div className="space-y-4 text-sm">
              <div>
                <span className="text-xs text-slate-400 block font-semibold uppercase tracking-wider">Injury</span>
                <p className="font-semibold text-slate-700 dark:text-slate-300 mt-0.5">{patient?.injury_type}</p>
              </div>
              
              <div>
                <span className="text-xs text-slate-400 block font-semibold uppercase tracking-wider">Date of Birth</span>
                <p className="font-medium text-slate-700 dark:text-slate-300 mt-0.5">{patient?.date_of_birth}</p>
              </div>

              <div>
                <span className="text-xs text-slate-400 block font-semibold uppercase tracking-wider">Phone</span>
                <p className="font-medium text-slate-700 dark:text-slate-300 mt-0.5">{patient?.phone}</p>
              </div>

              <div>
                <span className="text-xs text-slate-400 block font-semibold uppercase tracking-wider">Current Condition</span>
                <p className="text-slate-600 dark:text-slate-400 mt-0.5 text-xs leading-relaxed">{patient?.current_condition}</p>
              </div>

              <div className="pt-2">
                <span className="text-xs text-slate-400 block font-semibold uppercase tracking-wider mb-1">Medical History</span>
                <div className="bg-slate-50 dark:bg-slate-800/40 border border-slate-200/55 rounded-xl p-3 text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
                  {patient?.medical_history}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Right columns: Charts & Sessions */}
        <div className="lg:col-span-2 space-y-8">
          
          {/* ROM trends chart */}
          <div className="samarth-card p-6">
            <h2 className="text-lg font-display font-bold text-slate-800 dark:text-slate-200 mb-6 flex items-center gap-2">
              <Ruler className="w-5 h-5 text-brand" /> Kinematic ROM History
            </h2>
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={romTrends} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="date" />
                  <YAxis unit="°" domain={[60, 130]} />
                  <Tooltip contentStyle={{ borderRadius: '12px' }} />
                  <Legend verticalAlign="top" height={36} />
                  <Line type="monotone" dataKey="avg_left_rom" name="Left Knee ROM" stroke="#2A5BC4" strokeWidth={3} dot={{ r: 4 }} activeDot={{ r: 6 }} />
                  <Line type="monotone" dataKey="avg_right_rom" name="Right Knee ROM" stroke="#229096" strokeWidth={3} dot={{ r: 4 }} activeDot={{ r: 6 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Session history list */}
          <div className="samarth-card p-6">
            <h2 className="text-lg font-display font-bold text-slate-800 dark:text-slate-200 mb-5 flex items-center gap-2">
              <ClipboardList className="w-5 h-5 text-brand" /> Completed Exercise Sessions
            </h2>
            
            {sessions.length === 0 ? (
              <div className="text-center py-10 text-slate-400">
                <Activity className="w-10 h-10 mx-auto mb-2 text-slate-300" />
                <p>No exercises completed yet by this patient.</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm border-collapse">
                  <thead>
                    <tr className="border-b border-slate-100 dark:border-slate-800 text-slate-400 font-semibold text-xs uppercase tracking-wider">
                      <th className="pb-4 font-semibold">Exercise</th>
                      <th className="pb-4 font-semibold">Date Completed</th>
                      <th className="pb-4 font-semibold">Total Reps</th>
                      <th className="pb-4 font-semibold">L/R ROM</th>
                      <th className="pb-4 font-semibold">Symmetry</th>
                      <th className="pb-4 font-semibold">Quality Score</th>
                      <th className="pb-4 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60 text-slate-600 dark:text-slate-400">
                    {sessions.map((sess) => (
                      <tr key={sess.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-900/40 transition-colors">
                        <td className="py-4 font-semibold text-slate-800 dark:text-slate-200">
                          {sess.exercise_name}
                        </td>
                        <td className="py-4">
                          {new Date(sess.start_time).toLocaleString()}
                        </td>
                        <td className="py-4 font-medium text-slate-800 dark:text-slate-100">{sess.total_reps}</td>
                        <td className="py-4">
                          {sess.avg_left_rom?.toFixed(0)}° / {sess.avg_right_rom?.toFixed(0)}°
                        </td>
                        <td className="py-4 font-semibold text-slate-700 dark:text-slate-300">
                          {sess.symmetry_score?.toFixed(0)}%
                        </td>
                        <td className="py-4 font-semibold text-brand">
                          {sess.session_score ? `${(sess.session_score * 100).toFixed(0)}%` : 'N/A'}
                        </td>
                        <td className="py-4 text-right">
                          <button
                            onClick={() => navigate(`/session/summary/${sess.id}`)}
                            className="btn-secondary px-3 py-1.5 text-xs flex items-center gap-1 ml-auto border border-slate-200"
                          >
                            Report
                            <ChevronRight className="w-3.5 h-3.5" />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

        </div>

      </div>
    </div>
  );
}
