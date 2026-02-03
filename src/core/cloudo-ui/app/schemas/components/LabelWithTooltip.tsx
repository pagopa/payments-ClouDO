import React from "react";
import { HiOutlineExclamationCircle } from "react-icons/hi";

interface LabelWithTooltipProps {
  children: React.ReactNode;
  tooltip: string;
}

export function LabelWithTooltip({ children, tooltip }: LabelWithTooltipProps) {
  return (
    <label
      className="text-[11px] font-black uppercase tracking-widest text-cloudo-muted ml-1 flex items-center gap-2 group/label relative cursor-help"
      title={tooltip}
    >
      {children}
      <HiOutlineExclamationCircle className="w-3 h-3 opacity-40 group-hover/label:opacity-100 transition-opacity" />
    </label>
  );
}
