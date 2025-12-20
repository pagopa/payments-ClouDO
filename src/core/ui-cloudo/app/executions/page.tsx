'use client';

import { LogsPanel } from '../components/LogsPanel';
import { MdOutlineSchema } from "react-icons/md";

export default function ExecutionsPage() {
  return (
    <div className="flex flex-col h-full bg-[#0a0c10] text-cloudo-text font-sans selection:bg-cloudo-accent/30">
      {/* Top Bar - High Density UI */}
      <div className="flex items-center justify-between px-8 py-4 border-b border-cloudo-border/20 bg-[#0d1117]/80 backdrop-blur-xl sticky top-0 z-20">
        <div className="flex items-center gap-4">
          <div>
            <h1 className="text-sm font-bold tracking-tight text-white uppercase">Execution History</h1>
            <p className="text-[10px] text-cloudo-muted font-bold uppercase tracking-[0.2em] opacity-60">Query and analyze runbook execution logs</p>
          </div>
        </div>
      </div>
      <LogsPanel />
    </div>
  );
}
