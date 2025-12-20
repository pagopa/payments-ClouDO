'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useState } from 'react';
import {
  HiOutlineChevronDoubleLeft,
  HiOutlineChevronDoubleRight,
  HiOutlineLogout,
  HiOutlineChartBar,
  HiOutlineCog,
  HiOutlineTerminal,
  HiOutlineCollection,
  HiOutlineChip,
  HiOutlineLightningBolt,
  HiOutlineViewGrid,
  HiOutlineShieldCheck
} from "react-icons/hi";

interface NavItem {
  name: string;
  href: string;
  icon: JSX.Element;
  badge?: number;
}

const navigation: NavItem[] = [
  { name: 'Dashboard', href: '/', icon: <HiOutlineViewGrid /> },
  { name: 'Execute Trigger', href: '/trigger', icon: <HiOutlineLightningBolt /> },
  { name: 'Governance Gate', href: '/approvals', icon: <HiOutlineShieldCheck /> },
  { name: 'Registry', href: '/schemas', icon: <HiOutlineCollection /> },
  { name: 'Executions', href: '/executions', icon: <HiOutlineTerminal /> },
  { name: 'Compute Nodes', href: '/workers', icon: <HiOutlineChip /> },
];

export function Sidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div
      className={`${
        collapsed ? 'w-20' : 'w-64'
      } bg-[#0d1117] border-r border-cloudo-border/20 flex flex-col transition-all duration-300 h-screen sticky top-0 z-30 font-sans`}
    >
      {/* Header - Brand Layer */}
      <div className="p-6 border-b border-cloudo-border/10 flex items-center justify-between bg-white/[0.01]">
        {!collapsed && (
          <div className="animate-in fade-in duration-500">
            <h1 className="text-lg font-black text-white tracking-tighter flex items-center gap-2 uppercase">
              <span className="text-cloudo-accent">Clou</span>DO
            </h1>
            <p className="text-[10px] text-cloudo-muted font-black uppercase tracking-[0.3em] opacity-60">Runbook Automation</p>
          </div>
        )}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="p-2 hover:bg-white/5 rounded-md text-cloudo-muted hover:text-white transition-all border border-transparent hover:border-cloudo-border/20"
          title={collapsed ? 'Expand Workspace' : 'Collapse Workspace'}
        >
          {collapsed ? <HiOutlineChevronDoubleRight className="w-4 h-4" /> : <HiOutlineChevronDoubleLeft className="w-4 h-4" />}
        </button>
      </div>

      {/* Navigation - Strategic Layer */}
      <nav className="flex-1 p-4 space-y-6 overflow-y-auto custom-scrollbar">
        <div className="space-y-1">
          {!collapsed && (
            <p className="px-3 text-[9px] font-black text-cloudo-muted uppercase tracking-[0.2em] mb-3 opacity-40">Main Operations</p>
          )}
          {navigation.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.name}
                href={item.href}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-md transition-all group relative ${
                  isActive
                    ? 'bg-cloudo-accent/10 text-cloudo-accent border border-cloudo-accent/20'
                    : 'text-cloudo-muted hover:bg-white/[0.03] hover:text-white border border-transparent'
                }`}
              >
                <span className={`text-xl transition-transform group-hover:scale-110 ${isActive ? 'text-cloudo-accent' : 'opacity-70'}`}>
                  {item.icon}
                </span>
                {!collapsed && (
                  <>
                    <span className={`text-[11px] font-black uppercase tracking-widest flex-1 ${isActive ? 'text-white' : ''}`}>
                      {item.name}
                    </span>
                    {item.badge && (
                      <span className="bg-cloudo-accent text-white text-[9px] font-black px-1.5 py-0.5 rounded shadow-[0_0_10px_rgba(var(--cloudo-accent-rgb),0.3)]">
                        {item.badge}
                      </span>
                    )}
                  </>
                )}
                {isActive && (
                  <div className="absolute left-0 w-[2px] h-4 bg-cloudo-accent rounded-full -ml-[1px]" />
                )}
              </Link>
            );
          })}
        </div>
      </nav>

      {/* Footer - Identity Layer */}
      <div className="p-4 border-t border-cloudo-border/10 bg-white/[0.01]">
        {!collapsed ? (
          <div className="flex items-center gap-4 p-2 rounded-lg bg-black/20 border border-white/[0.03]">
            <div className="w-9 h-9 bg-cloudo-accent/10 border border-cloudo-accent/30 rounded flex items-center justify-center text-cloudo-accent font-black text-xs">
              AD
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-[10px] font-black text-white uppercase tracking-wider truncate">Administrator</p>
              <p className="text-[9px] text-cloudo-muted uppercase font-bold tracking-tighter opacity-60">System Root</p>
            </div>
            <button
              className="p-2 hover:bg-red-500/10 rounded text-cloudo-muted hover:text-red-500 transition-colors"
              title="Terminate Session"
            >
              <HiOutlineLogout className="w-4 h-4" />
            </button>
          </div>
        ) : (
          <div className="flex justify-center py-2">
            <div className="w-9 h-9 bg-cloudo-accent/10 border border-cloudo-accent/30 rounded flex items-center justify-center text-cloudo-accent font-black text-xs hover:bg-cloudo-accent/20 cursor-pointer transition-all">
              AD
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
