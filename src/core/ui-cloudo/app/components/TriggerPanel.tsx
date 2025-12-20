'use client';

import { useState, useMemo } from 'react';
import {
  HiOutlinePlay,
  HiOutlineCode,
  HiOutlineBeaker,
  HiOutlineTrash,
  HiOutlineCheckCircle,
  HiOutlineExclamationCircle,
  HiOutlineRefresh,
  HiOutlineTerminal,
  HiOutlineTemplate
} from 'react-icons/hi';

const TEMPLATES = {
  azure_alert: {
    data: {
      essentials: {
        alertRule: "High CPU Usage",
        severity: "Sev2",
        monitorCondition: "Fired"
      }
    }
  },
  generic: {
    action: "start",
    params: {
      id: 123,
      debug: true
    }
  }
};

export function TriggerPanel() {
  const [triggerId, setTriggerId] = useState('');
  const [triggerBody, setTriggerBody] = useState('');
  const [response, setResponse] = useState('');
  const [loading, setLoading] = useState(false);

  const isJsonValid = useMemo(() => {
    if (!triggerBody.trim()) return true;
    try {
      JSON.parse(triggerBody);
      return true;
    } catch {
      return false;
    }
  }, [triggerBody]);

  const loadTemplate = (key: keyof typeof TEMPLATES) => {
    setTriggerBody(JSON.stringify(TEMPLATES[key], null, 2));
  };

  const executeTrigger = async () => {
    if (!isJsonValid) return;
    setLoading(true);
    setResponse('');

    try {
      const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:7071/api';
      const url = `${API_URL}/Trigger${triggerId ? `?id=${triggerId}` : ''}`;
      const options: RequestInit = {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      };

      if (triggerBody.trim()) {
        options.body = triggerBody;
      }

      const res = await fetch(url, options);
      const text = await res.text();
      let formattedRes = text;
      try {
        formattedRes = JSON.stringify(JSON.parse(text), null, 2);
      } catch { /* not json */ }

      setResponse(`HTTP ${res.status}\n\n${formattedRes}`);
    } catch (error) {
      setResponse(`Error: ${error}`);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      if (!loading && isJsonValid) {
        executeTrigger();
      }
    }
  };

  return (
    <div className="space-y-6">
      <form onSubmit={(e) => { e.preventDefault(); if (!loading && isJsonValid) executeTrigger(); }} className="bg-[#0d1117]/40 border border-cloudo-border/20 rounded-xl overflow-hidden shadow-2xl">
        {/* Panel Header */}
        <div className="px-6 py-4 border-b border-cloudo-border/20 flex justify-between items-center bg-white/[0.02]">
          <div className="flex items-center gap-3">
            <HiOutlineBeaker className="text-cloudo-accent w-4 h-4" />
            <h2 className="text-[10px] font-black uppercase tracking-[0.2em] text-white">Execution Parameters</h2>
          </div>
          <div className="flex gap-4">
            <button
              type="button"
              onClick={() => loadTemplate('azure_alert')}
              className="flex items-center gap-1.5 text-[9px] font-black uppercase tracking-widest text-cloudo-muted hover:text-cloudo-accent transition-colors"
            >
              <HiOutlineTemplate className="w-3.5 h-3.5" />
              Azure Alert
            </button>
            <button
              type="button"
              onClick={() => setTriggerBody('')}
              className="flex items-center gap-1.5 text-[9px] font-black uppercase tracking-widest text-cloudo-muted hover:text-red-400 transition-colors"
            >
              <HiOutlineTrash className="w-3.5 h-3.5" />
              Reset Body
            </button>
          </div>
        </div>

        {/* Form Body */}
        <div className="p-8 space-y-8">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
            <div className="md:col-span-1 space-y-2">
              <label className="text-[10px] font-black uppercase tracking-widest text-cloudo-muted ml-1">Logic ID (Query)</label>
              <input
                type="text"
                className="w-full bg-black/40 border border-cloudo-border/50 rounded-md px-4 py-2.5 text-xs font-mono text-cloudo-accent outline-none focus:border-cloudo-accent/60 focus:ring-1 focus:ring-cloudo-accent/20 transition-all"
                placeholder="test-run-01"
                value={triggerId}
                onChange={(e) => setTriggerId(e.target.value)}
              />
            </div>

            <div className="md:col-span-3 space-y-2">
              <div className="flex justify-between items-center ml-1">
                <label className="text-[10px] font-black uppercase tracking-widest text-cloudo-muted">Input Data Payload (JSON)</label>
                <span className={`text-[9px] font-black uppercase flex items-center gap-1 ${isJsonValid ? 'text-cloudo-ok' : 'text-red-400'}`}>
                  {isJsonValid ? <HiOutlineCheckCircle /> : <HiOutlineExclamationCircle />}
                  {isJsonValid ? 'Structural Check: Valid' : 'Syntax Error'}
                </span>
              </div>
              <div className="relative">
                <HiOutlineCode className="absolute top-3.5 left-3.5 text-cloudo-muted opacity-30 w-4 h-4" />
                <textarea
                  className={`w-full bg-black/40 border rounded-md pl-11 pr-4 py-4 font-mono text-xs min-h-[200px] outline-none transition-all ${
                    !isJsonValid ? 'border-red-500/30 focus:border-red-500/50 focus:ring-red-500/10' : 'border-cloudo-border/50 focus:border-cloudo-accent/60 focus:ring-1 focus:ring-cloudo-accent/20'
                  }`}
                  placeholder='{ "action": "test", "params": {} }'
                  value={triggerBody}
                  onChange={(e) => setTriggerBody(e.target.value)}
                  onKeyDown={handleKeyDown}
                />
              </div>
            </div>
          </div>

          <div className="flex justify-end pt-4 border-t border-cloudo-border/10">
            <button
              type="submit"
              disabled={loading || !isJsonValid}
              className="bg-cloudo-accent hover:bg-cloudo-accent/90 text-white min-w-[180px] h-11 rounded-md text-[10px] font-black uppercase tracking-[0.2em] transition-all flex items-center justify-center gap-3 shadow-xl shadow-cloudo-accent/10 disabled:opacity-30"
            >
              {loading ? (
                <HiOutlineRefresh className="animate-spin w-4 h-4" />
              ) : (
                <HiOutlinePlay className="w-4 h-4" />
              )}
              {loading ? 'Executing Runbook...' : 'Commit Execution'}
            </button>
          </div>
        </div>
      </form>

      {/* Terminal Response Section */}
      {response && (
        <div className="animate-in slide-in-from-bottom duration-300">
          <div className="flex items-center gap-2 mb-3 ml-1">
            <HiOutlineTerminal className="text-cloudo-muted w-3.5 h-3.5" />
            <h3 className="text-[10px] font-black uppercase tracking-widest text-cloudo-muted">System Output</h3>
          </div>
          <div className="bg-[#080a0f] border border-cloudo-border/40 rounded-xl overflow-hidden shadow-2xl">
            <pre className="p-6 text-[11px] font-mono text-cloudo-text leading-relaxed whitespace-pre-wrap max-h-[400px] overflow-auto custom-scrollbar">
              {response}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
