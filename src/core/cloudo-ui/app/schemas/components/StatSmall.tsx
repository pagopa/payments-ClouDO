import React from "react";

interface StatSmallProps {
  title: string;
  value: number;
  icon: React.ReactNode;
  label: string;
  color?: string;
}

export function StatSmall({
  title,
  value,
  icon,
  label,
  color = "text-cloudo-text",
}: StatSmallProps) {
  return (
    <div className="bg-cloudo-panel border border-cloudo-border p-5 flex items-center justify-between relative overflow-hidden group">
      <div className="absolute top-0 left-0 w-[2px] h-full bg-cloudo-accent/10 transition-colors" />
      <div className="relative z-10">
        <p className="text-[11px] font-black uppercase tracking-[0.2em] text-cloudo-muted/60 mb-1">
          {title}
        </p>
        <p className={`text-2xl font-black ${color} tracking-tighter`}>
          {value}
        </p>
        <p className="text-[11px] font-bold text-cloudo-muted/60 uppercase mt-1 tracking-widest">
          {label}
        </p>
      </div>
      <div className="p-2.5 bg-cloudo-accent/10 border border-cloudo-border text-lg shrink-0 transition-colors opacity-70">
        <div className="text-cloudo-accent w-5 h-5 flex items-center justify-center">
          {icon}
        </div>
      </div>
    </div>
  );
}
