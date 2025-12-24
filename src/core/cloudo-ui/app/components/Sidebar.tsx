'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useState, useEffect } from 'react';
import {
  HiOutlineChevronDoubleLeft,
  HiOutlineChevronDoubleRight,
  HiOutlineLogout,
  HiOutlineChartBar,
  HiOutlineCog,
  HiOutlineTerminal,
  HiOutlineCode,
  HiOutlineCollection,
  HiOutlineChip,
  HiOutlineLightningBolt,
  HiOutlineViewGrid,
  HiOutlineShieldCheck,
  HiOutlineUsers,
  HiOutlineClipboardList,
  HiOutlineClock,
} from "react-icons/hi";

interface NavItem {
  name: string;
  href: string;
  icon: React.ReactNode;
  badge?: number;
  adminOnly?: boolean;
}

const navigation: NavItem[] = [
  { name: 'Dashboard', href: '/', icon: <HiOutlineViewGrid /> },
  { name: 'Schemas', href: '/schemas', icon: <HiOutlineCollection /> },
  { name: 'Governance Gate', href: '/approvals', icon: <HiOutlineShieldCheck /> },
  { name: 'Schedules', href: '/schedules', icon: <HiOutlineClock /> },
  { name: 'Runbook Studio', href: '/studio', icon: <HiOutlineCode /> },
  { name: 'Executions', href: '/executions', icon: <HiOutlineTerminal /> },
  { name: 'Compute Nodes', href: '/workers', icon: <HiOutlineChip /> },
  { name: 'Analytics', href: '/analytics', icon: <HiOutlineChartBar /> },
  { name: 'Users', href: '/users', icon: <HiOutlineUsers />, adminOnly: true },
  { name: 'Audit Logs', href: '/audit', icon: <HiOutlineClipboardList />, adminOnly: true },
  { name: 'Settings', href: '/settings', icon: <HiOutlineCog />, adminOnly: true },
];

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const [collapsed, setCollapsed] = useState(false);
  const [user, setUser] = useState<{username: string, email: string, role: string} | null>(null);

  useEffect(() => {
    const userData = localStorage.getItem('cloudo_user');
    if (userData) {
      try {
        setUser(JSON.parse(userData));
      } catch (e) {
        console.error("Failed to parse user data", e);
      }
    }
  }, []);

  const handleLogout = () => {
    localStorage.removeItem('cloudo_auth');
    localStorage.removeItem('cloudo_user');
    router.push('/login');
  };

  return (
    <div
      className={`${
        collapsed ? 'w-20' : 'w-64'
      } bg-cloudo-dark border-r border-cloudo-border flex flex-col transition-all duration-300 h-screen sticky top-0 z-30 font-mono`}
    >
      {/* Header - Brand Layer */}
      <div className="p-6 border-b border-cloudo-border flex items-center justify-between bg-black/20">
        {!collapsed && (
          <div className="animate-in fade-in duration-500">
            <h1 className="text-xl font-black text-white tracking-[0.1em] flex items-center gap-2 uppercase">
              <span className="text-cloudo-accent">Clou</span>DO
            </h1>
            <p className="text-[11px] text-cloudo-muted font-bold uppercase tracking-[0.3em] opacity-70 mt-1">Runbook Engine</p>
          </div>
        )}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="p-2 hover:bg-cloudo-accent hover:text-cloudo-dark text-cloudo-muted transition-all border border-cloudo-border"
          title={collapsed ? 'Expand' : 'Collapse'}
        >
          {collapsed ? <HiOutlineChevronDoubleRight className="w-4 h-4" /> : <HiOutlineChevronDoubleLeft className="w-4 h-4" />}
        </button>
      </div>

      {/* Navigation - Strategic Layer */}
      <nav className="flex-1 p-4 space-y-6 overflow-y-auto custom-scrollbar">
        {/* Core Section */}
        <div className="space-y-1">
          {!collapsed && (
            <p className="px-3 text-[11px] font-black text-cloudo-muted/70 uppercase tracking-[0.2em] mb-4">Core Systems</p>
          )}
          {navigation.filter(item => !item.adminOnly).map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.name}
                href={item.href}
                className={`flex items-center gap-3 px-3 py-3 transition-all group relative border ${
                  isActive
                    ? 'bg-cloudo-accent/5 text-cloudo-accent border-cloudo-accent/30 shadow-[inset_0_0_10px_rgba(88,166,255,0.05)]'
                    : 'text-cloudo-muted hover:bg-white/5 hover:text-white border-transparent'
                }`}
              >
                <span className={`text-lg shrink-0 ${isActive ? 'text-cloudo-accent' : 'opacity-50'}`}>
                  {item.icon}
                </span>
                {!collapsed && (
                  <span className={`text-sm font-bold uppercase tracking-[0.2em] flex-1 ${isActive ? 'text-white' : ''}`}>
                    {item.name}
                  </span>
                )}
                {isActive && (
                  <div className="absolute left-[-1px] w-[2px] h-6 bg-cloudo-accent" />
                )}
              </Link>
            );
          })}
        </div>

        {/* Admin Section */}
        {user?.role === 'ADMIN' && (
          <div className="space-y-1 pt-4">
            {!collapsed && (
              <p className="px-3 text-[11px] font-black text-cloudo-muted/70 uppercase tracking-[0.2em] mb-4">Administration</p>
            )}
            {navigation.filter(item => item.adminOnly).map((item) => {
              const isActive = pathname === item.href;
              return (
                <Link
                  key={item.name}
                  href={item.href}
                  className={`flex items-center gap-3 px-3 py-3 transition-all group relative border ${
                    isActive
                      ? 'bg-cloudo-accent/5 text-cloudo-accent border-cloudo-accent/30 shadow-[inset_0_0_10px_rgba(88,166,255,0.05)]'
                      : 'text-cloudo-muted hover:bg-white/5 hover:text-white border-transparent'
                  }`}
                >
                  <span className={`text-lg shrink-0 ${isActive ? 'text-cloudo-accent' : 'opacity-50'}`}>
                    {item.icon}
                  </span>
                  {!collapsed && (
                    <span className={`text-sm font-bold uppercase tracking-[0.2em] flex-1 ${isActive ? 'text-white' : ''}`}>
                      {item.name}
                    </span>
                  )}
                  {isActive && (
                    <div className="absolute left-[-1px] w-[2px] h-6 bg-cloudo-accent" />
                  )}
                </Link>
              );
            })}
          </div>
        )}
      </nav>

      {/* Footer - Identity Layer */}
      <div className="p-4 border-t border-cloudo-border bg-black/20">
        {!collapsed ? (
          <div className="flex items-center gap-4 p-3 bg-black/40 border border-cloudo-border">
            <div className="w-8 h-8 bg-cloudo-accent text-cloudo-dark flex items-center justify-center font-black text-[11px] shrink-0 uppercase">
              {user?.username?.slice(0, 2) || '??'}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-[12px] font-black text-white uppercase tracking-widest truncate">
                {user?.username || 'Unknown User'}
              </p>
              <p className="text-[11px] text-cloudo-muted uppercase font-bold tracking-widest opacity-70">
                {user?.role || 'L-GUEST'}
              </p>
            </div>
            <button
              onClick={handleLogout}
              className="p-2 hover:bg-cloudo-err hover:text-white text-cloudo-muted transition-colors border border-cloudo-border"
              title="Logout"
            >
              <HiOutlineLogout className="w-4 h-4" />
            </button>
          </div>
        ) : (
          <div className="flex justify-center py-2">
            <button
              onClick={handleLogout}
              className="w-10 h-10 bg-black/40 border border-cloudo-border flex items-center justify-center text-cloudo-muted hover:bg-cloudo-err hover:text-white transition-all"
              title="Logout"
            >
              <HiOutlineLogout className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
