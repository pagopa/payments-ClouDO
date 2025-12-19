'use client';

import { TriggerPanel } from '../components/TriggerPanel';
import { HiOutlineLightningBolt } from "react-icons/hi";

export default function TriggerPage() {
  return (
    <div className="flex flex-col h-full bg-[#0a0c10] text-cloudo-text font-sans">
      {/* Header Bar - Solid Tech Style */}
      <div className="flex items-center justify-between px-8 py-5 border-b border-cloudo-border/20 bg-[#0d1117]/80 backdrop-blur-xl sticky top-0 z-20">
        <div className="flex items-center gap-4">
          <div className="p-2 bg-cloudo-accent/10 rounded-lg border border-cloudo-accent/20">
            <HiOutlineLightningBolt className="text-cloudo-accent w-5 h-5" />
          </div>
          <div>
            <h1 className="text-sm font-bold tracking-tight text-white uppercase">Manual Trigger Engine</h1>
            <p className="text-[10px] text-cloudo-muted font-black uppercase tracking-[0.2em] opacity-60">Ad-hoc runbook invocation</p>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-8">
        <div className="max-w-[1200px] mx-auto">
          <TriggerPanel />
        </div>
      </div>
    </div>
  );
}
