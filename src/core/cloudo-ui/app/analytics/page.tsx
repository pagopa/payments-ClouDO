'use client';

import { useEffect, useState } from 'react';
import { cloudoFetch } from '@/lib/api';
import {
  HiOutlineChartBar,
  HiOutlineClock,
  HiOutlineTerminal,
  HiOutlineExclamationCircle,
  HiOutlineCheckCircle,
  HiOutlineTrendingUp,
  HiOutlineTrendingDown,
  HiOutlineLightningBolt,
  HiOutlineCalendar
} from "react-icons/hi";
import { MdAnalytics } from "react-icons/md";

interface AnalyticsData {
  totalRequests: number;
  successRate: number;
  avgLatency: number;
  errorCount: number;
  requestsByStatus: Record<string, number>;
  requestsByHour: Record<string, number>;
  topRunbooks: { name: string; count: number; success: number }[];
}

export default function AnalyticsPage() {
  const [loading, setLoading] = useState(true);
  const [timeRange, setTimeRange] = useState('24h');
  const [data, setData] = useState<AnalyticsData>({
    totalRequests: 0,
    successRate: 0,
    avgLatency: 0,
    errorCount: 0,
    requestsByStatus: {},
    requestsByHour: {},
    topRunbooks: []
  });

  useEffect(() => {
    fetchAnalytics();
  }, [timeRange]);

  const fetchAnalytics = async () => {
    setLoading(true);
    try {
      const days = timeRange === '24h' ? 1 : timeRange === '7d' ? 7 : 30;
      const today = new Date();

      let allLogs: any[] = [];

      for (let i = 0; i < days; i++) {
        const date = new Date(today);
        date.setDate(today.getDate() - i);
        const partitionKey = `${date.getFullYear()}${String(date.getMonth() + 1).padStart(2, '0')}${String(date.getDate()).padStart(2, '0')}`;

        try {
          const res = await cloudoFetch(`/logs/query?partitionKey=${partitionKey}&limit=1000`);
          if (res.ok) {
            const result = await res.json();
            allLogs = [...allLogs, ...(result.items || [])];
          }
        } catch (e) {
          console.error(`Failed to fetch logs for ${partitionKey}`, e);
        }
      }

      // Group by ExecId to calculate duration
      const execMap: Record<string, { start?: Date; end?: Date; status: string; runbook: string; requestedAt: string }> = {};

      allLogs.forEach(log => {
        const id = log.ExecId;
        if (!id) return;

        if (!execMap[id]) {
          execMap[id] = {
            status: 'unknown',
            runbook: log.Runbook || 'Unknown',
            requestedAt: log.RequestedAt
          };
        }

        const currentStatus = (log.Status || '').toLowerCase();
        const timestamp = new Date(log.RequestedAt);

        if (['accepted', 'pending', 'routed'].includes(currentStatus)) {
          if (!execMap[id].start || timestamp < execMap[id].start) {
            execMap[id].start = timestamp;
          }
        }

        if (['succeeded', 'completed', 'failed', 'error'].includes(currentStatus)) {
          if (!execMap[id].end || timestamp > execMap[id].end) {
            execMap[id].end = timestamp;
            execMap[id].status = currentStatus;
          }
        }
      });

      const processedExecutions = Object.values(execMap);
      const statusMap: Record<string, number> = {};
      const runbookMap: Record<string, { count: number; success: number }> = {};
      const hourMap: Record<string, number> = {};
      let totalLatency = 0;
      let latencyCount = 0;
      let succeeded = 0;

      processedExecutions.forEach(exec => {
        const status = exec.status;
        statusMap[status] = (statusMap[status] || 0) + 1;

        if (['succeeded', 'completed'].includes(status)) succeeded++;

        const rb = exec.runbook;
        if (!runbookMap[rb]) runbookMap[rb] = { count: 0, success: 0 };
        runbookMap[rb].count++;
        if (['succeeded', 'completed'].includes(status)) runbookMap[rb].success++;

        // Latency
        if (exec.start && exec.end) {
          const duration = exec.end.getTime() - exec.start.getTime();
          if (duration > 0) {
            totalLatency += duration;
            latencyCount++;
          }
        }

        // Timeline aggregation (by hour if 24h, else by day)
        const date = new Date(exec.requestedAt);
        let timeKey = "";
        if (timeRange === '24h') {
           timeKey = `${date.getHours()}:00`;
        } else {
           timeKey = date.toISOString().split('T')[0];
        }
        hourMap[timeKey] = (hourMap[timeKey] || 0) + 1;
      });

      const topRunbooks = Object.entries(runbookMap)
        .map(([name, stats]) => ({ name, ...stats }))
        .sort((a, b) => b.count - a.count)
        .slice(0, 5);

      setData({
        totalRequests: processedExecutions.length,
        successRate: processedExecutions.length > 0 ? (succeeded / processedExecutions.length) * 100 : 0,
        avgLatency: latencyCount > 0 ? Math.round(totalLatency / latencyCount) : 0,
        errorCount: (statusMap['failed'] || 0) + (statusMap['error'] || 0),
        requestsByStatus: statusMap,
        requestsByHour: hourMap,
        topRunbooks
      });

    } catch (error) {
      console.error('Error fetching analytics:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-full bg-cloudo-dark">
        <div className="w-8 h-8 border-2 border-cloudo-accent/30 border-t-cloudo-accent rounded-full animate-spin mb-4" />
        <span className="text-xs font-black uppercase tracking-[0.3em] text-cloudo-muted">Calculating Analytics...</span>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-cloudo-dark text-cloudo-text font-mono">
      {/* Header Bar */}
      <div className="flex items-center justify-between px-8 py-4 border-b border-cloudo-border bg-cloudo-panel sticky top-0 z-20">
        <div className="flex items-center gap-4 shrink-0">
          <div className="p-2 bg-cloudo-accent/5 border border-cloudo-accent/20 shrink-0">
            <HiOutlineChartBar className="text-cloudo-accent w-5 h-5" />
          </div>
          <div>
            <h1 className="text-sm font-black tracking-[0.2em] text-cloudo-text uppercase">Advanced Analytics</h1>
            <p className="text-[11px] text-cloudo-muted font-bold uppercase tracking-[0.3em] opacity-70">Performance & Diagnostics</p>
          </div>
        </div>

        {/* Time Picker */}
        <div className="flex items-center gap-2 bg-cloudo-accent/10 border border-cloudo-border p-1">
          {['24h', '7d', '30d'].map((range) => (
            <button
              key={range}
              onClick={() => setTimeRange(range)}
              className={`px-4 py-1.5 text-[11px] font-black uppercase tracking-widest transition-all ${
                timeRange === range
                  ? 'bg-cloudo-accent text-cloudo-dark'
                  : 'text-cloudo-muted hover:text-cloudo-text'
              }`}
            >
              {range}
            </button>
          ))}
          <div className="w-px h-4 bg-cloudo-border mx-2" />
          <div className="flex items-center gap-2 px-3 text-cloudo-muted/70">
            <HiOutlineCalendar className="w-4 h-4" />
            <span className="text-[10px] font-bold uppercase tracking-tighter">Custom Range</span>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-8">
        <div className="max-w-[1400px] mx-auto space-y-8">

          {/* Main KPI Row */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <MetricCard
              title="Throughput"
              value={data.totalRequests}
              subValue="Requests Processed"
              icon={<HiOutlineLightningBolt />}
              trend="LIVE"
              positive={true}
            />
            <MetricCard
              title="Success Rate"
              value={`${data.successRate.toFixed(1)}%`}
              subValue="Overall Reliability"
              icon={<HiOutlineCheckCircle />}
              trend={data.successRate > 95 ? "OPTIMAL" : "STABLE"}
              positive={true}
              color="text-cloudo-ok"
            />
            <MetricCard
              title="Avg Latency"
              value={`${data.avgLatency}ms`}
              subValue="Mean Response Time"
              icon={<HiOutlineClock />}
              trend={data.avgLatency < 500 ? "FAST" : "NOMINAL"}
              positive={true}
            />
            <MetricCard
              title="Error Volume"
              value={data.errorCount}
              subValue="Critical Incidents"
              icon={<HiOutlineExclamationCircle />}
              trend={data.errorCount === 0 ? "ZERO" : "WARN"}
              positive={data.errorCount === 0}
              color={data.errorCount > 0 ? "text-cloudo-err" : "text-cloudo-ok"}
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Status Distribution */}
            <div className="lg:col-span-1 space-y-4">
              <SectionHeader title="Status Distribution" />
              <div className="bg-cloudo-panel border border-cloudo-border p-6 space-y-4">
                {Object.entries(data.requestsByStatus).map(([status, count]) => (
                  <div key={status} className="space-y-1">
                    <div className="flex justify-between text-[11px] font-bold uppercase tracking-widest">
                      <span className="text-cloudo-muted">{status}</span>
                      <span className="text-cloudo-text">{count} ({((count / data.totalRequests) * 100).toFixed(1)}%)</span>
                    </div>
                    <div className="w-full h-1 bg-white/5 overflow-hidden">
                      <div
                        className={`h-full ${
                          ['succeeded', 'completed'].includes(status) ? 'bg-cloudo-ok' :
                          ['failed', 'error'].includes(status) ? 'bg-cloudo-err' :
                          'bg-cloudo-accent'
                        }`}
                        style={{ width: `${(count / data.totalRequests) * 100}%` }}
                      />
                    </div>
                  </div>
                ))}
                {Object.keys(data.requestsByStatus).length === 0 && (
                  <div className="py-10 text-center text-cloudo-muted/60 text-xs italic">NO_DATA_AVAILABLE</div>
                )}
              </div>
            </div>

            {/* Top Runbooks Performance */}
            <div className="lg:col-span-2 space-y-4">
              <SectionHeader title="Top Runbooks Performance" />
              <div className="bg-cloudo-panel border border-cloudo-border overflow-hidden">
                <table className="w-full text-left border-collapse text-sm">
                  <thead className="bg-cloudo-panel-2 border-b border-cloudo-border">
                    <tr className="text-[11px] font-black text-cloudo-muted uppercase tracking-[0.3em]">
                      <th className="px-6 py-4">Runbook_ID</th>
                      <th className="px-6 py-4">Invocations</th>
                      <th className="px-6 py-4">Success_Rate</th>
                      <th className="px-6 py-4 text-right">Trend</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-cloudo-border/50">
                    {data.topRunbooks.map((rb, i) => (
                      <tr key={i} className="hover:bg-white/[0.02] transition-colors">
                        <td className="px-6 py-4 font-bold text-cloudo-text uppercase tracking-wider">{rb.name}</td>
                        <td className="px-6 py-4 font-mono text-cloudo-muted">{rb.count}</td>
                        <td className="px-6 py-4">
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-xs">{((rb.success / rb.count) * 100).toFixed(1)}%</span>
                            <div className="flex-1 max-w-[100px] h-1 bg-white/5">
                              <div className="h-full bg-cloudo-ok" style={{ width: `${(rb.success / rb.count) * 100}%` }} />
                            </div>
                          </div>
                        </td>
                        <td className="px-6 py-4 text-right">
                          <HiOutlineTrendingUp className="inline text-cloudo-ok w-4 h-4" />
                        </td>
                      </tr>
                    ))}
                    {data.topRunbooks.length === 0 && (
                      <tr><td colSpan={4} className="py-20 text-center text-cloudo-muted/60 text-xs italic">NO_ACTIVE_RUNBOOKS</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {/* Activity Timeline */}
          <div className="space-y-4">
            <SectionHeader title="Traffic Density Timeline" />
            <div className="bg-cloudo-panel border border-cloudo-border p-8 h-48 flex items-end gap-1">
              {Object.entries(data.requestsByHour).length > 0 ? (
                // Ordiniamo le chiavi (ore o giorni)
                Object.entries(data.requestsByHour)
                  .sort(([a], [b]) => a.localeCompare(b))
                  .map(([key, count], i, arr) => {
                    const maxCount = Math.max(...Object.values(data.requestsByHour));
                    const height = (count / maxCount) * 100;
                    return (
                      <div
                        key={key}
                        className="flex-1 bg-cloudo-accent/20 hover:bg-cloudo-accent transition-all group relative"
                        style={{ height: `${height}%` }}
                      >
                        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 bg-cloudo-accent text-cloudo-dark text-[10px] font-black px-1.5 py-0.5 opacity-0 group-hover:opacity-400 transition-opacity whitespace-nowrap z-10">
                          {key}: {count} REQ
                        </div>
                      </div>
                    );
                  })
              ) : (
                <div className="w-full h-full flex items-center justify-center text-cloudo-muted/80 italic text-xs">NO_TIMELINE_DATA</div>
              )}
            </div>
            <div className="flex justify-between px-2 text-[10px] font-black text-cloudo-muted/70 uppercase tracking-[0.2em]">
              <span>{timeRange === '24h' ? '00:00' : 'OLDEST_DATA'}</span>
              <span>{timeRange === '24h' ? '12:00' : 'MID_PERIOD'}</span>
              <span>{timeRange === '24h' ? '23:00' : 'RECENT_DATA'}</span>
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}

function MetricCard({ title, value, subValue, icon, trend, positive, color = "text-cloudo-text" }: any) {
  return (
    <div className="bg-cloudo-panel border border-cloudo-border p-6 relative overflow-hidden group">
      <div className="absolute top-0 right-0 p-4 opacity-40 group-hover:opacity-50 transition-opacity text-4xl">
        {icon}
      </div>
      <p className="text-[11px] font-black uppercase tracking-[0.2em] text-cloudo-muted/60 mb-1">{title}</p>
      <div className="flex items-baseline gap-3">
        <h3 className={`text-3xl font-black tracking-tighter ${color}`}>{value}</h3>
        <span className={`text-[10px] font-bold px-1.5 py-0.5 border ${
          positive ? 'border-cloudo-ok/30 text-cloudo-ok bg-cloudo-ok/5' : 'border-cloudo-err/30 text-cloudo-err bg-cloudo-err/5'
        }`}>
          {trend}
        </span>
      </div>
      <p className="text-[10px] font-bold text-cloudo-muted/70 uppercase mt-2 tracking-widest">{subValue}</p>
    </div>
  );
}

function SectionHeader({ title }: { title: string }) {
  return (
    <div className="flex items-center gap-3">
      <div className="w-1.5 h-4 bg-cloudo-accent" />
      <h2 className="text-sm font-black uppercase tracking-[0.4em] text-cloudo-text">{title}</h2>
    </div>
  );
}
