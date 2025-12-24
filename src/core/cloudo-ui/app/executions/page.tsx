'use client';

import { LogsPanel } from '../components/LogsPanel';
import { HiOutlineTerminal } from "react-icons/hi";

export default function ExecutionsPage() {
  return (
    <div className="flex flex-col h-full bg-cloudo-dark text-cloudo-text font-mono selection:bg-cloudo-accent/30">
      {/* Header Bar - Solid Technical Style */}
      <div className="flex items-center justify-between px-8 py-5 border-b border-cloudo-border bg-cloudo-panel sticky top-0 z-20">
        <div className="flex items-center gap-4 shrink-0">
          <div className="p-2 bg-cloudo-accent/5 border border-cloudo-accent/20 shrink-0">
            <HiOutlineTerminal className="text-cloudo-accent w-5 h-5" />
          </div>
          <div>
            <h1 className="text-sm font-black tracking-[0.2em] text-cloudo-text uppercase">Execution Archive</h1>
            <p className="text-[11px] text-cloudo-muted font-black uppercase tracking-[0.3em] opacity-70">Historical Telemetry // LOG_STORAGE</p>
          </div>
        </div>
      </div>
      <div className="flex-1 overflow-hidden p-4">
        <LogsPanel />
      </div>
    </div>
  );
}
