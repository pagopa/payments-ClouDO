"use client";

import { useState, useEffect, useCallback } from "react";
import { cloudoFetch } from "@/lib/api";
import {
  HiOutlineSearch,
  HiOutlineDatabase,
  HiOutlineTerminal,
  HiOutlineX,
  HiOutlineRefresh,
  HiOutlineFilter,
  HiOutlineClipboardCheck,
  HiOutlineClipboard,
  HiOutlineTag,
  HiOutlineFingerPrint,
  HiOutlineCalendar,
} from "react-icons/hi";
import {
  parseDate,
  today,
  getLocalTimeZone,
  CalendarDate,
} from "@internationalized/date";

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
  Initiator?: string;
  Worker?: string;
}

export function LogsPanel() {
  const [partitionKey, setPartitionKey] = useState(
    today(getLocalTimeZone()).toString().replace(/-/g, ""),
  );
  const [dateValue, setDateValue] = useState<CalendarDate | null>(
    today(getLocalTimeZone()),
  );
  const [execId, setExecId] = useState("");
  const [status, setStatus] = useState("");
  const [query, setQuery] = useState("");
  const [limit, setLimit] = useState("200");
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedLog, setSelectedLog] = useState<LogEntry | null>(null);
  const [copied, setCopied] = useState(false);

  const setTodayDate = () => {
    const t = today(getLocalTimeZone());
    setDateValue(t);
    setPartitionKey(t.toString().replace(/-/g, ""));
  };

  const runQuery = useCallback(
    async (overrideParams?: { partitionKey?: string }) => {
      setLoading(true);
      try {
        const params = new URLSearchParams();
        const pKey =
          overrideParams?.partitionKey !== undefined
            ? overrideParams.partitionKey
            : partitionKey;

        if (pKey) params.set("partitionKey", pKey);
        if (execId) params.set("execId", execId);
        if (status) params.set("status", status);
        if (query) params.set("q", query);
        if (limit) params.set("limit", limit);

        const res = await cloudoFetch(`/logs/query?${params}`);
        const data = await res.json();
        const rawLogs = data.items || [];

        // Group by ExecId and keep only the final status
        const groupedByExecId = new Map<string, LogEntry>();
        const statusPriority: Record<string, number> = {
          succeeded: 5,
          completed: 5,
          failed: 4,
          error: 4,
          running: 3,
          skipped: 3,
          rejected: 3,
          stopped: 3,
          accepted: 2,
          pending: 1,
        };

        rawLogs.forEach((log: LogEntry) => {
          const execId = log.ExecId;
          const existing = groupedByExecId.get(execId);

          if (!existing) {
            groupedByExecId.set(execId, log);
          } else {
            // Keep the entry with higher priority status
            const currentPriority =
              statusPriority[log.Status?.toLowerCase()] || 0;
            const existingPriority =
              statusPriority[existing.Status?.toLowerCase()] || 0;

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

        setLogs(
          Array.from(groupedByExecId.values()).sort((a, b) =>
            b.RequestedAt.localeCompare(a.RequestedAt),
          ),
        );
      } catch (error) {
        console.error("Error fetching logs:", error);
        setLogs([]);
      } finally {
        setLoading(false);
      }
    },
    [partitionKey, execId, status, query, limit],
  );

  useEffect(() => {
    runQuery();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Run only on mount

  const handleReset = () => {
    setExecId("");
    setStatus("");
    setQuery("");
    setLimit("200");
    setLogs([]);
    setSelectedLog(null);
    setTodayDate();
  };

  const handleDateChange = (val: CalendarDate | null) => {
    setDateValue(val);
    if (val) {
      const pk = val.toString().replace(/-/g, "");
      setPartitionKey(pk);
      runQuery({ partitionKey: pk });
    } else {
      setPartitionKey("");
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      e.preventDefault();
      runQuery();
    }
  };

  const getStatusBadgeClass = (status: string) => {
    const s = status.toLowerCase();
    if (s === "succeeded" || s === "completed")
      return "border-cloudo-ok/30 text-cloudo-ok bg-cloudo-ok/5";
    if (s === "running" || s === "accepted")
      return "border-cloudo-accent/30 text-cloudo-accent bg-cloudo-accent/5";
    if (s === "failed" || s === "error")
      return "border-cloudo-err/30 text-cloudo-err bg-cloudo-err/5";
    if (s === "rejected")
      return "border-cloudo-err/30 text-cloudo-err bg-cloudo-err/5";
    if (s === "pending")
      return "border-cloudo-warn/30 text-cloudo-warn bg-cloudo-warn/5";
    if (s === "stopped")
      return "border-cloudo-warn/30 text-cloudo-warn bg-cloudo-warn/5";
    return "border-cloudo-muted/60 text-cloudo-muted bg-cloudo-muted/5";
  };

  const formatLogContent = (content: string) => {
    if (!content)
      return (
        <span className="italic text-cloudo-muted opacity-20">
          No log data available
        </span>
      );
    return content.split("\n").map((line, i) => {
      let color = "text-cloudo-text/80";
      if (
        line.toUpperCase().includes("ERROR") ||
        line.toUpperCase().includes("EXCEPTION")
      )
        color = "text-red-600";
      if (line.toUpperCase().includes("WARN")) color = "text-yellow-600";
      if (line.toUpperCase().includes("INFO")) color = "text-blue-600";
      return (
        <div
          key={i}
          className={`${color} font-mono text-xs leading-relaxed py-1 border-b border-white/[0.02] break-all`}
        >
          {line}
        </div>
      );
    });
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="flex flex-col lg:flex-row gap-4 h-full bg-cloudo-dark font-mono">
      {/* Search & List Section */}
      <div
        className={`flex flex-col gap-4 overflow-hidden transition-all duration-500 ${
          selectedLog ? "lg:max-w-[40%]" : "w-full"
        }`}
      >
        {/* Filters Card */}
        <div className="bg-cloudo-panel border border-cloudo-border shadow-none">
          <div className="px-6 py-4 border-b border-cloudo-border flex justify-between items-center bg-cloudo-panel-2">
            <div className="flex items-center gap-3 shrink-0">
              <HiOutlineDatabase className="text-cloudo-accent w-5 h-5 shrink-0" />
              <h2 className="text-sm font-black uppercase tracking-[0.2em] text-cloudo-text truncate">
                Log Explorer
              </h2>
            </div>
            <button
              onClick={handleReset}
              className="text-[11px] font-black uppercase tracking-widest text-cloudo-muted hover:text-cloudo-text transition-colors border border-cloudo-border px-2 py-1"
            >
              Reset
            </button>
          </div>

          <div className="p-6 space-y-6">
            <div className="grid grid-cols-2 md:grid-cols-3 gap-6">
              <div className="space-y-2">
                <label className="text-[11px] font-black uppercase tracking-widest text-cloudo-muted ml-1 block">
                  Date
                </label>
                <div className="relative group">
                  <HiOutlineCalendar className="absolute left-3 top-1/2 -translate-y-1/2 text-cloudo-muted/70 w-4 h-4 group-focus-within:text-cloudo-accent transition-colors pointer-events-none z-10" />
                  <input
                    type="date"
                    className="input input-icon pl-10 relative bg-transparent border border-cloudo-border text-cloudo-text w-full py-2 px-3 leading-tight focus:outline-none focus:border-cloudo-accent transition-colors block"
                    value={dateValue ? dateValue.toString() : ""}
                    onChange={(e) =>
                      handleDateChange(
                        e.target.value ? parseDate(e.target.value) : null,
                      )
                    }
                    onKeyDown={handleKeyDown}
                    onClick={(e) => e.currentTarget.showPicker?.()}
                  />
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-[11px] font-black uppercase tracking-widest text-cloudo-muted ml-1 block">
                  State
                </label>
                <div className="relative group">
                  <HiOutlineTag className="absolute left-3 top-1/2 -translate-y-1/2 text-cloudo-muted/70 w-4 h-4 group-focus-within:text-cloudo-accent transition-colors pointer-events-none z-10" />
                  <select
                    className="input input-icon pl-10 appearance-none relative w-full"
                    value={status}
                    onChange={(e) => setStatus(e.target.value)}
                    onKeyDown={handleKeyDown}
                  >
                    <option value="">ALL_EVENTS</option>
                    <option value="pending">PENDING</option>
                    <option value="accepted">ACCEPTED</option>
                    <option value="running">RUNNING</option>
                    <option value="succeeded">SUCCEEDED</option>
                    <option value="failed">FAILED</option>
                    <option value="rejected">REJECTED</option>
                    <option value="error">ERROR</option>
                  </select>
                </div>
              </div>
              <div className="space-y-2">
                <label className="text-[11px] font-black uppercase tracking-widest text-cloudo-muted ml-1 block">
                  Exec_ID
                </label>
                <div className="relative group">
                  <HiOutlineFingerPrint className="absolute left-3 top-1/2 -translate-y-1/2 text-cloudo-muted/70 w-4 h-4 group-focus-within:text-cloudo-accent transition-colors pointer-events-none z-10" />
                  <input
                    type="text"
                    className="input input-icon pl-10 relative w-full"
                    placeholder="Execution ID..."
                    value={execId}
                    onChange={(e) => setExecId(e.target.value)}
                    onKeyDown={handleKeyDown}
                  />
                </div>
              </div>
              <div className="col-span-2 md:col-span-1 space-y-2">
                <label className="text-[11px] font-black uppercase tracking-widest text-cloudo-muted ml-1 block">
                  Search_Term
                </label>
                <div className="relative group">
                  <HiOutlineSearch className="absolute left-3 top-1/2 -translate-y-1/2 text-cloudo-muted/70 w-4 h-4 group-focus-within:text-cloudo-accent transition-colors pointer-events-none z-10" />
                  <input
                    type="text"
                    className="input input-icon pl-10 relative w-full"
                    placeholder="Keywords in logs..."
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    onKeyDown={handleKeyDown}
                  />
                </div>
              </div>
              <div className="space-y-2">
                <label className="text-[11px] font-black uppercase tracking-widest text-cloudo-muted ml-1 block">
                  Limit
                </label>
                <div className="relative group">
                  <HiOutlineDatabase className="absolute left-3 top-1/2 -translate-y-1/2 text-cloudo-muted/70 w-4 h-4 group-focus-within:text-cloudo-accent transition-colors pointer-events-none z-10" />
                  <input
                    type="number"
                    className="input input-icon pl-10 relative w-full"
                    placeholder="200"
                    value={limit}
                    onChange={(e) => setLimit(e.target.value)}
                    onKeyDown={handleKeyDown}
                  />
                </div>
              </div>
            </div>

            <button
              onClick={() => runQuery()}
              disabled={loading}
              className="w-full btn btn-primary py-3"
              onKeyDown={handleKeyDown}
            >
              {loading ? (
                <HiOutlineRefresh className="animate-spin w-3.5 h-3.5" />
              ) : (
                <HiOutlineFilter className="w-3.5 h-3.5" />
              )}
              {loading ? "Executing..." : "Run Diagnostics"}
            </button>
          </div>
        </div>

        {/* Results List Card */}
        <div className="bg-cloudo-panel border border-cloudo-border flex-1 overflow-hidden flex flex-col">
          {logs.length > 0 && (
            <div className="px-6 py-2 border-b border-cloudo-border bg-cloudo-panel-2 flex justify-between items-center">
              <span className="text-[10px] font-black uppercase tracking-widest text-cloudo-muted">
                Displaying {logs.length} unique execution
                {logs.length !== 1 ? "s" : ""}
                {limit && ` (limited to ${limit} raw logs)`}
              </span>
            </div>
          )}
          <div className="overflow-y-auto custom-scrollbar">
            <table className="w-full text-xs border-collapse">
              <thead className="bg-cloudo-panel-2 sticky top-0 z-10 border-b border-cloudo-border">
                <tr className="text-[10px] font-black text-cloudo-muted uppercase tracking-[0.3em]">
                  <th className="px-4 py-4 text-left">Timestamp</th>
                  <th className="px-4 py-4 text-left">State</th>
                  <th className="px-4 py-4 text-left">Process_Context</th>
                  <th className="px-4 py-4 text-left">Runbook</th>
                  <th className="px-4 py-4 text-center w-10">On Call</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-cloudo-border/50">
                {logs.map((log) => (
                  <tr
                    key={log.RowKey}
                    onClick={() => setSelectedLog(log)}
                    className={`cursor-pointer transition-colors hover:bg-white/[0.02] ${
                      selectedLog?.RowKey === log.RowKey
                        ? "bg-cloudo-accent/5 border-l-2 border-cloudo-accent"
                        : ""
                    }`}
                  >
                    <td className="px-4 py-4 whitespace-nowrap">
                      <div className="text-cloudo-text font-bold">
                        {log.RequestedAt?.split("T")[1]?.slice(0, 8)}
                      </div>
                      <div className="text-[10px] text-cloudo-muted opacity-70">
                        {log.RequestedAt?.split("T")[0]}
                      </div>
                    </td>
                    <td className="px-4 py-4">
                      <div className="flex items-center gap-2">
                        <span
                          className={`px-1.5 py-0.5 border text-[10px] font-black uppercase tracking-widest ${getStatusBadgeClass(
                            log.Status,
                          )}`}
                        >
                          {log.Status}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-4">
                      <div className="text-cloudo-text font-bold uppercase tracking-widest truncate max-w-[150px]">
                        {log.Name || "SYS_TASK"}
                      </div>
                      <div className="text-[10px] text-cloudo-muted/60 opacity-50 truncate max-w-[150px]">
                        {log.ExecId.slice(0, 12)}
                      </div>
                    </td>
                    <td className="px-4 py-4">
                      <div className="text-[11px] font-mono text-cloudo-accent/70 uppercase tracking-widest truncate max-w-[150px]">
                        {log.Runbook}
                      </div>
                    </td>
                    <td className="px-4 py-4 text-center">
                      {(log.OnCall === true || log.OnCall === "true") && (
                        <div className="flex justify-center">
                          <div className="w-1.5 h-1.5 bg-cloudo-err animate-pulse" />
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {logs.length === 0 && !loading && (
              <div className="py-20 text-center flex flex-col items-center gap-3 opacity-50">
                <HiOutlineTerminal className="w-8 h-8" />
                <span className="text-[10px] font-black uppercase tracking-widest">
                  interrogation_idle // no_data
                </span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Detail Panel Section */}
      {selectedLog && (
        <div className="flex-1 bg-cloudo-panel border border-cloudo-border flex flex-col animate-in slide-in-from-right-4 duration-300 overflow-hidden">
          <div className="p-6 border-b border-cloudo-border bg-cloudo-panel-2 flex justify-between items-center">
            <div className="flex items-center gap-4">
              <div className="w-10 h-10 bg-cloudo-accent/10 border border-cloudo-accent/20 flex items-center justify-center text-cloudo-accent">
                <HiOutlineTerminal className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-xs font-black text-cloudo-text uppercase tracking-[0.2em]">
                  {selectedLog.Name || "Runtime Process"}
                </h3>
                <div className="flex items-center gap-2 mt-1">
                  <code className="text-[10px] text-cloudo-muted font-mono">
                    {selectedLog.ExecId}
                  </code>
                </div>
              </div>
            </div>
            <button
              onClick={() => setSelectedLog(null)}
              className="p-2 text-cloudo-muted hover:text-cloudo-text border border-cloudo-border transition-colors"
            >
              <HiOutlineX className="w-4 h-4" />
            </button>
          </div>

          <div className="flex-1 overflow-auto p-8 space-y-8 custom-scrollbar bg-cloudo-accent/10">
            {/* Section: Identity & Deployment */}
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <div className="w-1 h-3 bg-cloudo-accent" />
                <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-cloudo-muted">
                  Process Identity & Deployment
                </h3>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                <DetailItem
                  label="Asset_Path"
                  value={selectedLog.Runbook}
                  icon={<HiOutlineTerminal className="text-cloudo-accent" />}
                />
                <DetailItem
                  label="Initiator"
                  value={
                    selectedLog.Initiator ||
                    String(selectedLog.OnCall || "AUTO")
                  }
                  icon={<HiOutlineTag />}
                />
                <DetailItem
                  label="Node"
                  value={selectedLog.Worker || "DYNAMIC"}
                  icon={<HiOutlineDatabase />}
                />
                <DetailItem
                  label="Requested At"
                  value={new Date(selectedLog.RequestedAt).toLocaleString([], {
                    day: "2-digit",
                    month: "2-digit",
                    year: "numeric",
                    hour: "2-digit",
                    minute: "2-digit",
                    second: "2-digit",
                    hour12: false,
                  })}
                  icon={<HiOutlineCalendar />}
                  className="md:col-span-2"
                />
              </div>
            </div>

            {/* Section: Execution Status */}
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <div className="w-1 h-3 bg-cloudo-accent" />
                <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-cloudo-muted">
                  Execution Status
                </h3>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                <DetailItem
                  label="Status"
                  value={selectedLog.Status}
                  icon={<HiOutlineTag />}
                  className={`flex-col items-start !space-y-1 ${getStatusBadgeClass(
                    selectedLog.Status,
                  )}`}
                />
                <div
                  className="bg-cloudo-accent/10 border border-cloudo-border p-3 flex flex-col justify-center items-center gap-1 cursor-pointer hover:bg-cloudo-accent/5 transition-colors"
                  onClick={() => copyToClipboard(selectedLog.ExecId)}
                >
                  <span className="text-[10px] font-black text-cloudo-muted uppercase tracking-widest block">
                    Copy_ID
                  </span>
                  {copied ? (
                    <HiOutlineClipboardCheck className="text-cloudo-ok w-3 h-3" />
                  ) : (
                    <HiOutlineClipboard className="w-3 h-3" />
                  )}
                </div>
              </div>
            </div>

            {/* Section: Runtime Arguments */}
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <div className="w-1 h-3 bg-cloudo-accent" />
                <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-cloudo-muted">
                  Runtime Arguments
                </h3>
              </div>
              <div className="bg-cloudo-dark/60 border border-cloudo-border p-4 font-mono text-[11px] text-cloudo-accent whitespace-pre-wrap break-all leading-relaxed">
                {selectedLog.Run_Args || "EMPTY_ARGS"}
              </div>
            </div>

            {/* Section: Telemetry Logs */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-1 h-2 bg-cloudo-accent" />
                  <span className="text-[11px] font-black uppercase tracking-[0.2em] text-cloudo-text">
                    Standard Output Stream
                  </span>
                </div>
                <button
                  onClick={() => copyToClipboard(selectedLog.Log)}
                  className="flex items-center gap-2 text-[9px] font-black uppercase tracking-widest text-cloudo-accent hover:text-white transition-colors"
                  title="Copy all logs"
                >
                  {copied ? (
                    <>
                      <HiOutlineClipboardCheck className="w-3.5 h-3.5 text-cloudo-ok" />
                      <span className="text-cloudo-ok">Copied</span>
                    </>
                  ) : (
                    <>
                      <HiOutlineClipboard className="w-3.5 h-3.5" />
                      <span>Copy Logs</span>
                    </>
                  )}
                </button>
              </div>
              <div className="bg-cloudo-dark p-6 border border-cloudo-border font-mono text-xs min-h-[400px] overflow-x-auto">
                {formatLogContent(selectedLog.Log)}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function DetailItem({
  label,
  value,
  icon,
  className = "",
}: {
  label: string;
  value: string;
  icon: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`bg-cloudo-accent/10 border border-cloudo-border p-3 space-y-2 overflow-hidden ${className}`}
    >
      <div className="flex items-center gap-2 text-cloudo-muted/60">
        <span className="text-sm">{icon}</span>
        <span className="text-[10px] font-black uppercase tracking-widest whitespace-nowrap">
          {label}
        </span>
      </div>
      <div
        className="text-[11px] font-bold text-cloudo-text truncate uppercase tracking-tighter hover:whitespace-normal hover:break-all transition-all"
        title={value}
      >
        {value}
      </div>
    </div>
  );
}
