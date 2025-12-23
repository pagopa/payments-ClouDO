'use client';

import { useEffect, useState } from 'react';
import {
  HiOutlineCheckCircle,
  HiOutlineUsers,
  HiOutlineClock,
  HiOutlineTerminal,
  HiOutlineDatabase,
  HiOutlineArrowRight,
  HiOutlineLightningBolt,
  HiOutlineChartBar,
  HiOutlineShieldCheck,
  HiOutlineServer
} from "react-icons/hi";
import { MdOutlineSpaceDashboard, MdOutlineSchema } from "react-icons/md";

interface DashboardStats {
  totalExecutions: number;
  successRate: number;
  activeWorkers: number;
  pendingApprovals: number;
  recentExecutions: any[];
  liveProcesses: any[];
}

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats>({
    totalExecutions: 0,
    successRate: 0,
    activeWorkers: 0,
    pendingApprovals: 0,
    recentExecutions: [],
    liveProcesses: [],
  });
  const [loading, setLoading] = useState(true);
  const [isBackendDown, setIsBackendDown] = useState(false);

  useEffect(() => {
    fetchDashboardData();
    const interval = setInterval(fetchDashboardData, 30000);
    return () => clearInterval(interval);
  }, []);

  const fetchDashboardData = async () => {
    try {
      const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:7071/api';

      const workersRes = await fetch(`${API_URL}/workers`, {
        headers: { 'x-cloudo-key': process.env.NEXT_PUBLIC_CLOUDO_KEY || '' },
      });

      if (!workersRes.ok) throw new Error('Backend unreachable');

      const workers = await workersRes.json();
      const activeWorkers = Array.isArray(workers) ? workers : [];

      const processesPromises = activeWorkers.map(async (w: any) => {
        try {
          const res = await fetch(`${API_URL}/workers/processes?worker=${encodeURIComponent(w.RowKey)}`);
          if (!res.ok) return [];
          const data = await res.json();
          const procList = Array.isArray(data) ? data : (data.runs || data.processes || []);
          return procList.map((p: any) => ({ ...p, workerNode: w.RowKey }));
        } catch { return []; }
      });

      const allLiveProcesses = (await Promise.all(processesPromises)).flat();

      const today = new Date();
      const partitionKey = `${today.getFullYear()}${String(today.getMonth() + 1).padStart(2, '0')}${String(today.getDate()).padStart(2, '0')}`;
      const logsRes = await fetch(`${API_URL}/logs/query?partitionKey=${partitionKey}&limit=2000`);
      const logsData = await logsRes.json();

      const executions = logsData.items || [];

      // Group by ExecId and keep only the final status
      const groupedByExecId = new Map<string, any>();
      const statusPriority: Record<string, number> = {
        'succeeded': 5,
        'completed': 5,
        'failed': 4,
        'error': 4,
        'running': 3,
        'rejected': 3,
        'accepted': 2,
        'pending': 1,
        'skipped': 1,
        'routed': 1,
      };

      executions.forEach((log: any) => {
        const execId = log.ExecId;
        const existing = groupedByExecId.get(execId);

        if (!existing) {
          groupedByExecId.set(execId, log);
        } else {
          const currentPriority = statusPriority[log.Status?.toLowerCase()] || 0;
          const existingPriority = statusPriority[existing.Status?.toLowerCase()] || 0;

          if (currentPriority > existingPriority) {
            groupedByExecId.set(execId, log);
          } else if (currentPriority === existingPriority) {
            if (new Date(log.RequestedAt).getTime() > new Date(existing.RequestedAt).getTime()) {
              groupedByExecId.set(execId, log);
            }
          }
        }
      });

      const finalExecutions = Array.from(groupedByExecId.values());

      const succeeded = finalExecutions.filter((e: any) =>
        ['succeeded', 'completed'].includes((e.Status || '').toLowerCase())
      ).length;

      const pending = finalExecutions.filter((e: any) =>
        ['pending', 'accepted'].includes((e.Status || '').toLowerCase())
      ).length;

      const sortedExecutions = [...finalExecutions]
        .sort((a, b) => new Date(b.RequestedAt || 0).getTime() - new Date(a.RequestedAt || 0).getTime())
        .slice(0, 5);

      setStats({
        totalExecutions: finalExecutions.length,
            successRate: finalExecutions.length > 0 ? (succeeded / finalExecutions.length) * 100 : 0,
        activeWorkers: activeWorkers.length,
        pendingApprovals: pending,
        recentExecutions: sortedExecutions,
        liveProcesses: allLiveProcesses,
      });
      setIsBackendDown(false);
    } catch (error) {
      console.error('Error fetching dashboard data:', error);
      setIsBackendDown(true);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-full bg-[#0a0c10]">
        <div className="w-8 h-8 border-2 border-cloudo-accent/30 border-t-cloudo-accent rounded-full animate-spin mb-4" />
        <span className="text-[10px] font-black uppercase tracking-[0.3em] text-cloudo-muted">Booting Systems...</span>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-[#0a0c10] text-cloudo-text font-sans selection:bg-cloudo-accent/30">
      {/* Header Bar */}
      <div className="flex items-center justify-between px-8 py-4 border-b border-cloudo-border/20 bg-[#0d1117]/80 backdrop-blur-xl sticky top-0 z-20">
        <div className="flex items-center gap-4">
          <div className="p-2 bg-cloudo-accent/10 rounded-lg border border-cloudo-accent/20">
            <MdOutlineSpaceDashboard className="text-cloudo-accent w-5 h-5" />
          </div>
          <div>
            <h1 className="text-sm font-bold tracking-tight text-white uppercase">Operations Dashboard</h1>
            <p className="text-[10px] text-cloudo-muted font-bold uppercase tracking-[0.2em] opacity-60">Fleet Telemetry</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className="relative flex h-2 w-2">
            <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-40 ${isBackendDown ? 'bg-cloudo-err' : 'bg-cloudo-ok'}`}></span>
            <span className={`relative inline-flex rounded-full h-2 w-2 ${isBackendDown ? 'bg-cloudo-err' : 'bg-cloudo-ok'}`}></span>
          </span>
          <span className={`text-[10px] font-black uppercase tracking-widest italic ${isBackendDown ? 'text-cloudo-err animate-pulse' : 'text-cloudo-muted'}`}>
            {isBackendDown ? 'Connection Lost • Retry' : 'Live Stream • 30s'}
          </span>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-8 space-y-8">
        <div className="max-w-[1400px] mx-auto space-y-8">

          {/* Stats Cards Row */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard
              title="Workload Executions"
              value={stats.totalExecutions}
              icon={<HiOutlineTerminal className="text-blue-400" />}
              status="Today's Load"
            />
            <StatCard
              title="Executions Success Rate"
              value={`${stats.successRate.toFixed(1)}%`}
              icon={<HiOutlineCheckCircle className="text-cloudo-ok" />}
              status="Success Ratio"
            />
            <StatCard
              title="Compute Nodes"
              value={stats.activeWorkers}
              icon={<HiOutlineServer className="text-cloudo-accent" />}
              status="Active Capacity"
            />
            <StatCard
              title="Governance Queue"
              value={stats.pendingApprovals}
              icon={<HiOutlineClock className="text-cloudo-warn" />}
              status="Manual Actions"
              highlight={stats.pendingApprovals > 0}
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Recent Activity Table (Operational Stream) */}
            <div className="lg:col-span-2 space-y-4">
              <h2 className="text-[10px] font-black uppercase tracking-[0.3em] text-cloudo-muted border-b border-cloudo-border/10 pb-2">Operational Stream</h2>
              <div className="bg-[#0d1117]/40 border border-cloudo-border/20 rounded-xl overflow-hidden shadow-2xl">
                <table className="w-full text-left border-collapse text-xs">
                  <thead className="bg-white/[0.02] border-b border-cloudo-border/20">
                    <tr className="text-[9px] font-black text-cloudo-muted uppercase tracking-widest">
                      <th className="px-6 py-3">Event</th>
                      <th className="px-6 py-3">Asset Path</th>
                      <th className="px-6 py-3">Status</th>
                      <th className="px-6 py-3 text-right">Time</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-cloudo-border/10">
                    {stats.recentExecutions.length === 0 ? (
                      <tr><td colSpan={4} className="py-20 text-center text-[10px] uppercase font-bold text-cloudo-muted italic opacity-40 text-center">Empty Stream Output</td></tr>
                    ) : (
                      stats.recentExecutions.map((exec: any) => (
                        <tr key={exec.RowKey} className="group hover:bg-cloudo-accent/[0.02] transition-colors">
                          <td className="px-6 py-4">
                            <div className="font-bold text-white tracking-tight">{exec.Name || 'Runtime Task'}</div>
                            <div className="text-[10px] font-mono text-cloudo-accent/80 font-bold mt-0.5">
                              {exec.Id || '--'}
                            </div>
                          </td>
                          <td className="px-6 py-4 font-mono text-cloudo-accent/60 italic text-[11px]">
                            {exec.Runbook || '--'}
                          </td>
                          <td className="px-6 py-4">
                            <div className="flex flex-col gap-1">
                              <StatusIndicator status={exec.Status} />
                              <div
                                className="text-[8px] font-mono text-cloudo-muted/40 group-hover:text-cloudo-muted/80 transition-colors cursor-help flex items-center gap-1"
                                title={`Full ID: ${exec.ExecId}`}
                                onClick={() => navigator.clipboard.writeText(exec.ExecId)}
                              >
                                <span className="opacity-50">HEX:</span> {exec.ExecId?.slice(0, 12)}...
                              </div>
                            </div>
                          </td>
                          <td className="px-6 py-4 text-right">
                             <div className="text-white font-mono">{new Date(exec.RequestedAt).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', second:'2-digit'})}</div>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Live Worker Processes */}
            <div className="space-y-4">
              <h2 className="text-[10px] font-black uppercase tracking-[0.3em] text-cloudo-muted border-b border-cloudo-border/10 pb-2">Live Worker Processes</h2>
              <div className="bg-[#0d1117]/40 border border-cloudo-border/20 rounded-xl p-4 space-y-3 min-h-[320px] max-h-[500px] overflow-y-auto custom-scrollbar">
                    {stats.liveProcesses.length === 0 ? (
                      <div className="py-20 text-center opacity-20 flex flex-col items-center gap-2">
                        <HiOutlineServer className="w-8 h-8" />
                        <span className="text-[10px] font-black uppercase tracking-widest">No active workloads detected</span>
                      </div>
                    ) : (
                      stats.liveProcesses.map((proc: any) => (
                        <div key={proc.exec_id} className="bg-black/40 border border-cloudo-border/20 rounded-lg p-3 group hover:border-cloudo-accent/30 transition-all border-l-2 border-l-blue-500/50">
                          <div className="flex justify-between items-start mb-2">
                            <div className="flex items-center gap-2">
                              <div className="relative flex items-center justify-center">
                                <span className="absolute animate-ping h-2 w-2 rounded-full bg-blue-400 opacity-40"></span>
                                <div className="relative w-1.5 h-1.5 rounded-full bg-blue-500" />
                              </div>
                              <span className="text-[11px] font-bold text-white truncate max-w-[140px]">{proc.name}</span>
                            </div>
                            <span className="text-[9px] font-mono text-cloudo-accent/60 italic">{proc.workerNode}</span>
                          </div>
                          <div className="flex justify-between items-center text-[9px] text-cloudo-muted uppercase font-bold tracking-tighter">
                            <span className="flex items-center gap-1"><HiOutlineTerminal className="w-3 h-3"/> {proc.runbook}</span>
                            <span className="opacity-40">{proc.exec_id.slice(0, 8)}</span>
                          </div>
                        </div>
                      ))
                    )}
                  </div>

                  <h2 className="text-[10px] font-black uppercase tracking-[0.3em] text-cloudo-muted border-b border-cloudo-border/10 pb-2 pt-4">Direct Actions</h2>
              <div className="grid grid-cols-1 gap-2">
                <QuickLink icon={<HiOutlineLightningBolt />} label="Trigger Engine" href="/trigger" />
                <QuickLink icon={<HiOutlineDatabase />} label="Registry" href="/schemas" />
                <QuickLink icon={<HiOutlineServer />} label="Compute" href="/workers" />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function StatCard({ title, value, icon, status, highlight = false }: any) {
  return (
    <div className="bg-[#0d1117]/60 border border-cloudo-border/20 rounded-xl p-6 flex items-center justify-between shadow-xl">
      <div>
        <p className="text-[9px] font-black uppercase tracking-[0.15em] text-cloudo-muted">{title}</p>
        <p className={`text-2xl font-black mt-1 ${highlight ? 'text-amber-500 shadow-[0_0_15px_rgba(245,158,11,0.1)]' : 'text-white'}`}>{value}</p>
        <p className="text-[9px] font-bold text-cloudo-muted uppercase mt-2 opacity-50 tracking-tighter">{status}</p>
      </div>
      <div className="p-3 bg-white/[0.03] rounded-lg border border-white/[0.05] text-xl">
        {icon}
      </div>
    </div>
  );
}

function StatusIndicator({ status }: { status: string }) {
  const s = (status || '').toLowerCase();
  const colors: Record<string, string> = {
    succeeded: 'bg-cloudo-ok shadow-[0_0_8px_rgba(34,197,94,0.3)]',
    running: 'bg-blue-500 shadow-[0_0_8px_rgba(59,130,246,0.3)]',
    routed: 'bg-blue-500 shadow-[0_0_8px_rgba(59,130,246,0.3)]',
    failed: 'bg-cloudo-err shadow-[0_0_8px_rgba(239,68,68,0.3)]',
    error: 'bg-cloudo-err shadow-[0_0_8px_rgba(239,68,68,0.3)]',
    pending: 'bg-amber-500/50',
    accepted: 'bg-amber-500/50',
  };

  return (
    <div className="flex items-center gap-3">
      <div className="relative flex items-center justify-center">
        {s === 'running' && (
          <span className="absolute animate-ping h-3 w-3 rounded-full bg-blue-500 opacity-40"></span>
        )}
        <div className={`relative w-2 h-2 rounded-full ${colors[s] || 'bg-cloudo-muted'}`} />
      </div>
      <span className="text-[9px] font-black uppercase tracking-widest text-white/80">{status}</span>
    </div>
  );
}

function HealthMetric({ name, status, uptime }: any) {
  const isHealthy = status === 'healthy';
  return (
    <div className="flex items-center justify-between p-3 bg-black/40 border border-cloudo-border/20 rounded-lg group hover:border-cloudo-accent/20 transition-all">
      <div className="flex items-center gap-3">
        <div className={`w-1.5 h-1.5 rounded-full ${isHealthy ? 'bg-cloudo-ok shadow-[0_0_8px_rgba(34,197,94,0.3)]' : 'bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.3)] animate-pulse'}`} />
        <span className="text-[10px] font-bold text-white/90 uppercase tracking-tight">{name}</span>
      </div>
      <span className="text-[9px] font-mono text-cloudo-muted uppercase tracking-tighter">{uptime}</span>
    </div>
  );
}

function QuickLink({ icon, label, href }: any) {
  return (
    <a href={href} className="flex items-center justify-between p-4 bg-black/40 border border-cloudo-border/20 rounded-lg hover:bg-cloudo-accent/[0.05] hover:border-cloudo-accent/30 transition-all group">
      <div className="flex items-center gap-3">
        <div className="text-cloudo-muted group-hover:text-cloudo-accent transition-colors">
          {icon}
        </div>
        <span className="text-[10px] font-black text-white uppercase tracking-widest">{label}</span>
      </div>
      <HiOutlineArrowRight className="text-cloudo-muted group-hover:text-white transition-all transform group-hover:translate-x-1" />
    </a>
  );
}
