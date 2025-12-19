'use client';

import { useState, useEffect } from 'react';
import {
  HiOutlineRefresh,
  HiOutlinePlay,
  HiOutlineServer,
  HiOutlineDatabase,
  HiOutlineChip,
  HiOutlineTerminal,
  HiOutlineGlobeAlt,
  HiOutlineClock
} from 'react-icons/hi';

interface WorkerProcess {
  exec_id: string;
  name: string;
  id: string;
  runbook: string;
  status: string;
  startedAt?: string;
  requestedAt?: string;
}

interface Worker {
  PartitionKey: string;
  RowKey: string;
  Queue: string;
  LastSeen: string;
  Region: string;
  Load: number;
}

export function WorkersPanel() {
  const [workers, setWorkers] = useState<Worker[]>([]);
  const [selectedWorker, setSelectedWorker] = useState<string>('');
  const [processes, setProcesses] = useState<WorkerProcess[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingWorkers, setLoadingWorkers] = useState(true);

  useEffect(() => {
    fetchWorkers();
  }, []);

  const fetchWorkers = async () => {
    setLoadingWorkers(true);
    try {
      const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:7071/api';
      const res = await fetch(`http://localhost:7071/api/workers`, {
        headers: {
          'x-cloudo-key': process.env.NEXT_PUBLIC_CLOUDO_KEY || '',
        },
      });
      const data = await res.json();
      setWorkers(Array.isArray(data) ? data : []);
    } catch (error) {
      console.error('Error fetching workers:', error);
      setWorkers([]);
    } finally {
      setLoadingWorkers(false);
    }
  };

  const fetchProcesses = async (worker: string) => {
    if (!worker) return;
    setLoading(true);
    try {
      const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:7071/api';
      const res = await fetch(`${API_URL}/workers/processes?worker=${encodeURIComponent(worker)}`, {
        headers: {
          'x-cloudo-key': process.env.NEXT_PUBLIC_CLOUDO_KEY || '',
        },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const processesData = Array.isArray(data) ? data : (data.runs || data.processes || []);
      setProcesses(processesData);
    } catch (error) {
      console.error('Error fetching processes:', error);
      setProcesses([]);
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

  const workersByCapability = workers.reduce((acc, worker) => {
    const cap = worker.PartitionKey || 'unknown';
    if (!acc[cap]) acc[cap] = [];
    acc[cap].push(worker);
    return acc;
  }, {} as Record<string, Worker[]>);

  return (
    <div className="flex flex-col h-full bg-[#0a0c10] text-cloudo-text font-sans">
      {/* Header Sezionale */}
      <div className="flex items-center justify-between px-8 py-5 border-b border-cloudo-border/20 bg-[#0d1117]/80 backdrop-blur-xl sticky top-0 z-20">
        <div className="flex items-center gap-4">
          <div className="p-2 bg-cloudo-accent/10 rounded-lg border border-cloudo-accent/20">
            <HiOutlineServer className="text-cloudo-accent w-5 h-5" />
          </div>
          <div>
            <h1 className="text-sm font-bold tracking-tight text-white uppercase">Workers Panel</h1>
            <p className="text-[10px] text-cloudo-muted font-black uppercase tracking-[0.2em] opacity-60">Workers & Runtime</p>
          </div>
        </div>
        <button
          onClick={fetchWorkers}
          disabled={loadingWorkers}
          className="bg-white/5 hover:bg-white/10 text-white border border-cloudo-border/40 px-3 py-1.5 rounded-md text-[11px] font-black uppercase tracking-widest transition-all flex items-center gap-2"
        >
          <HiOutlineRefresh className={`w-3.5 h-3.5 ${loadingWorkers ? 'animate-spin' : ''}`} />
          Sync Workers
        </button>
      </div>

      <div className="flex-1 overflow-auto p-8 space-y-10">
        <div className="max-w-[1400px] mx-auto space-y-10">

          {/* Section: Workers Registry */}
          <section className="space-y-6">
            <h2 className="text-[10px] font-black uppercase tracking-[0.3em] text-cloudo-muted border-b border-cloudo-border/10 pb-2">Active Infrastructure</h2>

            {loadingWorkers ? (
              <div className="py-20 text-center flex flex-col items-center gap-3">
                <div className="w-6 h-6 border-2 border-cloudo-accent/30 border-t-cloudo-accent rounded-full animate-spin" />
                <span className="text-[10px] font-black uppercase tracking-widest text-cloudo-muted">Polling Workers...</span>
              </div>
            ) : Object.keys(workersByCapability).length === 0 ? (
              <div className="py-20 text-center border border-dashed border-cloudo-border/30 rounded-xl opacity-30">
                <p className="text-xs uppercase font-black tracking-widest">No active workers found in registry</p>
              </div>
            ) : (
              <div className="space-y-8">
                {Object.entries(workersByCapability).map(([capability, workerList]) => (
                  <div key={capability} className="space-y-4">
                    <div className="flex items-center gap-3">
                      <HiOutlineChip className="text-cloudo-accent w-4 h-4 opacity-70" />
                      <h3 className="text-xs font-black text-white uppercase tracking-widest">{capability}</h3>
                      <div className="h-[1px] flex-1 bg-cloudo-border/10" />
                      <span className="text-[10px] font-mono text-cloudo-muted">{workerList.length} Units</span>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                      {workerList.map((worker) => (
                        <div
                          key={worker.RowKey}
                          className="bg-black/40 border border-cloudo-border/30 rounded-lg p-5 hover:border-cloudo-accent/40 transition-all group"
                        >
                          <div className="flex justify-between items-start mb-4">
                            <code className="text-[11px] font-mono text-cloudo-accent group-hover:text-white transition-colors">
                              {worker.RowKey}
                            </code>
                            <div className="flex items-center gap-1.5">
                              <span className="h-1.5 w-1.5 rounded-full bg-cloudo-ok animate-pulse shadow-[0_0_8px_rgba(34,197,94,0.5)]"></span>
                              <span className="text-[9px] font-black text-cloudo-ok uppercase tracking-tighter">Alive</span>
                            </div>
                          </div>
                          <div className="space-y-2 text-[10px] font-bold text-cloudo-muted uppercase tracking-tight">
                            <div className="flex justify-between border-b border-white/[0.03] pb-1">
                              <span className="opacity-50 flex items-center gap-1"><HiOutlineDatabase className="w-3 h-3"/> Queue</span>
                              <span className="text-white font-mono lowercase">{worker.Queue}</span>
                            </div>
                            <div className="flex justify-between border-b border-white/[0.03] pb-1">
                              <span className="opacity-50 flex items-center gap-1"><HiOutlineGlobeAlt className="w-3 h-3"/> Region</span>
                              <span className="text-white">{worker.Region}</span>
                            </div>
                            <div className="flex justify-between border-b border-white/[0.03] pb-1">
                              <span className="opacity-50 flex items-center gap-1"><HiOutlineClock className="w-3 h-3"/> Load</span>
                              <span className="text-cloudo-accent">{worker.Load}%</span>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* Section: Worker Processes */}
          <section className="space-y-6">
            <h2 className="text-[10px] font-black uppercase tracking-[0.3em] text-cloudo-muted border-b border-cloudo-border/10 pb-2">Runtime Inspection</h2>

            <div className="bg-[#0d1117]/40 border border-cloudo-border/20 rounded-xl p-6">
              <div className="flex flex-col md:flex-row gap-6 items-end">
                <div className="flex-1 space-y-2">
                  <label className="text-[10px] font-black uppercase tracking-widest text-cloudo-muted ml-1">Target Worker Pool</label>
                  <select
                    className="w-full bg-black/40 border border-cloudo-border/50 rounded-md px-4 py-2 text-xs text-white outline-none focus:border-cloudo-accent/60 transition-all appearance-none cursor-pointer"
                    value={selectedWorker}
                    onChange={(e) => setSelectedWorker(e.target.value)}
                    disabled={workers.length === 0}
                  >
                    <option value="">Select an active node...</option>
                    {workers.map((worker) => (
                      <option key={worker.RowKey} value={worker.RowKey}>
                        {worker.RowKey} — {worker.PartitionKey}
                      </option>
                    ))}
                  </select>
                </div>
                <button
                  onClick={() => fetchProcesses(selectedWorker)}
                  disabled={!selectedWorker || loading}
                  className="bg-cloudo-accent hover:bg-cloudo-accent/90 text-white h-9 px-6 rounded-md text-[10px] font-black uppercase tracking-widest transition-all flex items-center gap-2 disabled:opacity-30 shadow-lg shadow-cloudo-accent/10"
                >
                  {loading ? <HiOutlineRefresh className="w-3.5 h-3.5 animate-spin" /> : <HiOutlinePlay className="w-3.5 h-3.5" />}
                  Inspect Node
                </button>
              </div>

              {processes.length > 0 && (
                <div className="mt-8 border border-cloudo-border/20 rounded-lg overflow-hidden bg-black/20">
                  <table className="w-full text-left border-collapse text-[11px]">
                    <thead>
                      <tr className="bg-white/[0.02] border-b border-cloudo-border/20 text-cloudo-muted uppercase font-black tracking-widest">
                        <th className="px-6 py-3">Exec ID</th>
                        <th className="px-6 py-3">Task / Instance</th>
                        <th className="px-6 py-3">Asset</th>
                        <th className="px-6 py-3">Status</th>
                        <th className="px-6 py-3 text-right">Timestamp</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-cloudo-border/10">
                      {processes.map((proc) => (
                        <tr key={proc.exec_id} className="hover:bg-white/[0.01] transition-colors">
                          <td className="px-6 py-4 font-mono text-cloudo-muted">
                            {proc.exec_id?.slice(0, 8)}...
                          </td>
                          <td className="px-6 py-4">
                            <div className="font-bold text-white">{proc.name}</div>
                            <div className="text-[9px] text-cloudo-muted font-mono">{proc.id}</div>
                          </td>
                          <td className="px-6 py-4">
                            <div className="flex items-center gap-2 text-cloudo-accent/70 font-mono">
                              <HiOutlineTerminal className="w-3 h-3 opacity-40" />
                              {proc.runbook}
                            </div>
                          </td>
                          <td className="px-6 py-4">
                            <span className={`status-badge text-[9px] px-2 py-0.5 rounded uppercase font-black tracking-tighter ${getStatusBadgeClass(proc.status)}`}>
                              {proc.status}
                            </span>
                          </td>
                          <td className="px-6 py-4 text-right text-cloudo-muted opacity-60">
                            {(proc.startedAt || proc.requestedAt || '-').replace('T', ' ').split('.')[0]}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {processes.length === 0 && selectedWorker && !loading && (
                <div className="mt-8 py-16 text-center border border-dashed border-cloudo-border/20 rounded-xl">
                  <HiOutlineDatabase className="h-8 w-8 text-cloudo-muted mx-auto mb-3 opacity-20" />
                  <p className="text-[10px] uppercase font-black tracking-widest text-cloudo-muted">No active processes detected on this node</p>
                </div>
              )}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
