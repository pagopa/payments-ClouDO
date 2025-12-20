'use client';

import { useState, useEffect } from 'react';
import {
  HiOutlineSearch,
  HiOutlineDatabase,
  HiOutlineTerminal,
  HiOutlineX,
  HiOutlineRefresh,
  HiOutlineFilter,
  HiOutlineClipboardCheck,
  HiOutlineClipboard,
  HiOutlineCalendar,
  HiOutlineTag
} from 'react-icons/hi';

interface LogEntry {
  PartitionKey: string;
  RowKey: string;
  ExecId: string;
  Status: string;
  RequestedAt: string;
  Name: string;
  Id: string;
  Runbook: string;
  Run_Args: string;
  Log: string;
  MonitorCondition: string;
  Severity: string;
  OnCall?: boolean | string;
}

export function LogsPanel() {
  const [partitionKey, setPartitionKey] = useState('');
  const [execId, setExecId] = useState('');
  const [status, setStatus] = useState('');
  const [query, setQuery] = useState('');
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedLog, setSelectedLog] = useState<LogEntry | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const today = new Date();
    const yyyymmdd = `${today.getFullYear()}${String(today.getMonth() + 1).padStart(2, '0')}${String(today.getDate()).padStart(2, '0')}`;
    setPartitionKey(yyyymmdd);
  }, []);

  const runQuery = async () => {
    if (!partitionKey) return;
    setLoading(true);
    try {
      const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:7071/api';
      const params = new URLSearchParams({ partitionKey });
      if (execId) params.set('execId', execId);
      if (status) params.set('status', status);
      if (query) params.set('q', query);

      const res = await fetch(`${API_URL}/logs/query?${params}`);
      const data = await res.json();
      const rawLogs = data.items || [];

      // Group by ExecId and keep only the final status
      const groupedByExecId = new Map<string, LogEntry>();
      const statusPriority: Record<string, number> = {
        'succeeded': 5,
        'completed': 5,
        'failed': 4,
        'error': 4,
        'running': 3,
        'accepted': 2,
        'pending': 1,
      };

      rawLogs.forEach((log: LogEntry) => {
        const execId = log.ExecId;
        const existing = groupedByExecId.get(execId);

        if (!existing) {
          groupedByExecId.set(execId, log);
        } else {
          // Keep the entry with higher priority status
          const currentPriority = statusPriority[log.Status?.toLowerCase()] || 0;
          const existingPriority = statusPriority[existing.Status?.toLowerCase()] || 0;

          if (currentPriority > existingPriority) {
            groupedByExecId.set(execId, log);
          } else if (currentPriority === existingPriority) {
            // If same priority, keep the most recent
            if (log.RequestedAt > existing.RequestedAt) {
              groupedByExecId.set(execId, log);
            }
          }
        }
      });

      setLogs(Array.from(groupedByExecId.values()).sort((a, b) =>
        b.RequestedAt.localeCompare(a.RequestedAt)
      ));
    } catch (error) {
      console.error('Error fetching logs:', error);
      setLogs([]);
    } finally {
      setLoading(false);
    }
  };

  const getStatusBadgeClass = (status: string) => {
    const s = status.toLowerCase();
    if (s === 'succeeded' || s === 'completed') return 'status-succeeded shadow-[0_0_8px_rgba(34,197,94,0.2)]';
    if (s === 'running') return 'status-running shadow-[0_0_8px_rgba(59,130,246,0.2)]';
    if (s === 'failed' || s === 'error') return 'status-failed shadow-[0_0_8px_rgba(239,68,68,0.2)]';
    return 'status-pending opacity-70';
  };

  const formatLogContent = (content: string) => {
    if (!content) return <span className="italic text-cloudo-muted opacity-50">No log data available</span>;
    return content.split('\n').map((line, i) => {
      let color = 'text-cloudo-text/80';
      if (line.toUpperCase().includes('ERROR') || line.toUpperCase().includes('EXCEPTION')) color = 'text-red-400';
      if (line.toUpperCase().includes('WARN')) color = 'text-yellow-400';
      if (line.toUpperCase().includes('INFO')) color = 'text-blue-300';
      return <div key={i} className={`${color} font-mono text-[11px] leading-relaxed py-0.5 border-b border-white/[0.02]`}>{line}</div>;
    });
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="flex flex-col lg:flex-row gap-4 h-[calc(100vh-12rem)] bg-[#0a0c10] p-2">
      {/* Search & List Section */}
      <div className={`flex flex-col gap-4 overflow-hidden transition-all duration-500 ${selectedLog ? 'lg:max-w-[40%]' : 'w-full'}`}>

        {/* Filters Card */}
        <div className="bg-[#0d1117]/60 border border-cloudo-border/20 rounded-xl overflow-hidden shadow-xl">
          <div className="px-6 py-4 border-b border-cloudo-border/20 flex justify-between items-center bg-white/[0.02]">
            <div className="flex items-center gap-3">
              <HiOutlineDatabase className="text-cloudo-accent w-4 h-4" />
              <h2 className="text-[10px] font-black uppercase tracking-[0.2em] text-white">Log Explorer</h2>
            </div>
            <button
              onClick={() => { setExecId(''); setStatus(''); setQuery(''); setLogs([]); setSelectedLog(null); }}
              className="text-[9px] font-black uppercase tracking-widest text-cloudo-muted hover:text-white transition-colors"
            >
              Reset Filters
            </button>
          </div>

          <div className="p-6 space-y-6">
            <div className="grid grid-cols-2 md:grid-cols-3 gap-6">
              <div className="space-y-2">
                <label className="text-[9px] font-black uppercase tracking-widest text-cloudo-muted ml-1">Partition (Date)</label>
                <div className="relative">
                  <HiOutlineCalendar className="absolute left-3 top-1/2 -translate-y-1/2 text-cloudo-muted/40 w-3.5 h-3.5" />
                  <input
                    type="text"
                    className="w-full bg-black/40 border border-cloudo-border/50 rounded-md pl-9 pr-3 py-2 text-[11px] font-mono text-white outline-none focus:border-cloudo-accent/60 transition-all"
                    placeholder="YYYYMMDD"
                    value={partitionKey}
                    onChange={(e) => setPartitionKey(e.target.value)}
                  />
                </div>
              </div>
              <div className="space-y-2">
                <label className="text-[9px] font-black uppercase tracking-widest text-cloudo-muted ml-1">Filter Status</label>
                <div className="relative">
                  <HiOutlineTag className="absolute left-3 top-1/2 -translate-y-1/2 text-cloudo-muted/40 w-3.5 h-3.5" />
                  <select
                    className="w-full bg-black/40 border border-cloudo-border/50 rounded-md pl-9 pr-3 py-2 text-[11px] text-white outline-none focus:border-cloudo-accent/60 appearance-none cursor-pointer"
                    value={status}
                    onChange={(e) => setStatus(e.target.value)}
                  >
                    <option value="">All Events</option>
                    <option value="succeeded">Succeeded</option>
                    <option value="running">Running</option>
                    <option value="failed">Failed</option>
                  </select>
                </div>
              </div>
              <div className="col-span-2 md:col-span-1 space-y-2">
                <label className="text-[9px] font-black uppercase tracking-widest text-cloudo-muted ml-1">Content Search</label>
                <div className="relative">
                  <HiOutlineSearch className="absolute left-3 top-1/2 -translate-y-1/2 text-cloudo-muted/40 w-3.5 h-3.5" />
                  <input
                    type="text"
                    className="w-full bg-black/40 border border-cloudo-border/50 rounded-md pl-9 pr-3 py-2 text-[11px] text-white outline-none focus:border-cloudo-accent/60 transition-all"
                    placeholder="Search logs..."
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                  />
                </div>
              </div>
            </div>

            <button
              onClick={runQuery}
              disabled={loading}
              className="w-full bg-cloudo-accent hover:bg-cloudo-accent/90 text-white py-2.5 rounded-md text-[10px] font-black uppercase tracking-[0.2em] transition-all flex items-center justify-center gap-2 shadow-lg shadow-cloudo-accent/10 disabled:opacity-30"
            >
              {loading ? <HiOutlineRefresh className="animate-spin w-3.5 h-3.5" /> : <HiOutlineFilter className="w-3.5 h-3.5" />}
              {loading ? 'Executing Query...' : 'Run Diagnostics'}
            </button>
          </div>
        </div>

        {/* Results List Card */}
        <div className="bg-[#0d1117]/40 border border-cloudo-border/20 rounded-xl flex-1 overflow-hidden flex flex-col shadow-2xl">
          <div className="overflow-y-auto custom-scrollbar">
            <table className="w-full text-[11px] border-collapse">
              <thead className="bg-[#0d1117] sticky top-0 z-10 border-b border-cloudo-border/20">
                <tr className="text-[9px] font-black text-cloudo-muted uppercase tracking-widest">
                  <th className="px-4 py-3 text-left">Timestamp</th>
                  <th className="px-4 py-3 text-left">Status</th>
                  <th className="px-4 py-3 text-left">Process</th>
                  <th className="px-4 py-3 text-center w-10">OC</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-cloudo-border/10">
                {logs.map((log) => (
                  <tr
                    key={log.RowKey}
                    onClick={() => setSelectedLog(log)}
                    className={`cursor-pointer transition-colors hover:bg-cloudo-accent/[0.03] ${selectedLog?.RowKey === log.RowKey ? 'bg-cloudo-accent/[0.06] border-l-2 border-cloudo-accent' : ''}`}
                  >
                    <td className="px-4 py-4 whitespace-nowrap">
                      <div className="text-white font-bold">{log.RequestedAt?.split('T')[1]?.slice(0, 8)}</div>
                      <div className="text-[9px] text-cloudo-muted font-mono opacity-60">{log.RequestedAt?.split('T')[0]}</div>
                    </td>
                    <td className="px-4 py-4">
                      <span className={`px-2 py-0.5 rounded-[4px] text-[9px] font-black uppercase tracking-tighter border border-transparent ${getStatusBadgeClass(log.Status)}`}>
                        {log.Status}
                      </span>
                    </td>
                    <td className="px-4 py-4">
                      <div className="text-white font-semibold truncate max-w-[150px]">{log.Name || 'unnamed'}</div>
                      <div className="text-[9px] text-cloudo-muted font-mono opacity-50 truncate max-w-[150px]">{log.ExecId}</div>
                    </td>
                    <td className="px-4 py-4 text-center">
                      {(log.OnCall === true || log.OnCall === 'true') && (
                        <div className="flex justify-center" title="On-Call Triggered">
                          <span className="relative flex h-2 w-2">
                            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-500 opacity-40"></span>
                            <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500"></span>
                          </span>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {logs.length === 0 && !loading && (
              <div className="py-20 text-center flex flex-col items-center gap-2 opacity-30">
                <HiOutlineTerminal className="w-8 h-8" />
                <span className="text-[10px] font-black uppercase tracking-widest">No matching logs</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Detail Panel Section */}
      {selectedLog && (
        <div className="flex-1 bg-[#0d1117]/60 border border-cloudo-border/30 rounded-xl overflow-hidden flex flex-col shadow-2xl animate-in slide-in-from-right duration-300">
          <div className="px-6 py-4 border-b border-cloudo-border/20 flex justify-between items-center bg-white/[0.02]">
            <div className="flex items-center gap-4">
              <div className="p-2 bg-cloudo-accent/10 rounded-lg">
                <HiOutlineTerminal className="text-cloudo-accent w-4 h-4" />
              </div>
              <div>
                <h3 className="font-bold text-sm text-white leading-none">{selectedLog.Name || 'Runtime Process'}</h3>
                <div className="flex items-center gap-2 mt-1.5 group">
                  <code className="text-[10px] text-cloudo-muted font-mono">{selectedLog.ExecId}</code>
                  <button
                    onClick={() => copyToClipboard(selectedLog.ExecId)}
                    className="text-cloudo-muted hover:text-cloudo-accent transition-colors"
                  >
                    {copied ? <HiOutlineClipboardCheck className="w-3.5 h-3.5 text-cloudo-ok" /> : <HiOutlineClipboard className="w-3.5 h-3.5 opacity-40 group-hover:opacity-100" />}
                  </button>
                </div>
              </div>
            </div>
            <button onClick={() => setSelectedLog(null)} className="p-2 hover:bg-white/5 rounded-full text-cloudo-muted transition-colors">
              <HiOutlineX className="w-5 h-5" />
            </button>
          </div>

          <div className="flex-1 overflow-hidden flex flex-col bg-[#080a0f]">
            {/* Metadata bar */}
            <div className="grid grid-cols-2 divide-x divide-cloudo-border/10 border-b border-cloudo-border/10">
              <div className="px-6 py-3">
                <span className="text-[9px] font-black text-cloudo-muted uppercase tracking-widest block mb-1">Execution Date</span>
                <span className="text-[11px] text-white font-mono">{new Date(selectedLog.RequestedAt).toLocaleString()}</span>
              </div>
              <div className="px-6 py-3">
                <span className="text-[9px] font-black text-cloudo-muted uppercase tracking-widest block mb-1">Logic Asset</span>
                <span className="text-[11px] text-cloudo-accent font-mono">{selectedLog.Runbook}</span>
              </div>
            </div>

            {/* Log Terminal Output */}
            <div className="flex-1 overflow-y-auto p-6 custom-scrollbar font-mono">
              <div className="space-y-0.5">
                {formatLogContent(selectedLog.Log)}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
