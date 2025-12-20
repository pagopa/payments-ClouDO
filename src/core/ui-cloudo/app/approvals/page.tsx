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
}

export default function ApprovalsPage() {
  const [pendingList, setPendingList] = useState<PendingApproval[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedExec, setSelectedExec] = useState<PendingApproval | null>(null);
  const [isProcessing, setIsProcessing] = useState(false); // Per gestire lo stato delle azioni

  // Helper per estrarre i link dal log JSON
  const approvalLinks = useMemo(() => {
    if (!selectedExec?.Log) return null;
    try {
      const parsed = JSON.parse(selectedExec.Log);
      return {
        approve: parsed.approve || null,
        reject: parsed.reject || null,
        message: parsed.message || ''
      };
    } catch {
      return null;
    }
  }, [selectedExec]);

  const handleAction = async (url: string | null) => {
    if (!url) return;
    setIsProcessing(true);
    try {
      // Usiamo GET o POST a seconda di come è implementata la tua API di approvazione
      // Dalla struttura dell'URL sembra una GET con parametri in query string
      const res = await fetch(url, { method: 'GET' });
      if (res.ok) {
        // Ricarichiamo la coda dopo l'azione
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
      const today = new Date();
      const partitionKey = `${today.getFullYear()}${String(today.getMonth() + 1).padStart(2, '0')}${String(today.getDate()).padStart(2, '0')}`;

      const res = await fetch(`${API_URL}/logs/query?partitionKey=${partitionKey}`);
      const data = await res.json();
      const items = data.items || [];

      const executedIds = new Set(
        items
          .filter((e: any) => !['pending', 'accepted'].includes((e.Status || '').toLowerCase()))
          .map((e: any) => e.ExecId)
      );

      const pendingMap = new Map();
      items.forEach((e: any) => {
        const id = e.ExecId;
        const status = (e.Status || '').toLowerCase();
        const isWaitingStatus = ['pending'].includes(status);

        if (isWaitingStatus && !executedIds.has(id)) {
          if (!pendingMap.has(id)) {
            pendingMap.set(id, e);
          }
        }
      });

      const finalPendingList = Array.from(pendingMap.values());
      setPendingList(finalPendingList);

      // Reset selezione se l'elemento non è più in lista
      if (selectedExec && !pendingMap.has(selectedExec.ExecId)) {
        setSelectedExec(null);
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
                          <div className={`w-2 h-2 rounded-full bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.4)] ${selectedExec?.ExecId === item.ExecId ? 'animate-pulse' : ''}`} />
                          <span className="text-sm font-bold text-white tracking-tight group-hover:text-amber-500 transition-colors">{item.Name || 'Unlabeled Request'}</span>
                        </div>
                        <span className="text-[9px] font-mono text-cloudo-muted uppercase opacity-40">
                          {item.ExecId.slice(0, 12)}
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
                        <div className="flex items-center gap-2 text-[10px] font-black uppercase tracking-widest text-amber-500/80">
                          <HiOutlineFingerPrint /> Cryptographic Identity
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
                         <div className="bg-black/40 border border-cloudo-border/30 rounded-lg p-4 flex items-center justify-between">
                            <div className="flex items-center gap-3">
                               <HiOutlineTerminal className="text-cloudo-accent w-4 h-4" />
                               <span className="text-[11px] font-bold text-white uppercase tracking-wider">{selectedExec.Runbook}</span>
                            </div>
                            <span className="text-[9px] font-black bg-cloudo-accent/10 text-cloudo-accent px-2 py-1 rounded border border-cloudo-accent/20 uppercase tracking-widest font-mono">ASSET_VERIFIED</span>
                         </div>
                      </div>

                      {/* Log / Context Area */}
                      <div className="space-y-3">
                        <div className="text-[10px] font-black uppercase tracking-widest text-cloudo-muted">Raw Context Payload</div>
                        <div className="bg-[#080a0f] border border-cloudo-border/30 rounded-lg p-5 text-[11px] font-mono text-cloudo-text/60 leading-relaxed overflow-x-auto min-h-[120px] max-h-[250px] custom-scrollbar">
                          {selectedExec.Log || '// Metadata entry only\n// Waiting for manual signature to proceed with worker allocation.'}
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
