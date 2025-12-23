'use client';

import { useState, useEffect, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import {
  HiOutlineClipboardList,
  HiOutlineSearch,
  HiOutlineRefresh,
  HiOutlineUser,
  HiOutlineCube,
  HiOutlineExclamationCircle,
  HiOutlineClock,
  HiOutlineTag,
  HiOutlineIdentification
} from "react-icons/hi";

interface AuditLog {
  timestamp: string;
  operator: string;
  action: string;
  target: string;
  details: string;
}

export default function AuditPage() {
  const router = useRouter();
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [error, setError] = useState<string | null>(null);

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
    fetchLogs();
  }, [router]);

  const fetchLogs = async () => {
    setLoading(true);
    setError(null);
    try {
      const userData = localStorage.getItem('cloudo_user');
      const currentUser = userData ? JSON.parse(userData) : null;
      const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:7071/api';

      const res = await fetch(`${API_URL}/audit`, {
        headers: {
          'x-cloudo-user': currentUser?.username || ''
        }
      });

      if (!res.ok) throw new Error(`HTTP Error: ${res.status}`);

      const data = await res.json();
      setLogs(Array.isArray(data) ? data : []);
    } catch (e) {
      console.error('Failed to fetch audit logs', e);
      setError('Uplink to Security Vault failed. Check system status.');
    } finally {
      setLoading(false);
    }
  };

  const filteredLogs = useMemo(() => {
    return logs.filter(log =>
      log.operator?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      log.action?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      log.target?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      log.details?.toLowerCase().includes(searchQuery.toLowerCase())
    );
  }, [logs, searchQuery]);

  const getActionColor = (action: string) => {
    if (action.includes('DELETE') || action.includes('REVOKE')) return 'text-cloudo-err border-cloudo-err/30 bg-cloudo-err/5';
    if (action.includes('CREATE') || action.includes('ENROLL')) return 'text-cloudo-ok border-cloudo-ok/30 bg-cloudo-ok/5';
    if (action.includes('UPDATE')) return 'text-cloudo-warn border-cloudo-warn/30 bg-cloudo-warn/5';
    return 'text-cloudo-accent border-cloudo-accent/30 bg-cloudo-accent/5';
  };

  return (
    <div className="flex flex-col h-full bg-cloudo-dark text-cloudo-text font-mono selection:bg-cloudo-accent/30">
      {/* Top Bar */}
      <div className="flex items-center justify-between px-8 py-4 border-b border-cloudo-border bg-cloudo-panel sticky top-0 z-20">
        <div className="flex items-center gap-4 shrink-0">
          <div className="p-2 bg-cloudo-err/5 border border-cloudo-err/20 shrink-0">
            <HiOutlineClipboardList className="text-cloudo-err w-4 h-4" />
          </div>
          <div>
            <h1 className="text-sm font-black tracking-[0.2em] text-white uppercase">Security Audit Log</h1>
            <p className="text-[11px] text-cloudo-muted font-bold uppercase tracking-[0.3em] opacity-40">Immutable Action Trace // SEC_VAULT</p>
          </div>
        </div>

        <div className="flex items-center gap-6">
          <div className="relative group">
            <HiOutlineSearch className="absolute left-3 top-1/2 -translate-y-1/2 text-cloudo-muted/40 w-4 h-4 group-focus-within:text-cloudo-accent transition-colors" />
            <input
              type="text"
              placeholder="Search audit trail..."
              className="input pl-10 w-64 h-10 border-cloudo-border/50 focus:border-cloudo-accent/50"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
          <button
            onClick={fetchLogs}
            disabled={loading}
            className="btn btn-ghost h-10 px-4 flex items-center gap-2"
          >
            <HiOutlineRefresh className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh Trail
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-8">
        <div className="max-w-[1400px] mx-auto">
          <div className="border border-cloudo-border bg-cloudo-panel overflow-hidden relative">
             {/* Decorative corners */}
            <div className="absolute top-0 left-0 w-8 h-8 border-t border-l border-cloudo-err/20 pointer-events-none" />
            <div className="absolute bottom-0 right-0 w-8 h-8 border-b border-r border-cloudo-err/20 pointer-events-none" />

            <table className="w-full text-left border-collapse text-sm">
              <thead>
                <tr className="border-b border-cloudo-border bg-black/40">
                  <th className="px-8 py-5 font-black text-cloudo-muted uppercase tracking-[0.3em] w-48 text-[11px]">Timestamp</th>
                  <th className="px-8 py-5 font-black text-cloudo-muted uppercase tracking-[0.3em] w-40 text-[11px]">Operator</th>
                  <th className="px-8 py-5 font-black text-cloudo-muted uppercase tracking-[0.3em] w-48 text-[11px]">Action Event</th>
                  <th className="px-8 py-5 font-black text-cloudo-muted uppercase tracking-[0.3em] w-48 text-[11px]">Resource Target</th>
                  <th className="px-8 py-5 font-black text-cloudo-muted uppercase tracking-[0.3em] text-[11px]">Event Metadata</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-cloudo-border/30">
                {loading ? (
                  <tr key="loading-row"><td colSpan={5} className="py-32 text-center text-cloudo-muted italic animate-pulse uppercase tracking-[0.5em] font-black opacity-20">Extracting Vault Data...</td></tr>
                ) : error ? (
                  <tr key="error-row"><td colSpan={5} className="py-32 text-center text-cloudo-err font-black uppercase tracking-[0.2em]">
                    <div className="flex flex-col items-center gap-4">
                      <HiOutlineExclamationCircle className="w-8 h-8 opacity-40" />
                      {error}
                    </div>
                  </td></tr>
                ) : filteredLogs.length === 0 ? (
                  <tr key="empty-row"><td colSpan={5} className="py-32 text-center text-sm font-black uppercase tracking-[0.5em] opacity-10 italic">NO_AUDIT_EVENTS_CAPTURED</td></tr>
                ) : (
                  filteredLogs.map((log, idx) => (
                    <tr key={`${log.timestamp}-${idx}`} className="group hover:bg-white/[0.02] transition-colors relative border-l-2 border-l-transparent hover:border-l-cloudo-err/40">
                      <td className="px-8 py-6 whitespace-nowrap">
                        <div className="flex items-center gap-2 text-white/80 font-mono">
                          <HiOutlineClock className="w-4 h-4 opacity-30" />
                          <span>{log.timestamp?.replace('T', ' ').split('.')[0]}</span>
                        </div>
                      </td>
                      <td className="px-8 py-6">
                        <div className="flex items-center gap-2">
                          <HiOutlineUser className="w-4 h-4 text-cloudo-accent opacity-40" />
                          <span className="font-black text-white uppercase tracking-widest">{log.operator}</span>
                        </div>
                      </td>
                      <td className="px-8 py-6">
                        <span className={`px-2 py-0.5 border text-[11px] font-black uppercase tracking-widest ${getActionColor(log.action)}`}>
                          {log.action}
                        </span>
                      </td>
                      <td className="px-8 py-6">
                        <div className="flex items-center gap-2 font-mono text-cloudo-accent/80">
                          <HiOutlineTag className="w-4 h-4 opacity-30" />
                          <span className="truncate max-w-[160px] text-[11px]">{log.target}</span>
                        </div>
                      </td>
                      <td className="px-8 py-6 text-cloudo-muted font-mono text-[11px] leading-relaxed italic opacity-60 group-hover:opacity-100 transition-opacity">
                        {log.details || '---'}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
