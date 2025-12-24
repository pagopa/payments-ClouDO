'use client';

import { useState, useEffect } from 'react';
import { cloudoFetch } from '@/lib/api';
import { useRouter } from 'next/navigation';
import {
  HiOutlineCog,
  HiOutlineShieldCheck,
  HiOutlineSave,
  HiOutlineRefresh,
  HiOutlineCheckCircle,
  HiOutlineExclamationCircle,
  HiOutlineInformationCircle,
  HiOutlineBell,
  HiOutlineDatabase
} from "react-icons/hi";

interface Settings {
  [key: string]: string;
}

interface Notification {
  id: string;
  type: 'success' | 'error';
  message: string;
}

export default function SettingsPage() {
  const router = useRouter();
  const [settings, setSettings] = useState<Settings>({
    RUNBOOK_TIMEOUT_MIN: '30',
    LOG_RETENTION_DAYS: '90',
    NOTIFICATION_SLACK_WEBHOOK: '',
    NOTIFICATION_TEAMS_WEBHOOK: '',
    SYSTEM_MAINTENANCE_MODE: 'false',
    AUDIT_ENABLED: 'true'
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [notifications, setNotifications] = useState<Notification[]>([]);

  const addNotification = (type: 'success' | 'error', message: string) => {
    const id = Date.now().toString();
    setNotifications(prev => [...prev, { id, type, message }]);
    setTimeout(() => {
      setNotifications(prev => prev.filter(n => n.id !== id));
    }, 4000);
  };

  useEffect(() => {
    const userData = localStorage.getItem('cloudo_user');
    if (userData) {
      try {
        const user = JSON.parse(userData);
        if (user.role !== 'ADMIN') {
          router.push('/');
          return;
        }
      } catch (e) {
        router.push('/login');
        return;
      }
    } else {
      router.push('/login');
      return;
    }
    fetchSettings();
  }, [router]);

  const fetchSettings = async () => {
    setLoading(true);
    try {
      const res = await cloudoFetch(`/settings`);

      if (res.ok) {
        const data = await res.json();
        if (Object.keys(data).length > 0) {
          setSettings(prev => ({ ...prev, ...data }));
        }
      }
    } catch (e) {
      console.error('Failed to fetch settings', e);
    } finally {
      setLoading(false);
    }
  };

  const saveSettings = async () => {
    setSaving(true);
    try {
      const res = await cloudoFetch(`/settings`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(settings)
      });

      if (res.ok) {
        addNotification('success', 'Global configuration updated successfully');
      } else {
        addNotification('error', 'Failed to update settings');
      }
    } catch (e) {
      addNotification('error', 'Uplink failed');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-cloudo-dark text-cloudo-text font-mono selection:bg-cloudo-accent/30">
      {/* Notification Toast Container */}
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
                <HiOutlineCheckCircle className="w-5 h-5 flex-shrink-0" />
              ) : (
                <HiOutlineExclamationCircle className="w-5 h-5 flex-shrink-0" />
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
            <HiOutlineCog className="text-cloudo-accent w-5 h-5" />
          </div>
          <div>
            <h1 className="text-sm font-black tracking-[0.2em] text-white uppercase">System Settings</h1>
            <p className="text-[11px] text-cloudo-muted font-bold uppercase tracking-[0.3em] opacity-70">Global Config // SYSTEM_GATE</p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <button
            onClick={fetchSettings}
            className="btn btn-ghost h-10 px-4 flex items-center gap-2"
          >
            <HiOutlineRefresh className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            Sync
          </button>
          <button
            onClick={saveSettings}
            disabled={saving}
            className="btn btn-primary h-10 px-6 flex items-center gap-2"
          >
            <HiOutlineSave className="w-4 h-4" />
            {saving ? 'Saving...' : 'Commit Changes'}
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-8">
        <div className="max-w-4xl mx-auto space-y-8">

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            {/* Execution Policy Section */}
            <div className="space-y-6">
              <div className="flex items-center gap-3">
                <div className="w-1.5 h-4 bg-cloudo-accent" />
                <h2 className="text-sm font-black uppercase tracking-[0.4em] text-white">Execution Policy</h2>
              </div>

              <div className="bg-cloudo-panel border border-cloudo-border p-6 space-y-6">
                <div className="space-y-2">
                  <label className="text-[11px] font-black uppercase tracking-widest text-cloudo-muted ml-1">Runbook Timeout (Minutes)</label>
                  <input
                    type="number"
                    className="input h-11"
                    value={settings.RUNBOOK_TIMEOUT_MIN}
                    onChange={e => setSettings({...settings, RUNBOOK_TIMEOUT_MIN: e.target.value})}
                  />
                  <p className="text-[10px] text-cloudo-muted/70 uppercase tracking-tight ml-1">Kills processes exceeding this threshold</p>
                </div>

                <div className="space-y-2">
                  <label className="text-[11px] font-black uppercase tracking-widest text-cloudo-muted ml-1">Log Retention (Days)</label>
                  <input
                    type="number"
                    className="input h-11"
                    value={settings.LOG_RETENTION_DAYS}
                    onChange={e => setSettings({...settings, LOG_RETENTION_DAYS: e.target.value})}
                  />
                  <p className="text-[10px] text-cloudo-muted/70 uppercase tracking-tight ml-1">Automatic pruning of old telemetry data</p>
                </div>

                <div className="flex items-center justify-between p-4 bg-black/40 border border-cloudo-border group hover:border-cloudo-accent/40 transition-all cursor-pointer" onClick={() => setSettings({...settings, SYSTEM_MAINTENANCE_MODE: settings.SYSTEM_MAINTENANCE_MODE === 'true' ? 'false' : 'true'})}>
                  <div className="space-y-1">
                    <p className="text-sm font-black text-white uppercase tracking-widest">Maintenance Mode</p>
                    <p className="text-[11px] text-cloudo-muted uppercase font-bold opacity-70">Lock all executions</p>
                  </div>
                  <div className={`w-5 h-5 border flex items-center justify-center transition-all ${settings.SYSTEM_MAINTENANCE_MODE === 'true' ? 'bg-cloudo-err border-cloudo-err text-white' : 'border-cloudo-border'}`}>
                    {settings.SYSTEM_MAINTENANCE_MODE === 'true' && <HiOutlineShieldCheck className="w-4 h-4" />}
                  </div>
                </div>
              </div>
            </div>

            {/* Notification Channels Section */}
            <div className="space-y-6">
              <div className="flex items-center gap-3">
                <div className="w-1.5 h-4 bg-cloudo-warn" />
                <h2 className="text-sm font-black uppercase tracking-[0.4em] text-white">Security & Alerts</h2>
              </div>


              <div className="bg-cloudo-panel border border-cloudo-border p-6 space-y-6">
              {/*
                <div className="space-y-2">
                  <div className="flex items-center gap-2 mb-1">
                    <HiOutlineBell className="text-cloudo-warn w-4 h-4" />
                    <label className="text-[11px] font-black uppercase tracking-widest text-cloudo-muted">Slack Integration Hook</label>
                  </div>
                  <input
                    type="password"
                    className="input h-11 text-sm"
                    placeholder="https://hooks.slack.com/services/..."
                    value={settings.NOTIFICATION_SLACK_WEBHOOK}
                    onChange={e => setSettings({...settings, NOTIFICATION_SLACK_WEBHOOK: e.target.value})}
                  />
                </div>
                  */}

                {/*
                <div className="space-y-2">
                  <div className="flex items-center gap-2 mb-1">
                    <HiOutlineBell className="text-cloudo-accent w-4 h-4" />
                    <label className="text-[11px] font-black uppercase tracking-widest text-cloudo-muted">Teams Webhook Endpoint</label>
                  </div>
                  <input
                    type="password"
                    className="input h-11 text-sm"
                    placeholder="https://cloudo.webhook.office.com/..."
                    value={settings.NOTIFICATION_TEAMS_WEBHOOK}
                    onChange={e => setSettings({...settings, NOTIFICATION_TEAMS_WEBHOOK: e.target.value})}
                  />
                </div>

                  */}

                <div className="flex items-center justify-between p-4 bg-black/40 border border-cloudo-border group hover:border-cloudo-accent/40 transition-all cursor-pointer" onClick={() => setSettings({...settings, AUDIT_ENABLED: settings.AUDIT_ENABLED === 'true' ? 'false' : 'true'})}>
                  <div className="space-y-1">
                    <p className="text-sm font-black text-white uppercase tracking-widest">Audit Engine</p>
                    <p className="text-[11px] text-cloudo-muted uppercase font-bold opacity-70">Log all operator actions</p>
                  </div>
                  <div className={`w-5 h-5 border flex items-center justify-center transition-all ${settings.AUDIT_ENABLED === 'true' ? 'bg-cloudo-accent border-cloudo-accent text-cloudo-dark' : 'border-cloudo-border'}`}>
                    {settings.AUDIT_ENABLED === 'true' && <HiOutlineCheckCircle className="w-4 h-4" />}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* System Information Panel */}
          <div className="bg-cloudo-accent/5 border border-cloudo-accent/20 p-8 relative overflow-hidden group">
            <div className="absolute top-0 right-0 p-4 opacity-40 group-hover:opacity-60 transition-opacity">
              <HiOutlineDatabase className="w-24 h-24" />
            </div>
            <div className="relative z-10 flex gap-6 items-start">
              <HiOutlineInformationCircle className="text-cloudo-accent w-6 h-6 shrink-0 mt-1" />
              <div className="space-y-4">
                <h3 className="text-[11px] font-black text-white uppercase tracking-widest">Operator Note</h3>
                <p className="text-[10px] text-cloudo-muted uppercase font-bold leading-relaxed max-w-2xl">
                  These parameters affect the global behavior of the ClouDO engine. Changes are applied in real-time to all future runbook executions and audit streams. Verify security hooks before committing.
                </p>
              </div>
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}
