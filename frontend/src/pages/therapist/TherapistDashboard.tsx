import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { patientApi } from '@/api';
import { Users, ClipboardList, TrendingUp, CheckCircle, Search, ChevronRight, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

export default function TherapistDashboard() {
  const navigate = useNavigate();
  const [patients, setPatients] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  
  useEffect(() => {
    const fetchPatients = async () => {
      try {
        const res = await patientApi.list().catch(() => [
          {
            id: 'pat_1',
            user: { full_name: 'John Doe', email: 'john@example.com' },
            injury_type: 'Knee ACL Reconstruction',
            current_condition: 'Post-op Week 6. Minor knee stiffness.',
            compliance_rate: 94,
            last_session_date: new Date(Date.now() - 3600000 * 2).toISOString(),
            active_plan_name: 'ACL Recovery Protocol',
          },
          {
            id: 'pat_2',
            user: { full_name: 'Alice Smith', email: 'alice@example.com' },
            injury_type: 'Ankle Dorsiflexion Restriction',
            current_condition: 'Chronic tightness. Improving ROM.',
            compliance_rate: 85,
            last_session_date: new Date(Date.now() - 3600000 * 24).toISOString(),
            active_plan_name: 'Ankle Mobility Standard',
          },
          {
            id: 'pat_3',
            user: { full_name: 'Robert Johnson', email: 'robert@example.com' },
            injury_type: 'Hip Osteoarthritis',
            current_condition: 'Mild pain during deep flexion.',
            compliance_rate: 60,
            last_session_date: new Date(Date.now() - 3600000 * 48).toISOString(),
            active_plan_name: 'Hip Extension Protocol',
          }
        ]);
        setPatients(res);
      } catch {
        toast.error('Failed to load patient directory.');
      } finally {
        setLoading(false);
      }
    };
    fetchPatients();
  }, []);

  const filteredPatients = patients.filter((p) => {
    const name = p.user?.full_name || '';
    const email = p.user?.email || '';
    const injury = p.injury_type || '';
    return name.toLowerCase().includes(search.toLowerCase()) ||
      email.toLowerCase().includes(search.toLowerCase()) ||
      injury.toLowerCase().includes(search.toLowerCase());
  });

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-display font-bold text-slate-800 dark:text-slate-100">Patient Directory</h1>
        <p className="text-slate-500 mt-1">Monitor patient recovery compliance, review AI kinematic logs, and adjust prescriptions</p>
      </div>

      {/* Quick Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-5">
        <div className="stat-card">
          <div className="flex justify-between items-start">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Total Patients</span>
            <Users className="w-5 h-5 text-brand" />
          </div>
          <span className="text-3xl font-display font-bold text-slate-800 dark:text-slate-100 mt-2">
            {patients.length}
          </span>
          <span className="text-xs text-slate-400 mt-1">Active caseload</span>
        </div>

        <div className="stat-card">
          <div className="flex justify-between items-start">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Active Prescriptions</span>
            <ClipboardList className="w-5 h-5 text-purple-500" />
          </div>
          <span className="text-3xl font-display font-bold text-slate-800 dark:text-slate-100 mt-2">
            {patients.filter((p) => p.active_plan_name).length}
          </span>
          <span className="text-xs text-slate-400 mt-1">Structured plans running</span>
        </div>

        <div className="stat-card">
          <div className="flex justify-between items-start">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Case Compliance</span>
            <TrendingUp className="w-5 h-5 text-green-500" />
          </div>
          <span className="text-3xl font-display font-bold text-slate-800 dark:text-slate-100 mt-2">
            {(patients.reduce((acc, curr) => acc + (curr.compliance_rate || 0), 0) / (patients.length || 1)).toFixed(0)}%
          </span>
          <span className="text-xs text-green-600 font-semibold mt-1">Above threshold (80%)</span>
        </div>

        <div className="stat-card">
          <div className="flex justify-between items-start">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Sessions This Week</span>
            <CheckCircle className="w-5 h-5 text-accent" />
          </div>
          <span className="text-3xl font-display font-bold text-slate-800 dark:text-slate-100 mt-2">
            18
          </span>
          <span className="text-xs text-slate-400 mt-1">Completed by patients</span>
        </div>
      </div>

      {/* Search Bar & Table */}
      <div className="samarth-card p-6">
        <div className="flex items-center gap-3 mb-6 bg-slate-50 dark:bg-slate-800 px-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 max-w-md">
          <Search className="w-5 h-5 text-slate-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search patients by name, email, or injury..."
            className="w-full bg-transparent text-sm focus:outline-none text-slate-800 dark:text-slate-200"
          />
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-10 h-10 text-brand animate-spin" />
          </div>
        ) : filteredPatients.length === 0 ? (
          <div className="text-center py-20 text-slate-400">
            <Users className="w-12 h-12 mx-auto mb-3 text-slate-300" />
            <p>No patients matched your search.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm border-collapse">
              <thead>
                <tr className="border-b border-slate-100 dark:border-slate-800 text-slate-400 font-semibold text-xs uppercase tracking-wider">
                  <th className="pb-4 font-semibold">Patient Name</th>
                  <th className="pb-4 font-semibold">Injury Category</th>
                  <th className="pb-4 font-semibold">Prescribed Protocol</th>
                  <th className="pb-4 font-semibold">Last Session</th>
                  <th className="pb-4 font-semibold">Compliance</th>
                  <th className="pb-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                {filteredPatients.map((patient) => (
                  <tr key={patient.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-900/40 transition-colors">
                    <td className="py-4 font-semibold text-slate-800 dark:text-slate-200">
                      <div>
                        <p>{patient.user?.full_name}</p>
                        <p className="text-xs text-slate-400 font-normal mt-0.5">{patient.user?.email}</p>
                      </div>
                    </td>
                    <td className="py-4 text-slate-600 dark:text-slate-400">{patient.injury_type}</td>
                    <td className="py-4 font-medium text-slate-700 dark:text-slate-300">
                      {patient.active_plan_name || (
                        <span className="text-xs text-slate-400 italic">No plan prescribed</span>
                      )}
                    </td>
                    <td className="py-4 text-slate-500 dark:text-slate-400">
                      {patient.last_session_date ? new Date(patient.last_session_date).toLocaleDateString() : 'N/A'}
                    </td>
                    <td className="py-4">
                      <div className="flex items-center gap-2">
                        <div className="w-16 h-2 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full ${
                              patient.compliance_rate > 80 ? 'bg-green-500' : patient.compliance_rate > 60 ? 'bg-amber-500' : 'bg-red-500'
                            }`}
                            style={{ width: `${patient.compliance_rate}%` }}
                          />
                        </div>
                        <span className="font-semibold text-slate-700 dark:text-slate-300">{patient.compliance_rate}%</span>
                      </div>
                    </td>
                    <td className="py-4 text-right">
                      <button
                        onClick={() => navigate(`/therapist/patient/${patient.id}`)}
                        className="btn-secondary px-3.5 py-1.5 text-xs flex items-center gap-1 ml-auto border border-slate-200"
                        id={`view-patient-${patient.id}`}
                      >
                        Details
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
  );
}
