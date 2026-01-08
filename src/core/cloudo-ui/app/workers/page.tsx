"use client";

import { WorkersPanel } from "../components/WorkersPanel";

export default function WorkersPage() {
  return (
    <div className="flex flex-col h-full bg-[#0a0c10] text-cloudo-text font-sans selection:bg-cloudo-accent/30">
      <WorkersPanel />
    </div>
  );
}
