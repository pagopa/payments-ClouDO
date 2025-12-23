'use client';

import { useState, useMemo } from 'react';
import {
  HiOutlinePlay,
  HiOutlineCode,
  HiOutlineBeaker,
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
        alertRule: "test",
        severity: "Sev4",
        monitorCondition: "Fired",
        alertTargetIDs: [
          "/subscriptions/00000000-0000-0000-0000-000000000001/resourcegroups/test-RG/providers/microsoft.operationalinsights/workspaces/test-logAnalyticsWorkspace"
        ]
      },
      alertContext: {
        labels: {
          alertname: "KubeHpaMaxedOut",
          cluster: "pagopa-d-weu-dev-aks",
          horizontalpodautoscaler: "keda-hpa-pagopa-mbd-service",
          instance: "ama-metrics-ksm.kube-system.svc.cluster.local:8080",
          job: "kube-state-metrics",
          deployment: "apisix-dashboard",
          namespace: "nonamespace",
          resourcename: "pagopa-d-weu-dev-aks",
          resourcegroup: "pagopa-d-weu-dev-aks-rg"
        }
      }
    }
  },
  elastic_alert: {
    data: {
      essentials: {
        alertRule: "restart-pod",
        severity: "Sev1",
        monitorCondition: "Fired",
        logs: "{{context.hits}}",
        type: "aks"
      },
      alertContext: {
        labels: {
          deployment: "cache-postgresql",
          namespace: "apiconfig",
          region: "westeurope",
          resourcegroup: "pagopa-d-weu-dev-aks-rg",
          resourcename: "pagopa-d-weu-dev-aks"
        }
      }
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
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
      <div className="lg:col-span-8 space-y-6">
        <form onSubmit={(e) => { e.preventDefault(); if (!loading && isJsonValid) executeTrigger(); }} className="bg-cloudo-panel border border-cloudo-border shadow-sm">
          {/* Panel Header */}
          <div className="px-6 py-4 border-b border-cloudo-border flex justify-between items-center bg-cloudo-panel-2">
            <div className="flex items-center gap-2">
              <HiOutlineBeaker className="text-cloudo-accent w-5 h-5" />
              <h2 className="text-sm font-semibold text-white tracking-tight">Request Configuration</h2>
            </div>
            <div className="flex gap-4">
              <button
                type="button"
                onClick={() => setTriggerBody('')}
                className="text-[11px] font-medium text-cloudo-muted hover:text-cloudo-err transition-colors"
              >
                Clear Body
              </button>
            </div>
          </div>

          {/* Form Body */}
          <div className="p-6 space-y-6">
            <div className="space-y-4">
              <div className="flex flex-col gap-1.5">
                <label className="text-[12px] font-semibold text-cloudo-muted uppercase tracking-wider">Target Endpoint ID</label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <span className="text-cloudo-muted text-xs font-mono">ID:</span>
                  </div>
                  <input
                    type="text"
                    className="input pl-10 h-10 bg-black/20"
                    placeholder="e.g. process-transaction-01"
                    value={triggerId}
                    onChange={(e) => setTriggerId(e.target.value)}
                  />
                </div>
                <p className="text-[11px] text-cloudo-muted italic opacity-60">Specify the unique identifier for the logic execution context.</p>
              </div>

              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <label className="text-[12px] font-semibold text-cloudo-muted uppercase tracking-wider">Payload (JSON)</label>
                  <span className={`text-[11px] font-medium flex items-center gap-1.5 ${isJsonValid ? 'text-cloudo-ok' : 'text-cloudo-err'}`}>
                    {isJsonValid ? <HiOutlineCheckCircle className="w-3.5 h-3.5" /> : <HiOutlineExclamationCircle className="w-3.5 h-3.5" />}
                    {isJsonValid ? 'JSON Schema Valid' : 'Invalid Syntax'}
                  </span>
                </div>
                <div className="relative border border-cloudo-border focus-within:border-cloudo-accent/50 transition-colors">
                  <textarea
                    className={`w-full bg-black/30 p-4 font-mono text-xs min-h-[300px] outline-none resize-y ${
                      !isJsonValid ? 'text-cloudo-err' : 'text-cloudo-text'
                    }`}
                    placeholder='{
  "action": "execute",
  "metadata": {
    "source": "manual-console"
  }
}'
                    value={triggerBody}
                    onChange={(e) => setTriggerBody(e.target.value)}
                    onKeyDown={handleKeyDown}
                  />
                </div>
              </div>
            </div>

            <div className="flex justify-end pt-4">
              <button
                type="submit"
                disabled={loading || !isJsonValid}
                className={`btn btn-primary h-10 px-8 flex items-center gap-2 normal-case tracking-tight font-semibold ${loading ? 'opacity-70' : ''}`}
              >
                {loading ? (
                  <HiOutlineRefresh className="animate-spin w-4 h-4" />
                ) : (
                  <HiOutlinePlay className="w-4 h-4" />
                )}
                {loading ? 'Processing...' : 'Run Request'}
              </button>
            </div>
          </div>
        </form>

        {/* Terminal Response Section */}
        {response && (
          <div className="animate-in fade-in slide-in-from-bottom-2 duration-300">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <HiOutlineTerminal className="text-cloudo-accent w-4 h-4" />
                <h3 className="text-[12px] font-semibold text-cloudo-muted uppercase tracking-wider">Response Stream</h3>
              </div>
              <div className="text-[10px] font-mono text-cloudo-muted opacity-50">
                TIMESTAMP: {new Date().toISOString()}
              </div>
            </div>
            <div className="bg-[#0d1117] border border-cloudo-border rounded-sm overflow-hidden">
              <div className="flex items-center gap-1 px-3 py-1.5 bg-black/40 border-b border-cloudo-border">
                <div className="w-2.5 h-2.5 rounded-full bg-cloudo-err/20 border border-cloudo-err/40" />
                <div className="w-2.5 h-2.5 rounded-full bg-cloudo-warn/20 border border-cloudo-warn/40" />
                <div className="w-2.5 h-2.5 rounded-full bg-cloudo-ok/20 border border-cloudo-ok/40" />
              </div>
              <pre className="p-5 text-[13px] font-mono text-cloudo-text leading-relaxed whitespace-pre-wrap max-h-[600px] overflow-auto custom-scrollbar">
                {response}
              </pre>
            </div>
          </div>
        )}
      </div>

      <div className="lg:col-span-4 space-y-6">
        <div className="bg-cloudo-panel border border-cloudo-border p-5">
          <div className="flex items-center gap-2 mb-4 border-b border-cloudo-border pb-3">
            <HiOutlineTemplate className="text-cloudo-accent w-4 h-4" />
            <h3 className="text-xs font-semibold text-white uppercase tracking-wider">Templates</h3>
          </div>
          <div className="space-y-2">
            {Object.keys(TEMPLATES).map((key) => (
              <button
                key={key}
                type="button"
                onClick={() => loadTemplate(key as keyof typeof TEMPLATES)}
                className="w-full text-left p-3 border border-cloudo-border bg-black/20 hover:border-cloudo-accent/50 hover:bg-cloudo-accent/5 transition-all group"
              >
                <div className="text-[11px] font-bold text-cloudo-muted group-hover:text-cloudo-accent uppercase mb-1">
                  {key.replace('_', ' ')}
                </div>
                <div className="text-[10px] text-cloudo-muted opacity-60 truncate">
                  Pre-configured payload for {key} integration.
                </div>
              </button>
            ))}
          </div>
        </div>

        <div className="bg-cloudo-panel/50 border border-cloudo-border p-5 border-dashed">
          <h4 className="text-[11px] font-bold text-cloudo-muted uppercase mb-3">Developer Quick Reference</h4>
          <div className="space-y-3 text-[11px] text-cloudo-muted leading-relaxed">
            <div className="flex gap-2">
              <span className="text-cloudo-accent">⌘+Enter</span>
              <span>Execute current request</span>
            </div>
            <div className="flex gap-2">
              <span className="text-cloudo-accent">POST</span>
              <span>All requests use POST method</span>
            </div>
            <div className="pt-2 border-t border-cloudo-border/30">
              Chiamata verso il servizio orchestratore per l'attivazione manuale dei flussi di lavoro definiti nel sistema.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
