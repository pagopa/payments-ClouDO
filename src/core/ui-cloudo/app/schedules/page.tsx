'use client';

import { useState, useEffect, useMemo } from 'react';
import {
  HiOutlinePlus,
  HiOutlineSearch,
  HiOutlineClock,
  HiOutlineTerminal,
  HiOutlineTrash,
  HiOutlinePencil,
  HiOutlineX,
  HiOutlineCheck,
  HiOutlineCheckCircle,
  HiOutlineExclamationCircle,
  HiOutlinePlay,
  HiOutlineRefresh,
  HiOutlineSwitchHorizontal,
  HiOutlineBan
} from "react-icons/hi";

interface Schedule {
  id: string;
  name: string;
  cron: string;
  runbook: string;
  run_args: string;
  queue?: string;
  worker_pool?: string;
  enabled: boolean;
  last_run?: string;
}

interface Notification {
  id: string;
  type: 'success' | 'error';
  message: string;
}

export default function SchedulesPage() {
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [modalMode, setModalMode] = useState<'create' | 'edit' | null>(null);
  const [selectedSchedule, setSelectedSchedule] = useState<Schedule | null>(null);
  const [notifications, setNotifications] = useState<Notification[]>([]);

  const addNotification = (type: 'success' | 'error', message: string) => {
    const id = Date.now().toString();
    setNotifications(prev => [...prev, { id, type, message }]);
    setTimeout(() => {
      setNotifications(prev => prev.filter(n => n.id !== id));
    }, 4000);
  };

  useEffect(() => {
    fetchSchedules();
  }, []);

  const fetchSchedules = async () => {
    setLoading(true);
    try {
      const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:7071/api';
      const userData = localStorage.getItem('cloudo_user');
      const currentUser = userData ? JSON.parse(userData) : null;

      const res = await fetch(`${API_URL}/schedules`, {
        headers: {
          'x-cloudo-user': currentUser?.username || ''
        }
      });
      const data = await res.json();
      setSchedules(Array.isArray(data) ? data : []);
    } catch (e) {
      setSchedules([]);
    } finally {
      setLoading(false);
    }
  };

  const deleteSchedule = async (id: string) => {
    if (!confirm(`Are you sure you want to delete schedule ${id}?`)) return;
    try {
      const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:7071/api';
      const userData = localStorage.getItem('cloudo_user');
      const currentUser = userData ? JSON.parse(userData) : null;

      const res = await fetch(`${API_URL}/schedules?id=${id}`, {
        method: 'DELETE',
        headers: {
          'x-cloudo-user': currentUser?.username || ''
        }
      });
      if (res.ok) {
        addNotification('success', `Schedule ${id} destroyed`);
        fetchSchedules();
      }
    } catch (e) {
      addNotification('error', 'Destruction failed');
    }
  };

  const filteredSchedules = useMemo(() => {
    return schedules.filter(s =>
      s.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.id?.toLowerCase().includes(searchQuery.toLowerCase())
    );
  }, [schedules, searchQuery]);

  return (
    <div className="flex flex-col h-full bg-cloudo-dark text-cloudo-text font-mono selection:bg-cloudo-accent/30">
      {/* Notifications */}
      <div className="fixed top-4 right-4 z-[100] space-y-2 pointer-events-none">
        {notifications.map((notif) => (
          <div
            key={notif.id}
            className={`pointer-events-auto min-w-[320px] p-4 border shadow-2xl animate-in slide-in-from-right-5 duration-300 ${
              notif.type === 'success'
                ? 'bg-cloudo-panel border-cloudo-ok/30 text-cloudo-ok'
                : 'bg-cloudo-panel border-cloudo-err/30 text-cloudo-err'
            }`}
          >
            <div className="flex items-center gap-3">
              {notif.type === 'success' ? (
                <HiOutlineCheckCircle className="w-5 h-5" />
              ) : (
                <HiOutlineExclamationCircle className="w-5 h-5" />
              )}
              <p className="text-[10px] font-black uppercase tracking-widest">{notif.message}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Top Bar */}
      <div className="flex items-center justify-between px-8 py-4 border-b border-cloudo-border bg-cloudo-panel sticky top-0 z-20">
        <div className="flex items-center gap-4 shrink-0">
          <div className="p-2 bg-cloudo-accent/5 border border-cloudo-accent/20 shrink-0">
            <HiOutlineClock className="text-cloudo-accent w-4 h-4" />
          </div>
          <div>
            <h1 className="text-sm font-black tracking-[0.2em] text-white uppercase">Automated Schedules</h1>
            <p className="text-[11px] text-cloudo-muted font-bold uppercase tracking-[0.3em] opacity-40">Cron Engine // CRON_DB</p>
          </div>
        </div>

        <div className="flex items-center gap-6">
          <div className="relative group">
            <HiOutlineSearch className="absolute left-3 top-1/2 -translate-y-1/2 text-cloudo-muted/40 w-4 h-4 group-focus-within:text-cloudo-accent transition-colors" />
            <input
              type="text"
              placeholder="Search schedules..."
              className="input pl-10 w-64 h-10 border-cloudo-border/50 focus:border-cloudo-accent/50"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
          <button
            onClick={() => { setSelectedSchedule(null); setModalMode('create'); }}
            className="btn btn-primary h-10 px-4 flex items-center gap-2 group"
          >
            <HiOutlinePlus className="w-4 h-4 group-hover:rotate-90 transition-transform" /> New Schedule
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-8">
        <div className="max-w-[1400px] mx-auto">
          <div className="border border-cloudo-border bg-cloudo-panel overflow-hidden relative">
            <div className="absolute top-0 left-0 w-8 h-8 border-t border-l border-cloudo-accent/20 pointer-events-none" />
            <div className="absolute bottom-0 right-0 w-8 h-8 border-b border-r border-cloudo-accent/20 pointer-events-none" />

            <table className="w-full text-left border-collapse text-sm">
              <thead>
                <tr className="border-b border-cloudo-border bg-black/40">
                  <th className="px-8 py-5 font-black text-cloudo-muted uppercase tracking-[0.3em] text-[11px]">Task Name</th>
                  <th className="px-8 py-5 font-black text-cloudo-muted uppercase tracking-[0.3em] text-[11px]">Cron Expression</th>
                  <th className="px-8 py-5 font-black text-cloudo-muted uppercase tracking-[0.3em] text-[11px]">Runbook Path</th>
                  <th className="px-8 py-5 font-black text-cloudo-muted uppercase tracking-[0.3em] text-[11px]">Last Execution</th>
                  <th className="px-8 py-5 font-black text-cloudo-muted uppercase tracking-[0.3em] text-right text-[11px]">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-cloudo-border/30">
                {loading ? (
                  <tr><td colSpan={5} className="py-32 text-center text-cloudo-muted italic animate-pulse uppercase tracking-[0.5em] font-black opacity-20">Syncing Cron Registry...</td></tr>
                ) : filteredSchedules.length === 0 ? (
                  <tr><td colSpan={5} className="py-32 text-center text-sm font-black uppercase tracking-[0.5em] opacity-10 italic">NO_SCHEDULES_FOUND</td></tr>
                ) : (
                  filteredSchedules.map((s) => (
                    <tr key={s.id} className="group hover:bg-cloudo-accent/[0.02] transition-colors relative border-l-2 border-l-transparent hover:border-l-cloudo-accent/40">
                      <td className="px-8 py-6">
                        <div className="flex items-center gap-3">
                          <div className={`w-2 h-2 rounded-full ${s.enabled ? 'bg-cloudo-ok animate-pulse' : 'bg-cloudo-muted opacity-30'}`} />
                          <div className="flex flex-col">
                            <span className="text-sm font-black text-white tracking-[0.1em] uppercase group-hover:text-cloudo-accent transition-colors">{s.name}</span>
                            <span className="text-[11px] text-cloudo-muted/40 font-mono mt-0.5">ID: {s.id}</span>
                          </div>
                        </div>
                      </td>
                      <td className="px-8 py-6">
                        <div className="bg-black/40 border border-cloudo-border px-3 py-1.5 font-mono text-cloudo-accent/80 text-xs w-fit">
                          {s.cron}
                        </div>
                      </td>
                      <td className="px-8 py-6 text-white/70 font-mono">
                        <div className="flex items-center gap-2">
                           <HiOutlineTerminal className="w-4 h-4 opacity-30" />
                           {s.runbook}
                        </div>
                      </td>
                      <td className="px-8 py-6 text-cloudo-muted opacity-40 font-mono">
                        {s.last_run ? new Date(s.last_run).toLocaleString() : 'NEVER_EXECUTED'}
                      </td>
                      <td className="px-8 py-6 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <button
                            onClick={() => { setSelectedSchedule(s); setModalMode('edit'); }}
                            className="p-2.5 bg-black/40 border border-cloudo-border hover:border-white/20 text-cloudo-muted hover:text-white transition-all group/btn"
                            title="Edit Schedule"
                          >
                            <HiOutlinePencil className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => deleteSchedule(s.id)}
                            className="p-2.5 bg-black/40 border border-cloudo-border hover:border-cloudo-err/40 text-cloudo-err hover:bg-cloudo-err hover:text-white transition-all group/btn"
                            title="Delete Schedule"
                          >
                            <HiOutlineTrash className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Modal */}
      {modalMode && (
        <div className="fixed inset-0 bg-cloudo-dark/90 backdrop-blur-sm flex items-center justify-center z-50 p-4" onClick={() => setModalMode(null)}>
          <div className="bg-cloudo-panel border border-cloudo-border shadow-2xl w-full max-w-xl overflow-hidden animate-in zoom-in-95 duration-200" onClick={e => e.stopPropagation()}>
            <div className="px-8 py-5 border-b border-cloudo-border flex justify-between items-center bg-black/20">
              <div className="flex items-center gap-3">
                <HiOutlineClock className="text-cloudo-accent w-5 h-5" />
                <h3 className="text-sm font-black uppercase tracking-[0.3em] text-white">
                  {modalMode === 'create' ? 'Provision Schedule' : 'Update Cron Policy'}
                </h3>
              </div>
              <button onClick={() => setModalMode(null)} className="p-1.5 hover:bg-cloudo-err hover:text-white border border-cloudo-border text-cloudo-muted transition-colors">
                <HiOutlineX className="w-5 h-5" />
              </button>
            </div>

            <ScheduleForm
              initialData={selectedSchedule}
              mode={modalMode}
              onSuccess={(msg: string) => { fetchSchedules(); setModalMode(null); addNotification('success', msg); }}
              onCancel={() => setModalMode(null)}
              onError={(msg: string) => addNotification('error', msg)}
            />
          </div>
        </div>
      )}
    </div>
  );
}

function ScheduleForm({ initialData, mode, onSuccess, onCancel, onError }: any) {
  const [formData, setFormData] = useState({
    id: initialData?.id || '',
    name: initialData?.name || '',
    cron: initialData?.cron || '0 */1 * * * *',
    runbook: initialData?.runbook || '',
    run_args: initialData?.run_args || '',
    worker_pool: initialData?.worker_pool || '',
    enabled: initialData?.enabled ?? true
  });
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:7071/api';
      const userData = localStorage.getItem('cloudo_user');
      const currentUser = userData ? JSON.parse(userData) : null;

      const res = await fetch(`${API_URL}/schedules`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-cloudo-user': currentUser?.username || ''
        },
        body: JSON.stringify(formData)
      });
      if (res.ok) {
        onSuccess(mode === 'create' ? 'Schedule provisioned' : 'Policy updated');
      } else {
        const d = await res.json();
        onError(d.error || 'Operation failed');
      }
    } catch (e) {
      onError('Uplink failed');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="p-8 space-y-6">
      <div className="grid grid-cols-2 gap-6">
        <div className="space-y-2">
          <label className="text-[11px] font-black uppercase tracking-widest text-cloudo-muted ml-1">Task Name</label>
          <input
            type="text"
            required
            className="input h-11"
            value={formData.name}
            onChange={e => setFormData({...formData, name: e.target.value})}
            placeholder="NIGHTLY_CLEANUP"
          />
        </div>
        <div className="space-y-2">
          <label className="text-[11px] font-black uppercase tracking-widest text-cloudo-muted ml-1">Cron Expression (Azure Format)</label>
          <input
            type="text"
            required
            className="input h-11 font-mono text-cloudo-accent"
            value={formData.cron}
            onChange={e => setFormData({...formData, cron: e.target.value})}
            placeholder="0 */5 * * * *"
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-6">
        <div className="space-y-2">
          <label className="text-[11px] font-black uppercase tracking-widest text-cloudo-muted ml-1">Runbook Path</label>
          <input
            type="text"
            required
            className="input h-11 font-mono"
            value={formData.runbook}
            onChange={e => setFormData({...formData, runbook: e.target.value})}
            placeholder="scripts/cleanup.sh"
          />
        </div>
        <div className="space-y-2">
          <label className="text-[11px] font-black uppercase tracking-widest text-cloudo-muted ml-1">Runtime Arguments</label>
          <input
            type="text"
            className="input h-11 font-mono"
            value={formData.run_args}
            onChange={e => setFormData({...formData, run_args: e.target.value})}
            placeholder="--force --quiet"
          />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6">
        <div className="space-y-2">
          <label className="text-[11px] font-black uppercase tracking-widest text-cloudo-muted ml-1">Worker Pool (Lock)</label>
          <input
            type="text"
            className="input h-11 font-mono"
            value={formData.worker_pool}
            onChange={e => setFormData({...formData, worker_pool: e.target.value})}
            placeholder="pool-01"
          />
        </div>
      </div>

      <div className="flex items-center justify-between p-4 bg-black/40 border border-cloudo-border group hover:border-cloudo-accent/40 transition-all cursor-pointer" onClick={() => setFormData({...formData, enabled: !formData.enabled})}>
        <div className="space-y-1">
          <p className="text-sm font-black text-white uppercase tracking-widest">Job Status</p>
          <p className="text-[11px] text-cloudo-muted uppercase font-bold opacity-40">Active Engine State</p>
        </div>
        <div className={`flex items-center gap-2 px-3 py-1 border font-black text-[11px] uppercase tracking-widest transition-all ${formData.enabled ? 'bg-cloudo-ok/10 border-cloudo-ok text-cloudo-ok' : 'bg-cloudo-muted/10 border-cloudo-muted text-cloudo-muted opacity-40'}`}>
          {formData.enabled ? <HiOutlineSwitchHorizontal className="w-4 h-4 text-cloudo-accent" /> : <HiOutlineBan className="w-4 h-4 text-cloudo-muted" />}
          {formData.enabled ? 'Active' : 'Disabled'}
        </div>
      </div>

      <div className="flex gap-4 pt-6 border-t border-cloudo-border">
        <button type="button" onClick={onCancel} className="btn btn-ghost flex-1 h-12">Abort</button>
        <button type="submit" disabled={submitting} className="btn btn-primary flex-1 h-12">
          {submitting ? 'Committing...' : 'Commit Policy'}
        </button>
      </div>
    </form>
  );
}
