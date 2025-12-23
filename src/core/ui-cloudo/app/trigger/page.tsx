'use client';

import { TriggerPanel } from '../components/TriggerPanel';
import { HiOutlineLightningBolt } from "react-icons/hi";

export default function TriggerPage() {
  return (
    <div className="flex flex-col h-full bg-cloudo-dark text-cloudo-text font-sans selection:bg-cloudo-accent/30">
      {/* Header Bar - Enterprise Style */}
      <div className="flex items-center justify-between px-8 py-4 border-b border-cloudo-border bg-cloudo-panel sticky top-0 z-20">
        <div className="flex items-center gap-4 shrink-0">
          <div className="p-2 bg-cloudo-accent/10 border border-cloudo-accent/20 rounded-md shrink-0">
            <HiOutlineLightningBolt className="text-cloudo-accent w-5 h-5" />
          </div>
          <div>
            <h1 className="text-lg font-semibold tracking-tight text-white">Service Trigger Console</h1>
            <p className="text-[12px] text-cloudo-muted font-medium opacity-70">Execute and monitor ad-hoc orchestration workflows</p>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-8">
        <div className="max-w-[1400px] mx-auto">
          <TriggerPanel />
        </div>
      </div>
    </div>
  );
}
