'use client';

import { useEffect, useState } from 'react';
import { cloudoFetch } from '@/lib/api';
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
      const workersRes = await cloudoFetch(`/workers`);

      if (!workersRes.ok) throw new Error('Backend unreachable');

      const workers = await workersRes.json();
      const activeWorkers = Array.isArray(workers) ? workers : [];

      const processesPromises = activeWorkers.map(async (w: any) => {
        try {
          const res = await cloudoFetch(`/workers/processes?worker=${encodeURIComponent(w.RowKey)}`);
          if (!res.ok) return [];
          const data = await res.json();
          const procList = Array.isArray(data) ? data : (data.runs || data.processes || []);
          return procList.map((p: any) => ({ ...p, workerNode: w.RowKey }));
        } catch { return []; }
      });

      const allLiveProcesses = (await Promise.all(processesPromises)).flat();

      const today = new Date();
      const partitionKey = `${today.getFullYear()}${String(today.getMonth() + 1).padStart(2, '0')}${String(today.getDate()).padStart(2, '0')}`;
      const logsRes = await cloudoFetch(`/logs/query?partitionKey=${partitionKey}&limit=5000`);
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

      const failed = finalExecutions.filter((e: any) =>
        ['failed', 'error'].includes((e.Status || '').toLowerCase())
      ).length;

      const oneHourAgo = Date.now() - (60 * 60 * 1000); // Timestamp di un'ora fa

      const pending = finalExecutions.filter((e: any) => {
        const isPending = ['pending'].includes((e.Status || '').toLowerCase());
        const executionTime = new Date(e.CreatedAt).getTime();
        return isPending && executionTime > oneHourAgo;
      }).length;

      const sortedExecutions = [...finalExecutions]
        .sort((a, b) => new Date(b.RequestedAt || 0).getTime() - new Date(a.RequestedAt || 0).getTime())
        .slice(0, 5);

      const totalFinished = succeeded + failed;
      setStats({
        totalExecutions: finalExecutions.length,
        successRate: totalFinished > 0 ? +((succeeded / totalFinished) * 100).toFixed(2) : 0,
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
      <div className="flex flex-col items-center justify-center h-full bg-cloudo-dark">
        <div className="w-8 h-8 border-2 border-cloudo-accent/30 border-t-cloudo-accent rounded-full animate-spin mb-4" />
        <span className="text-xs font-black uppercase tracking-[0.3em] text-cloudo-muted">Booting Systems...</span>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-cloudo-dark text-cloudo-text font-mono selection:bg-cloudo-accent/30">
      {/* Header Bar */}
      <div className="flex items-center justify-between px-8 py-4 border-b border-cloudo-border bg-cloudo-panel sticky top-0 z-20">
        <div className="flex items-center gap-4 shrink-0">
          <div className="p-2 bg-cloudo-accent/5 border border-cloudo-accent/20 shrink-0">
            <MdOutlineSpaceDashboard className="text-cloudo-accent w-5 h-5" />
          </div>
          <div>
            <h1 className="text-sm font-black tracking-[0.2em] text-cloudo-text uppercase">Operations Dashboard</h1>
            <p className="text-[11px] text-cloudo-muted font-bold uppercase tracking-[0.3em] opacity-70">System Telemetry // LIVE</p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 px-3 py-1 bg-cloudo-accent/10 border border-cloudo-border">
            <span className="relative flex h-2 w-2">
              <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-70 ${isBackendDown ? 'bg-cloudo-err' : 'bg-cloudo-ok'}`}></span>
              <span className={`relative inline-flex rounded-full h-2 w-2 ${isBackendDown ? 'bg-cloudo-err' : 'bg-cloudo-ok'}`}></span>
            </span>
            <span className={`text-[11px] font-black uppercase tracking-widest ${isBackendDown ? 'text-cloudo-err animate-pulse' : 'text-cloudo-muted'}`}>
              {isBackendDown ? 'CONNECTION_LOST' : 'UPLINK_STABLE | Live Stream • 30s'}
            </span>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-8 space-y-8">
        <div className="max-w-[1400px] mx-auto space-y-8">

          {/* Stats Cards Row */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard
              title="Workload Executions"
              value={stats.totalExecutions}
              icon={<HiOutlineTerminal className="text-cloudo-accent" />}
              status="TOTAL_LOAD"
              trend={[10, 20, 15, 30, 25, 40, 35]}
            />
            <StatCard
              title="Success Rate"
              value={`${stats.successRate}%`}
              icon={<HiOutlineCheckCircle className="text-cloudo-ok" />}
              status="COMPLIANCE_RATIO"
              trend={[95, 98, 97, 99, 100, 98, 99]}
            />
            <StatCard
              title="Compute Nodes"
              value={stats.activeWorkers}
              icon={<HiOutlineServer className="text-cloudo-accent" />}
              status="ACTIVE_CAPACITY"
              trend={[2, 3, 3, 4, 4, 4, 4]}
            />
            <StatCard
              title="Governance Queue"
              value={stats.pendingApprovals}
              icon={<HiOutlineClock className="text-cloudo-warn" />}
              status="AWAITING_SIG"
              highlight={stats.pendingApprovals > 0}
              trend={[5, 2, 4, 1, 0, 2, 1]}
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Operational Stream e Live Worker Processes */}
            <div className="lg:col-span-2 space-y-4">
              <div className="flex items-center gap-3">
                <div className="w-1.5 h-4 bg-cloudo-accent" />
                <h2 className="text-sm font-black uppercase tracking-[0.4em] text-cloudo-text">Operational Stream</h2>
              </div>
              <div className="bg-cloudo-panel border border-cloudo-border overflow-hidden">
                <table className="w-full text-left border-collapse text-sm">
                  <thead className="bg-cloudo-panel-2 border-b border-cloudo-border">
                    <tr className="text-[11px] font-black text-cloudo-muted uppercase tracking-[0.3em]">
                      <th className="px-6 py-4">Event_ID</th>
                      <th className="px-6 py-4">Asset_Path</th>
                      <th className="px-6 py-4">Status</th>
                      <th className="px-6 py-4 text-right">Timestamp</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-cloudo-border/50">
                    {stats.recentExecutions.length === 0 ? (
                      <tr><td colSpan={4} className="py-20 text-center text-sm uppercase font-bold text-cloudo-muted italic opacity-60">NO_DATA_STREAM</td></tr>
                    ) : (
                      stats.recentExecutions.map((exec: any) => (
                        <tr key={exec.RowKey} className="group hover:bg-white/[0.02] transition-colors">
                          <td className="px-6 py-4 font-mono">
                            <div className="text-cloudo-text font-bold">{exec.ExecId?.slice(0, 8)}</div>
                            <div className="text-[11px] text-cloudo-muted/60">{exec.Name || 'SYS_TASK'}</div>
                          </td>
                          <td className="px-6 py-4 font-mono text-cloudo-accent/60">
                            {exec.Runbook || '--'}
                          </td>
                          <td className="px-6 py-4">
                            <StatusIndicator status={exec.Status} />
                          </td>
                          <td className="px-6 py-4 text-right font-mono text-cloudo-muted">
                             {new Date(exec.RequestedAt).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', second:'2-digit', hour12: false})}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="space-y-4">
              <div className="flex items-center gap-3">
                <div className="w-1.5 h-4 bg-cloudo-accent" />
                <h2 className="text-sm font-black uppercase tracking-[0.4em] text-cloudo-text">Runtime Processes</h2>
              </div>
              <div className="bg-cloudo-panel border border-cloudo-border p-4 space-y-3 min-h-[320px] max-h-[500px] overflow-y-auto custom-scrollbar">
                {stats.liveProcesses.length === 0 ? (
                  <div className="py-20 text-center opacity-50 flex flex-col items-center gap-3">
                    <HiOutlineServer className="w-8 h-8" />
                    <span className="text-[11px] font-black uppercase tracking-widest text-center">IDLE_STATE<br/>NO_ACTIVE_WORKLOADS</span>
                  </div>
                ) : (
                  stats.liveProcesses.map((proc: any) => (
                    <div key={proc.exec_id} className="bg-cloudo-accent/10 border border-cloudo-border p-3 border-l-2 border-l-cloudo-accent group hover:bg-cloudo-accent/5 transition-all">
                      <div className="flex justify-between items-start mb-2">
                        <div className="flex items-center gap-2">
                          <div className="w-1.5 h-1.5 bg-cloudo-accent animate-pulse" />
                          <span className="text-sm font-bold text-cloudo-text truncate max-w-[140px] uppercase tracking-widest">{proc.name}</span>
                        </div>
                        <span className="text-[11px] font-mono text-cloudo-muted/60">{proc.workerNode}</span>
                      </div>
                      <div className="flex justify-between items-center text-[11px] text-cloudo-muted uppercase font-bold tracking-widest">
                        <span className="flex items-center gap-1 opacity-60"><HiOutlineTerminal className="w-4 h-4"/> {proc.runbook}</span>
                        <span className="opacity-60">{proc.exec_id.slice(0, 8)}</span>
                      </div>
                    </div>
                  ))
                )}
              </div>

              <div className="grid grid-cols-1 gap-2 pt-4">
                <QuickLink icon={<HiOutlineDatabase />} label="Registry" href="/schemas" />
                <QuickLink icon={<HiOutlineClock />} label="Schedules" href="/schedules" />
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
    <div className="bg-cloudo-panel border border-cloudo-border p-6 flex items-center justify-between relative overflow-hidden group">
      <div className="absolute top-0 left-0 w-[2px] h-full bg-cloudo-accent/20" />
      <div className="relative z-10">
        <p className="text-[11px] font-black uppercase tracking-[0.2em] text-cloudo-muted/80">{title}</p>
        <p className={`text-3xl font-black mt-1 ${highlight ? 'text-cloudo-warn' : 'text-cloudo-text'} tracking-tighter`}>{value}</p>
        <p className="text-[11px] font-bold text-cloudo-muted/80 uppercase mt-2 tracking-[0.1em]">{status}</p>
      </div>
      <div className="p-3 bg-cloudo-accent/10 border border-cloudo-border text-xl shrink-0">
        {icon}
      </div>
    </div>
  );
}

function StatusIndicator({ status }: { status: string }) {
  const s = (status || '').toLowerCase();
  const colors: Record<string, string> = {
    succeeded: 'bg-cloudo-ok',
    running: 'bg-cloudo-accent',
    routed: 'bg-cloudo-accent',
    failed: 'bg-cloudo-err',
    error: 'bg-cloudo-err',
    pending: 'bg-cloudo-warn',
    accepted: 'bg-cloudo-warn',
  };

  return (
    <div className="flex items-center gap-2">
      <div className={`w-2 h-2 ${colors[s] || 'bg-cloudo-muted'} ${s === 'running' ? 'animate-pulse' : ''}`} />
      <span className="text-xs font-black uppercase tracking-widest text-cloudo-text/80">{status}</span>
    </div>
  );
}

function QuickLink({ icon, label, href }: any) {
  return (
    <a href={href} className="flex items-center justify-between p-4 bg-cloudo-panel border border-cloudo-border hover:bg-cloudo-accent/5 hover:border-cloudo-accent transition-all group">
      <div className="flex items-center gap-3 min-w-0">
        <div className="text-cloudo-muted group-hover:text-cloudo-accent transition-colors shrink-0">
          {icon}
        </div>
        <span className="text-xs font-black text-cloudo-text uppercase tracking-[0.2em] truncate">{label}</span>
      </div>
      <HiOutlineArrowRight className="text-cloudo-muted/70 group-hover:text-cloudo-accent transition-all transform group-hover:translate-x-1 shrink-0 w-4 h-4" />
    </a>
  );
}
