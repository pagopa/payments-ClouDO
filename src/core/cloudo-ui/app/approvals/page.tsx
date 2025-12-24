'use client';

import { useState, useEffect, useMemo } from 'react';
import { cloudoFetch } from '@/lib/api';
import {
  HiOutlineShieldCheck,
  HiOutlineTerminal,
  HiOutlineCheck,
  HiOutlineX,
  HiOutlineRefresh,
  HiOutlineClock,
  HiOutlineUser,
  HiOutlineFingerPrint,
  HiOutlineSearch,
  HiOutlineServer,
  HiOutlineInformationCircle,
  HiOutlineExclamationCircle
} from "react-icons/hi";

interface Notification {
  id: number;
  type: 'success' | 'error' | 'info';
  message: string;
}

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
  const [notifications, setNotifications] = useState<Notification[]>([]);

  const addNotification = (type: 'success' | 'error' | 'info', message: string) => {
    const id = Date.now();
    setNotifications(prev => [...prev, { id, type, message }]);
    setTimeout(() => {
      setNotifications(prev => prev.filter(n => n.id !== id));
    }, 5000);
  };

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
    const userData = localStorage.getItem('cloudo_user');
    const currentUser = userData ? JSON.parse(userData) : null;

    if (!url) return;
    setIsProcessing(true);
    try {
      const res = await cloudoFetch(
        url, {
          method: 'GET',
          headers: {
            'x-Approver': currentUser?.username || '',
            'x-cloudo-user': currentUser?.username || ''
          }
        }
      );
      if (res.ok) {
        addNotification('success', 'Operation executed successfully');
        await fetchPendingApprovals();
      } else {
        addNotification('error', `Action failed: ${res.statusText}`);
      }
    } catch (e) {
      console.error(e);
      addNotification('error', 'Error communicating with orchestrator');
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
      const now = new Date();
      const oneHourAgo = new Date(now.getTime() - 60 * 60 * 1000);

      const today = new Date();
      const partitionKey = `${today.getFullYear()}${String(today.getMonth() + 1).padStart(2, '0')}${String(today.getDate()).padStart(2, '0')}`;

      const res = await cloudoFetch(`/logs/query?partitionKey=${partitionKey}`);
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

        if (requestedAt < oneHourAgo || terminalIds.has(id) || e.ApprovalRequired !== true) {
          return;
        }

        if (status === 'pending' || status === 'accepted') {
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
    <div className="flex flex-col h-full bg-cloudo-dark text-cloudo-text font-mono selection:bg-cloudo-accent/30">
      {/* Header Bar - Solid Technical Style */}
      <div className="flex items-center justify-between px-8 py-4 border-b border-cloudo-border bg-cloudo-panel sticky top-0 z-20">
        <div className="flex items-center gap-4 shrink-0">
          <div className="p-2 bg-cloudo-warn/5 border border-cloudo-warn/20 shrink-0">
            <HiOutlineShieldCheck className="text-cloudo-warn w-4 h-4" />
          </div>
          <div>
            <h1 className="text-sm font-black tracking-[0.2em] text-white uppercase">Governance Gate</h1>
            <p className="text-[11px] text-cloudo-muted font-bold uppercase tracking-[0.3em] opacity-40">Filtered Approval Queue</p>
          </div>
        </div>
        <div className="flex items-center gap-4">
           <div className="text-[11px] font-black uppercase tracking-widest text-cloudo-muted bg-black/40 px-3 py-1.5 border border-cloudo-border">
              {pendingList.length} Requests Pending Signature
           </div>
           <button
            onClick={fetchPendingApprovals}
            className="btn btn-primary"
          >
            <HiOutlineRefresh className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-8">
        <div className="max-w-[1400px] mx-auto">
          {loading ? (
            <div className="py-24 text-center flex flex-col items-center gap-4">
              <div className="w-8 h-8 border-2 border-cloudo-warn/30 border-t-cloudo-warn rounded-full animate-spin" />
              <span className="text-[11px] font-black uppercase tracking-[0.3em] text-cloudo-muted">Verifying Registry Compliance...</span>
            </div>
          ) : pendingList.length === 0 ? (
            <div className="py-32 text-center border border-cloudo-border bg-black/20">
              <HiOutlineShieldCheck className="w-16 h-16 text-cloudo-muted/20 mx-auto mb-6" />
              <p className="text-sm font-black uppercase tracking-[0.4em] text-cloudo-muted">No authorization requests detected</p>
              <p className="text-[11px] text-cloudo-muted/40 uppercase mt-2 tracking-widest">System is currently compliant</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-12">
              {/* Left Column: List */}
              <div className="space-y-4">
                <div className="flex items-center gap-3 mb-6">
                   <div className="w-1.5 h-4 bg-cloudo-warn" />
                   <h2 className="text-sm font-black uppercase tracking-[0.4em] text-white">Pending Requests</h2>
                </div>
                <div className="space-y-3">
                  {pendingList.map((item) => (
                    <div
                      key={item.ExecId}
                      onClick={() => setSelectedExec(item)}
                      className={`p-4 border transition-all cursor-pointer group relative ${
                        selectedExec?.ExecId === item.ExecId
                          ? 'bg-cloudo-warn/5 border-cloudo-warn/40'
                          : 'bg-cloudo-panel border-cloudo-border hover:border-cloudo-muted/40'
                      }`}
                    >
                      <div className="flex justify-between items-start mb-3">
                        <div className="flex items-center gap-3">
                          <div className={`w-2 h-2 ${item.Status === 'running' ? 'bg-cloudo-accent animate-pulse' : 'bg-cloudo-warn'}`} />
                          <h3 className="text-sm font-black text-white uppercase tracking-widest truncate max-w-[180px]">
                            {item.Name || 'SYS_TASK'}
                          </h3>
                        </div>
                        <span className="text-[11px] font-mono text-cloudo-muted opacity-40 uppercase">{new Date(item.RequestedAt).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit', hour12: false})}</span>
                      </div>
                      <div className="flex items-center gap-2 text-[11px] font-mono text-cloudo-accent/60 uppercase tracking-widest">
                        <HiOutlineTerminal className="w-4 h-4" />
                        {item.Runbook}
                      </div>
                      {selectedExec?.ExecId === item.ExecId && (
                        <div className="absolute left-[-1px] top-0 w-[2px] h-full bg-cloudo-warn" />
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {/* Right Column: Detail Panel */}
              <div className="space-y-4">
                <div className="flex items-center gap-3 mb-6">
                   <div className="w-1.5 h-4 bg-cloudo-accent" />
                   <h2 className="text-sm font-black uppercase tracking-[0.4em] text-white">Resource Details</h2>
                </div>
                {selectedExec ? (
                  <div className="border border-cloudo-border bg-cloudo-panel overflow-hidden sticky top-8 animate-in fade-in slide-in-from-right-4 duration-300">
                    <div className="p-6 border-b border-cloudo-border bg-black/20 flex justify-between items-center">
                      <div className="flex items-center gap-4">
                        <div className="w-12 h-12 bg-cloudo-warn/10 border border-cloudo-warn/20 flex items-center justify-center text-cloudo-warn">
                           <HiOutlineFingerPrint className="w-6 h-6" />
                        </div>
                        <div>
                          <h2 className="text-sm font-black text-white uppercase tracking-[0.2em]">{selectedExec.Name}</h2>
                          <p className="text-[11px] font-mono text-cloudo-muted uppercase tracking-widest mt-1">Request_ID: {selectedExec.ExecId}</p>
                        </div>
                      </div>
                      <button onClick={() => setSelectedExec(null)} className="p-2 text-cloudo-muted hover:text-white transition-colors border border-cloudo-border">
                        <HiOutlineX className="w-5 h-5" />
                      </button>
                    </div>

                    <div className="p-8 space-y-8">
                      {/* Meta Information Grid */}
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                         <DetailItem label="Initiator" value={selectedExec.OnCall || 'AUTO_TRIGGER'} icon={<HiOutlineUser />} />
                         <DetailItem label="Node" value={selectedExec.Worker || 'DYNAMIC'} icon={<HiOutlineServer className="w-4 h-4"/>} />
                         <DetailItem label="Priority" value={approvalLinks?.severity || 'NORMAL'} icon={<HiOutlineClock />} />
                         <DetailItem label="Condition" value={approvalLinks?.monitor || 'DIRECT'} icon={<HiOutlineSearch />} />
                      </div>

                      {/* Arguments Panel */}
                      <div className="space-y-3">
                         <div className="flex items-center gap-2">
                           <div className="w-1.5 h-2.5 bg-cloudo-accent" />
                           <span className="text-[11px] font-black uppercase tracking-[0.2em] text-white">Runtime Arguments</span>
                         </div>
                         <div className="bg-black/60 border border-cloudo-border p-4 font-mono text-xs text-cloudo-accent/80 whitespace-pre-wrap leading-relaxed">
                           {selectedExec.Run_Args || 'NO_ARGS_PROVIDED'}
                         </div>
                      </div>

                      {/* Approval Data Panel */}
                      {approvalLinks?.display_info && Object.keys(approvalLinks.display_info).length > 0 && (
                        <div className="space-y-3">
                           <div className="flex items-center gap-2">
                             <div className="w-1.5 h-2.5 bg-cloudo-warn" />
                             <span className="text-[11px] font-black uppercase tracking-[0.2em] text-white">Compliance Manifest</span>
                           </div>
                           <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                             {Object.entries(approvalLinks.display_info).map(([k, v]: [string, any]) => (
                               <div key={k} className="bg-black/40 border border-cloudo-border p-3 flex justify-between items-center group">
                                 <span className="text-[11px] font-black text-cloudo-muted uppercase tracking-widest">{k}</span>
                                 <span className="text-xs font-mono text-white group-hover:text-cloudo-accent transition-colors">{String(v)}</span>
                               </div>
                             ))}
                           </div>
                        </div>
                      )}

                      {/* Action Bar */}
                      <div className="grid grid-cols-2 gap-4 pt-8 border-t border-cloudo-border">
                        <button
                          onClick={() => handleAction(approvalLinks?.reject)}
                          disabled={isProcessing || !approvalLinks?.reject}
                          className="flex items-center justify-center gap-2 bg-cloudo-err/10 hover:bg-cloudo-err hover:text-white text-cloudo-err border border-cloudo-err/30 py-4 text-[11px] font-black uppercase tracking-[0.3em] transition-all disabled:opacity-30"
                        >
                          <HiOutlineX className="w-5 h-5" />
                          Reject Request
                        </button>
                        <button
                          onClick={() => handleAction(approvalLinks?.approve)}
                          disabled={isProcessing || !approvalLinks?.approve}
                          className="flex items-center justify-center gap-2 bg-cloudo-warn hover:bg-cloudo-warn/90 text-cloudo-dark py-4 text-[11px] font-black uppercase tracking-[0.3em] transition-all disabled:opacity-30"
                        >
                          <HiOutlineCheck className="w-5 h-5" />
                          Sign and Authorize
                        </button>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="h-[400px] flex flex-col items-center justify-center border border-cloudo-border/10 bg-black/10 text-cloudo-muted/40">
                    <HiOutlineShieldCheck className="w-16 h-16 mb-4 opacity-10" />
                    <span className="text-sm font-black uppercase tracking-[0.4em]">Select request to audit</span>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Notifications Overlay */}
      <div className="fixed bottom-8 right-8 z-50 flex flex-col gap-3 pointer-events-none">
        {notifications.map((n) => (
          <div
            key={n.id}
            className={`flex items-center gap-3 px-6 py-4 border animate-in slide-in-from-right-full duration-300 pointer-events-auto ${
              n.type === 'success' ? 'bg-green-500/10 border-green-500 text-green-500' :
              n.type === 'error' ? 'bg-cloudo-err/10 border-cloudo-err text-cloudo-err' :
              'bg-cloudo-accent/10 border-cloudo-accent text-cloudo-accent'
            }`}
          >
            {n.type === 'success' && <HiOutlineCheck className="w-5 h-5" />}
            {n.type === 'error' && <HiOutlineExclamationCircle className="w-5 h-5" />}
            {n.type === 'info' && <HiOutlineInformationCircle className="w-5 h-5" />}
            <span className="text-xs font-black uppercase tracking-[0.2em]">{n.message}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function DetailItem({ label, value, icon }: { label: string, value: string, icon: React.ReactNode }) {
  return (
    <div className="bg-black/40 border border-cloudo-border p-3 space-y-2">
       <div className="flex items-center gap-2 text-cloudo-muted/60">
          <span className="text-sm">{icon}</span>
          <span className="text-[10px] font-black uppercase tracking-widest">{label}</span>
       </div>
       <div className="text-[11px] font-bold text-white truncate uppercase tracking-tighter">
          {value}
       </div>
    </div>
  );
}
