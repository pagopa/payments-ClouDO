'use client';

import { useState, useEffect, useMemo } from 'react';
import {
  HiOutlineShieldCheck,
  HiOutlineTerminal,
  HiOutlineCheck,
  HiOutlineX,
  HiOutlineRefresh,
  HiOutlineClock,
  HiOutlineUser,
  HiOutlineFingerPrint,
  HiOutlineSearch
} from "react-icons/hi";

interface PendingApproval {
  ExecId: string;
  Name: string;
  Runbook: string;
  RequestedAt: string;
  Status: string;
  Log?: string;
  ResourceInfo?: any;
  Run_Args?: string;
  Worker?: string;
  OnCall?: string;
}

export default function ApprovalsPage() {
  const [pendingList, setPendingList] = useState<PendingApproval[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedExec, setSelectedExec] = useState<PendingApproval | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);

  const approvalLinks = useMemo(() => {
    if (!selectedExec?.Log) return null;
    try {
      const parsed = JSON.parse(selectedExec.Log);
      const approveUrl = parsed.approve || null;
      let decodedPayload: any = null;

      if (approveUrl) {
        try {
          const url = new URL(approveUrl);
          const p = url.searchParams.get('p');
          if (p) {
            let base64 = p.replace(/-/g, '+').replace(/_/g, '/');

            while (base64.length % 4) {
              base64 += '=';
            }

            const binString = atob(base64);
            const jsonPayload = decodeURIComponent(
              Array.prototype.map.call(binString, (c) => {
                return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
              }).join('')
            );

            decodedPayload = JSON.parse(jsonPayload);
            console.log(decodedPayload)
          }
        } catch (e) {
          console.warn("Payload decoding failed:", e);
        }
      }

      const resource_info = decodedPayload?.resource_info || parsed.resource_info || (parsed.response?.resource_info) || {};
      const routing_info = decodedPayload?.routing_info || parsed.routing_info || {};

      return {
        approve: approveUrl,
        reject: parsed.reject || null,
        message: parsed.message || '',
        // Uniamo resource e routing info per non avere il pannello vuoto
        display_info: { ...resource_info },
        worker: decodedPayload?.worker || selectedExec.Worker || null,
        severity: decodedPayload?.severity || null,
        monitor: decodedPayload?.monitorCondition || null,
        run_args: selectedExec.Run_Args || null,
        oncall: selectedExec.OnCall || null
      };
    } catch {
      return null;
    }
  }, [selectedExec]);

  const handleAction = async (url: string | null) => {
    if (!url) return;
    setIsProcessing(true);
    try {
      const res = await fetch(url, { method: 'GET' });
      if (res.ok) {
        await fetchPendingApprovals();
      } else {
        alert(`Action failed: ${res.statusText}`);
      }
    } catch (e) {
      console.error(e);
      alert('Error communicating with orchestrator');
    } finally {
      setIsProcessing(false);
    }
  };

  useEffect(() => {
    fetchPendingApprovals();
  }, []);

  const fetchPendingApprovals = async () => {
    setLoading(true);
    try {
      const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:7071/api';
      const now = new Date();
      const oneHourAgo = new Date(now.getTime() - 60 * 60 * 1000);

      const today = new Date();
      const partitionKey = `${today.getFullYear()}${String(today.getMonth() + 1).padStart(2, '0')}${String(today.getDate()).padStart(2, '0')}`;

      const res = await fetch(`${API_URL}/logs/query?partitionKey=${partitionKey}`);
      const data = await res.json();
      const items = data.items || [];

      const terminalIds = new Set(
        items
          .filter((e: any) => {
            const s = (e.Status || '').toLowerCase();
            return ['succeeded', 'failed', 'rejected', 'error', 'skipped'].includes(s);
          })
          .map((e: any) => e.ExecId)
      );

      const pendingMap = new Map();

      const sortedItems = [...items].sort((a, b) =>
        new Date(a.RequestedAt).getTime() - new Date(b.RequestedAt).getTime()
      );

      sortedItems.forEach((e: any) => {
        const id = e.ExecId;
        const status = (e.Status || '').toLowerCase();
        const requestedAt = new Date(e.RequestedAt);

        // Ignoriamo se è scaduto o se ha già un record terminale nel log
        if (requestedAt < oneHourAgo || terminalIds.has(id)) {
          return;
        }

        if (status === 'pending' || status === 'accepted') {
          // Se troviamo 'accepted', sovrascriviamo il 'pending' precedente per questo ExecId
          const enriched = {
            ...e,
            Status: status === 'accepted' ? 'running' : 'pending'
          };
          pendingMap.set(id, enriched);
        }
      });

      const finalPendingList = Array.from(pendingMap.values())
        .sort((a: any, b: any) => new Date(b.RequestedAt).getTime() - new Date(a.RequestedAt).getTime());

      setPendingList(finalPendingList);

      // Update selection with new data if it exists, otherwise clear it
      if (selectedExec) {
        const updated = pendingMap.get(selectedExec.ExecId);
        if (updated) {
          setSelectedExec(updated);
        } else {
          setSelectedExec(null);
        }
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-[#0a0c10] text-cloudo-text font-sans selection:bg-amber-500/30">
      {/* Header Bar - Solid Technical Style */}
      <div className="flex items-center justify-between px-8 py-4 border-b border-cloudo-border/20 bg-[#0d1117]/80 backdrop-blur-xl sticky top-0 z-20">
        <div className="flex items-center gap-4">
          <div className="p-2 bg-amber-500/10 rounded-lg border border-amber-500/20">
            <HiOutlineShieldCheck className="text-amber-500 w-5 h-5 shadow-[0_0_10px_rgba(245,158,11,0.2)]" />
          </div>
          <div>
            <h1 className="text-sm font-bold tracking-tight text-white uppercase">Governance Gate</h1>
            <p className="text-[10px] text-cloudo-muted font-black uppercase tracking-[0.2em] opacity-60">Filtered Approval Queue</p>
          </div>
        </div>
        <div className="flex items-center gap-4">
           <div className="text-[10px] font-black uppercase tracking-widest text-cloudo-muted bg-white/[0.03] px-3 py-1.5 rounded border border-cloudo-border/10">
              {pendingList.length} Requests Awaiting Signature
           </div>
           <button
            onClick={fetchPendingApprovals}
            className="bg-cloudo-accent hover:bg-cloudo-accent/90 text-white px-4 py-1.5 rounded-md text-[11px] font-black uppercase tracking-widest transition-all flex items-center gap-2 shadow-lg shadow-cloudo-accent/10"
          >
            <HiOutlineRefresh className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            Sync Queue
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-8">
        <div className="max-w-[1400px] mx-auto">
          {loading ? (
            <div className="py-24 text-center flex flex-col items-center gap-4">
              <div className="w-8 h-8 border-2 border-amber-500/30 border-t-amber-500 rounded-full animate-spin" />
              <span className="text-[10px] font-black uppercase tracking-[0.3em] text-cloudo-muted">Verifying Registry Compliance...</span>
            </div>
          ) : pendingList.length === 0 ? (
            <div className="py-32 text-center flex flex-col items-center gap-4 opacity-20">
              <HiOutlineShieldCheck className="w-16 h-16" />
              <p className="text-[10px] font-black uppercase tracking-[0.4em]">All Systems Authorized • No Pending Gates</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-12">
              {/* Left Column: List */}
              <div className="space-y-4">
                <h2 className="text-[10px] font-black uppercase tracking-[0.3em] text-cloudo-muted border-b border-cloudo-border/10 pb-2 flex justify-between">
                  <span>Authorization Requests</span>
                  <span className="text-amber-500/60 font-mono tracking-normal">{pendingList.length} Pending</span>
                </h2>
                <div className="space-y-3">
                  {pendingList.map((item) => (
                    <div
                      key={item.ExecId}
                      onClick={() => setSelectedExec(item)}
                      className={`group bg-[#0d1117]/40 border rounded-xl p-5 cursor-pointer transition-all ${selectedExec?.ExecId === item.ExecId ? 'border-amber-500/50 bg-amber-500/[0.04] shadow-[0_0_20px_rgba(245,158,11,0.05)]' : 'border-cloudo-border/20 hover:border-cloudo-border/50'}`}
                    >
                      <div className="flex justify-between items-start mb-4">
                        <div className="flex items-center gap-3">
                          <div className={`w-2 h-2 rounded-full shadow-[0_0_8px_rgba(245,158,11,0.4)] ${item.Status === 'running' ? 'bg-green-500 shadow-green-500/40 animate-pulse' : 'bg-amber-500 animate-pulse'}`} />
                          <span className="text-sm font-bold text-white tracking-tight group-hover:text-amber-500 transition-colors">{item.Name || 'Unlabeled Request'}</span>
                        </div>
                        <span className={`text-[8px] font-black px-1.5 py-0.5 rounded border uppercase tracking-tighter font-mono ${item.Status === 'running' ? 'bg-green-500/10 text-green-500 border-green-500/20' : 'bg-amber-500/10 text-amber-500 border-amber-500/20'}`}>
                          {item.Status === 'running' ? 'Running' : 'Pending'}
                        </span>
                      </div>
                      <div className="flex items-center gap-6 text-[10px] text-cloudo-muted font-black uppercase tracking-tight">
                        <span className="flex items-center gap-2"><HiOutlineTerminal className="w-3.5 h-3.5 text-cloudo-accent/40" /> {item.Runbook}</span>
                        <span className="flex items-center gap-2"><HiOutlineClock className="w-3.5 h-3.5 opacity-40" /> {new Date(item.RequestedAt).toLocaleTimeString()}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Right Column: Detail Panel */}
              <div className="space-y-4">
                <h2 className="text-[10px] font-black uppercase tracking-[0.3em] text-cloudo-muted border-b border-cloudo-border/10 pb-2">Resource Details</h2>
                {selectedExec ? (
                  <div className="bg-[#0d1117]/60 border border-cloudo-border/30 rounded-xl overflow-hidden shadow-2xl animate-in slide-in-from-right duration-300">
                    <div className="p-8 space-y-8">
                      {/* Identity Header */}
                      <div className="space-y-4">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2 text-[10px] font-black uppercase tracking-widest text-amber-500/80">
                            <HiOutlineFingerPrint /> Cryptographic Identity
                          </div>
                          {approvalLinks?.message && (
                            <span className="text-[9px] font-black text-blue-400/80 uppercase tracking-widest flex items-center gap-1.5">
                              <HiOutlineShieldCheck className="w-3 h-3" />
                              {approvalLinks.message}
                            </span>
                          )}
                        </div>
                        <div className="grid grid-cols-2 gap-6 bg-black/40 p-4 rounded-lg border border-cloudo-border/30">
                          <div className="space-y-1">
                            <span className="text-[9px] font-black text-cloudo-muted uppercase tracking-widest block">ExecId</span>
                            <span className="text-[10px] text-white font-mono break-all">{selectedExec.ExecId}</span>
                          </div>
                          <div className="space-y-1 text-right">
                            <span className="text-[9px] font-black text-cloudo-muted uppercase tracking-widest block">Timestamp</span>
                            <span className="text-[10px] text-white font-mono">{new Date(selectedExec.RequestedAt).toLocaleString()}</span>
                          </div>
                        </div>
                      </div>

                          {/* Runbook Info */}
                          <div className="space-y-4">
                             <div className="text-[10px] font-black uppercase tracking-widest text-cloudo-muted">Execution Target</div>
                             <div className="bg-black/40 border border-cloudo-border/30 rounded-lg p-4 space-y-3">
                                <div className="flex items-center justify-between">
                                   <div className="flex items-center gap-3">
                                      <HiOutlineTerminal className="text-cloudo-accent w-4 h-4" />
                                      <span className="text-[11px] font-bold text-white uppercase tracking-wider">{selectedExec.Runbook}</span>
                                   </div>
                                   <span className="text-[9px] font-black bg-cloudo-accent/10 text-cloudo-accent px-2 py-1 rounded border border-cloudo-accent/20 uppercase tracking-widest font-mono">
                                      {approvalLinks?.worker || 'DYNAMIC_ROUTING'}
                                   </span>
                                </div>
                                {approvalLinks?.severity && (
                                   <div className="flex items-center gap-2 text-[10px] text-cloudo-muted font-black uppercase">
                                      <span className="opacity-40">Severity:</span>
                                      <span className="text-amber-500/80">{approvalLinks.severity}</span>
                                   </div>
                                )}
                                {approvalLinks?.monitor && (
                                   <div className="flex items-center gap-2 text-[10px] text-cloudo-muted font-black uppercase">
                                      <span className="opacity-40">Condition:</span>
                                      <span className="text-blue-400/80">{approvalLinks.monitor}</span>
                                   </div>
                                )}
                             </div>
                          </div>

                      {/* Execution Context */}
                      <div className="space-y-4">
                        <div className="text-[10px] font-black uppercase tracking-widest text-cloudo-muted">Execution Context</div>
                        <div className="bg-black/40 border border-cloudo-border/30 rounded-lg p-4 space-y-4">
                          <div className="space-y-1.5">
                            <span className="text-[9px] font-black text-cloudo-muted uppercase tracking-widest block opacity-40">Arguments</span>
                            <div className="bg-[#05070a] p-3 rounded border border-cloudo-border/10 font-mono text-[10px] text-amber-500/90 break-all leading-relaxed">
                              {approvalLinks?.run_args ? (
                                <code>{approvalLinks.run_args}</code>
                              ) : (
                                <span className="opacity-30 italic">No arguments provided</span>
                              )}
                            </div>
                          </div>

                          {approvalLinks?.oncall && approvalLinks.oncall !== 'false' && (
                            <div className="flex items-center justify-between pt-2 border-t border-cloudo-border/10">
                              <div className="flex items-center gap-2 text-[10px] font-black uppercase text-cloudo-muted">
                                <HiOutlineUser className="text-blue-400" />
                                <span>On-Call Support</span>
                              </div>
                              <span className="text-[10px] font-mono text-white bg-blue-500/10 px-2 py-0.5 rounded border border-blue-500/20">
                                {approvalLinks.oncall}
                              </span>
                            </div>
                          )}
                        </div>
                      </div>

                      {/* Resource Context Info */}
                      <div className="space-y-3">
                        <div className="text-[10px] font-black uppercase tracking-widest text-cloudo-muted">Resource Context</div>
                        <div className="bg-[#080a0f] border border-cloudo-border/30 rounded-lg p-4 space-y-2">
                          {approvalLinks?.display_info ? (
                            Object.entries(approvalLinks.display_info).map(([key, value]) => {
                              if (!value || key === '_raw') return null;
                              return (
                                <div key={key} className="flex justify-between text-[10px] border-b border-cloudo-border/5 pb-1">
                                  <span className="text-cloudo-muted font-bold uppercase">{key.replace('resource_', '').replace('resource', '').replace('aks_', 'k8s_').replace(/[A-Z]/g, letter => `_${letter.toLowerCase()}`).replace(/^_/, '')}</span>
                                  <span className="text-white font-mono text-right ml-4 break-all">{String(value)}</span>
                                </div>
                              );
                            })
                          ) : (
                            <p className="text-[10px] text-cloudo-muted italic italic">No resource metadata available</p>
                          )}
                        </div>
                      </div>

                      {/* Action Bar */}
                      <div className="grid grid-cols-2 gap-4 pt-6 border-t border-cloudo-border/10">
                        <button
                          onClick={() => handleAction(approvalLinks?.reject)}
                          disabled={isProcessing || !approvalLinks?.reject}
                          className="flex items-center justify-center gap-2 bg-red-500/10 hover:bg-red-500/20 text-red-500 border border-red-500/30 py-3 rounded-md text-[10px] font-black uppercase tracking-[0.2em] transition-all disabled:opacity-30 disabled:cursor-not-allowed"
                        >
                          {isProcessing ? (
                            <div className="w-3 h-3 border-2 border-red-500/30 border-t-red-500 rounded-full animate-spin" />
                          ) : (
                            <HiOutlineX className="w-4 h-4" />
                          )}
                          Deny Request
                        </button>
                        <button
                          onClick={() => handleAction(approvalLinks?.approve)}
                          disabled={isProcessing || !approvalLinks?.approve}
                          className="flex items-center justify-center gap-2 bg-amber-500 hover:bg-amber-600 text-black py-3 rounded-md text-[10px] font-black uppercase tracking-[0.2em] transition-all shadow-xl shadow-amber-500/10 disabled:opacity-30 disabled:cursor-not-allowed"
                        >
                          {isProcessing ? (
                            <div className="w-3 h-3 border-2 border-black/30 border-t-black rounded-full animate-spin" />
                          ) : (
                            <HiOutlineCheck className="w-4 h-4" />
                          )}
                          Authorize Execution
                        </button>
                      </div>

                      {/* Warning if links are missing */}
                      {!approvalLinks && !isProcessing && (
                        <p className="text-[9px] text-red-400/60 uppercase font-black text-center italic tracking-widest">
                          Error: Approval metadata missing from log entry
                        </p>
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="h-[400px] border border-dashed border-cloudo-border/20 rounded-xl flex flex-col items-center justify-center gap-4 text-cloudo-muted opacity-30">
                    <HiOutlineSearch className="w-12 h-12" />
                    <span className="text-[10px] font-black uppercase tracking-[0.4em]">Select request to audit</span>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
