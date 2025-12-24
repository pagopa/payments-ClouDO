'use client';

import { useState, useEffect } from 'react';
import {
  HiOutlineCode,
  HiOutlineTerminal,
  HiOutlineClipboardCopy,
  HiOutlineCheck,
  HiOutlineDownload,
  HiOutlineLightBulb,
  HiOutlineBookOpen,
  HiOutlineDocumentText,
  HiOutlineVariable,
  HiOutlineCube,
  HiOutlineSearch,
  HiOutlinePlus,
  HiOutlineArrowRight,
  HiOutlineExclamationCircle,
  HiOutlineX,
  HiOutlineInformationCircle,
  HiOutlineShieldCheck,
  HiOutlinePlay,
  HiOutlineDatabase,
  HiOutlineClipboardList
} from "react-icons/hi";

interface Suggestion {
  id: string;
  type: 'info' | 'warning' | 'success';
  text: string;
  impact: string;
}

const TEMPLATES = [
  {
    id: 'py-alert',
    name: 'Python Alert Handler',
    lang: 'python',
    description: 'Ottimizzato per gestire allarmi da Azure Monitor o sistemi esterni.',
    code: `#!/usr/bin/env python3
"""
ClouDO Python Template: Alert Handler
Questo script processa i payload JSON inviati dai sistemi di monitoraggio.
"""
import json
import logging
import os
import sys

# Configurazione logging su stderr per visibilità in console ClouDO
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def main():
    # ClouDO passa il payload via variabile d'ambiente CLOUDO_PAYLOAD
    try:
        input_data = os.environ.get('CLOUDO_PAYLOAD', '{}')
        payload = json.loads(input_data)
    except Exception as e:
        logging.error(f"Failed to parse input: {e}")
        sys.exit(1)

    logging.info("--- CLOUDO OPERATIONAL STREAM START ---")

    # Esempio: Estrazione dati da un allarme Azure
    essentials = payload.get('data', {}).get('essentials', {})
    alert_rule = essentials.get('alertRule', 'Unknown Rule')
    severity = essentials.get('severity', 'N/A')

    logging.info(f"SIGNAL_DETECTED: {alert_rule}")
    logging.info(f"SEVERITY_LEVEL: {severity}")

    # --- TUA LOGICA QUI ---
    # Esempio: Ripristino servizio, pulizia log, etc.

    logging.info("AUTOMATION_LOGIC_EXECUTED")
    print("SUCCESS: Runbook completed successfully")

if __name__ == "__main__":
    main()`
  },
  {
    id: 'sh-manual',
    name: 'Bash Manual Script',
    lang: 'bash',
    description: 'Script robusto per esecuzioni manuali veloci e diagnostica.',
    code: `#!/bin/bash
# ClouDO Bash Template: Manual Execution
# Utilizzato per task ad-hoc sui nodi del cluster.

echo "--- CLOUDO SYSTEM DIAGNOSTICS ---"
echo "NODE_IDENTIFIER: $(hostname)"
echo "EXECUTION_TIME: $(date)"
echo "OPERATOR_CONTEXT: $USER"

# Il payload JSON è disponibile via variabile d'ambiente CLOUDO_PAYLOAD
PAYLOAD=$CLOUDO_PAYLOAD

echo "RAW_PAYLOAD_RECEIVED: $PAYLOAD"

# Funzione per simulare un'operazione tecnica
perform_health_check() {
    echo "STATUS: VERIFYING_FILESYSTEM..."
    df -h | grep '^/'
    sleep 1
    echo "STATUS: CHECKING_RESOURCES..."
    free -m
}

perform_health_check

echo "--------------------------------"
echo "RESULT: COMPLIANT"
echo "ClouDO_EXEC_STATUS: OK"
exit 0`
  },
  {
    id: 'py-minimal',
    name: 'Python Minimal',
    lang: 'python',
    description: 'Template essenziale per script personalizzati ad alte prestazioni.',
    code: `#!/usr/bin/env python3
import json
import os
import sys

# ClouDO Data Ingestion
payload = json.loads(os.environ.get('CLOUDO_PAYLOAD', '{}'))

# Logic Block
def run():
    print(f"ClouDO Engine v4.0 Active")
    print(f"Processing payload: {payload}")
    # Insert code here

if __name__ == "__main__":
    run()`
  }
];

export default function StudioPage() {
  const [selectedTemplate, setSelectedTemplate] = useState(TEMPLATES[0]);
  const [code, setCode] = useState(TEMPLATES[0].code);
  const [copied, setCopied] = useState(false);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [payload, setPayload] = useState('{\n  "data": {\n    "essentials": {\n      "alertRule": "HighCPU-Production",\n      "severity": "Sev2"\n    }\n  }\n}');
  const [simulationOutput, setSimulationOutput] = useState<string[]>([]);
  const [isSimulating, setIsSimulating] = useState(false);
  const [rightTab, setRightTab] = useState<'simulator' | 'handbook'>('simulator');
  const [jsonError, setJsonError] = useState<string | null>(null);
  const [notifications, setNotifications] = useState<{id: number, type: string, message: string}[]>([]);

  const addNotification = (type: 'success' | 'error' | 'info', message: string) => {
    const id = Date.now();
    setNotifications(prev => [...prev, { id, type, message }]);
    setTimeout(() => {
      setNotifications(prev => prev.filter(n => n.id !== id));
    }, 5000);
  };

  useEffect(() => {
    try {
      JSON.parse(payload);
      setJsonError(null);
    } catch (e: any) {
      setJsonError(e.message);
    }
  }, [payload]);

  useEffect(() => {
    analyzeCode(code, selectedTemplate.lang);
  }, [code, selectedTemplate]);

  const analyzeCode = (content: string, lang: string) => {
    const newSuggestions: Suggestion[] = [];

    if (lang === 'python') {
      if (!content.includes('import logging')) {
        newSuggestions.push({
          id: 'py-logging',
          type: 'warning',
          text: 'Manca il modulo logging.',
          impact: 'Difficile monitorare l\'esecuzione nel Worker.'
        });
      }
      if (content.includes('print(') && !content.includes('sys.stderr')) {
        newSuggestions.push({
          id: 'py-stderr',
          type: 'info',
          text: 'Usa stderr per i log di debug.',
          impact: 'Evita di sporcare lo stdout destinato ai dati.'
        });
      }
      if (!content.includes('try:') || !content.includes('except')) {
        newSuggestions.push({
          id: 'py-error',
          type: 'warning',
          text: 'Nessuna gestione eccezioni rilevata.',
          impact: 'Lo script potrebbe fallire silenziosamente.'
        });
      }
      if (content.includes('CLOUDO_PAYLOAD') && !content.includes('json.loads')) {
        newSuggestions.push({
          id: 'py-json',
          type: 'warning',
          text: 'Payload non parsato come JSON.',
          impact: 'Accesso ai dati inefficace.'
        });
      }
    } else if (lang === 'bash') {
      if (!content.includes('set -e')) {
        newSuggestions.push({
          id: 'sh-set-e',
          type: 'info',
          text: 'Consigliato "set -e" all\'inizio.',
          impact: 'Interrompe lo script al primo errore.'
        });
      }
      if (!content.includes('>&2') && content.includes('echo')) {
        newSuggestions.push({
          id: 'sh-stderr',
          type: 'info',
          text: 'Redirigi i log su stderr (>&2).',
          impact: 'Mantiene pulito il canale dei risultati.'
        });
      }
      if (!content.includes('exit ')) {
        newSuggestions.push({
          id: 'sh-exit',
          type: 'warning',
          text: 'Mancano exit codes espliciti.',
          impact: 'Il Worker non saprà se lo script è riuscito.'
        });
      }
    }

    // Dynamic checks based on payload
    try {
      const parsed = JSON.parse(payload);
      if (lang === 'python' && content.includes('.get(')) {
        const matches = content.match(/\.get\(['"]([^'"]+)['"]\)/g);
        if (matches) {
          matches.forEach(m => {
            const key = m.match(/['"]([^'"]+)['"]/)?.[1];
            if (key && !JSON.stringify(parsed).includes(key)) {
              newSuggestions.push({
                id: `missing-key-${key}`,
                type: 'warning',
                text: `Chiave "${key}" non trovata nel Payload.`,
                impact: 'Il runbook potrebbe ricevere valori null.'
              });
            }
          });
        }
      }
    } catch (e) {}

    if (newSuggestions.length === 0) {
      newSuggestions.push({
        id: 'perfect',
        type: 'success',
        text: 'Script conforme alle best practices.',
        impact: 'Pronto per la produzione.'
      });
    }

    setSuggestions(newSuggestions);
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    addNotification('success', 'Code copied to clipboard');
    setTimeout(() => setCopied(false), 2000);
  };

  const handleTemplateSelect = (tpl: typeof TEMPLATES[0]) => {
    setSelectedTemplate(tpl);
    setCode(tpl.code);
  };

  const handleDownload = () => {
    const element = document.createElement("a");
    const file = new Blob([code], {type: 'text/plain'});
    element.href = URL.createObjectURL(file);
    element.download = selectedTemplate.lang === 'python' ? 'runbook.py' : 'runbook.sh';
    document.body.appendChild(element);
    element.click();
    addNotification('info', 'Runbook file exported');
  };

  const runSimulation = () => {
    if (jsonError) {
      addNotification('error', 'Fix JSON errors before simulation');
      return;
    }
    setIsSimulating(true);
    setSimulationOutput([]);

    setTimeout(() => {
      const logs = [];
      logs.push(`[${new Date().toLocaleTimeString()}] CLOUDO_INIT: Loading environment...`);
      logs.push(`[${new Date().toLocaleTimeString()}] CLOUDO_RUNTIME: Spawning ${selectedTemplate.lang} worker...`);

      try {
        const parsedPayload = JSON.parse(payload);
        logs.push(`[${new Date().toLocaleTimeString()}] PAYLOAD_INJECTED: ${Object.keys(parsedPayload).length} keys detected.`);

        if (selectedTemplate.lang === 'python') {
          logs.push(`STDOUT: --- CLOUDO OPERATIONAL STREAM START ---`);
          const alertRule = parsedPayload.data?.essentials?.alertRule || 'Unknown';
          logs.push(`STDOUT: SIGNAL_DETECTED: ${alertRule}`);
          logs.push(`STDOUT: AUTOMATION_LOGIC_EXECUTED`);
          logs.push(`STDOUT: SUCCESS: Runbook completed successfully`);
        } else {
          logs.push(`STDOUT: --- CLOUDO SYSTEM DIAGNOSTICS ---`);
          logs.push(`STDOUT: NODE_IDENTIFIER: cloudo-worker-sim-01`);
          logs.push(`STDOUT: RESULT: COMPLIANT`);
          logs.push(`STDOUT: ClouDO_EXEC_STATUS: OK`);
        }
        addNotification('success', 'Simulation finished successfully');
      } catch (e) {
        logs.push(`STDERR: Error parsing payload: ${e}`);
        addNotification('error', 'Simulation failed');
      }

      logs.push(`[${new Date().toLocaleTimeString()}] CLOUDO_EXIT: Code 0 (Success)`);
      setSimulationOutput(logs);
      setIsSimulating(false);
    }, 1200);
  };

  return (
    <div className="flex flex-col h-full bg-cloudo-dark text-cloudo-text font-mono selection:bg-cloudo-accent/30">
      {/* Header Bar */}
      <div className="flex items-center justify-between px-8 py-5 border-b border-cloudo-border bg-cloudo-panel sticky top-0 z-20">
        <div className="flex items-center gap-4 shrink-0">
          <div className="p-2 bg-cloudo-accent/5 border border-cloudo-accent/20 shrink-0">
            <HiOutlineCode className="text-cloudo-accent w-5 h-5" />
          </div>
          <div>
            <h1 className="text-sm font-black tracking-[0.2em] text-cloudo-text uppercase">Runbook Studio & Advisor</h1>
            <p className="text-[11px] text-cloudo-muted font-bold uppercase tracking-[0.3em] opacity-70">Interactive Editor // LIVE_GUIDANCE_ACTIVE</p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <button onClick={handleDownload} className="btn btn-ghost border-cloudo-border/40 hover:border-cloudo-accent/40 text-cloudo-muted hover:text-cloudo-text">
            <HiOutlineDownload className="w-5 h-5" />
            Export File
          </button>
          <button onClick={handleCopy} className="btn btn-primary min-w-[160px]">
            {copied ? <HiOutlineCheck className="w-5 h-5" /> : <HiOutlineClipboardCopy className="w-5 h-5" />}
            {copied ? 'Copied to Clipboard' : 'Copy Source Code'}
          </button>
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* Left Sidebar: Templates */}
        <div className="w-72 border-r border-cloudo-border bg-cloudo-accent/5 overflow-y-auto p-6 space-y-6 shrink-0">
          <div className="flex items-center gap-2 mb-3">
            <HiOutlineDocumentText className="text-cloudo-accent w-4 h-4" />
            <h2 className="text-[11px] font-black uppercase tracking-[0.2em] text-cloudo-text">Logic Blueprints</h2>
          </div>
          <div className="space-y-3">
            {TEMPLATES.map((tpl) => (
              <button
                key={tpl.id}
                onClick={() => handleTemplateSelect(tpl)}
                className={`w-full text-left p-4 border transition-all relative group ${
                  selectedTemplate.id === tpl.id
                    ? 'bg-cloudo-accent/5 border-cloudo-accent/40'
                    : 'bg-cloudo-panel border-cloudo-border hover:border-cloudo-muted/70'
                }`}
              >
                <div className="flex items-center gap-3 mb-2">
                  {tpl.lang === 'python' ? <HiOutlineCode className="text-cloudo-accent w-4 h-4" /> : <HiOutlineTerminal className="text-cloudo-accent w-4 h-4" />}
                  <span className="text-[11px] font-black text-cloudo-text uppercase tracking-widest">{tpl.name}</span>
                </div>
                <p className="text-[11px] text-cloudo-muted leading-relaxed opacity-60 group-hover:opacity-400">
                  {tpl.description}
                </p>
                {selectedTemplate.id === tpl.id && (
                  <div className="absolute left-[-1px] top-0 w-[2px] h-full bg-cloudo-accent" />
                )}
              </button>
            ))}
          </div>

          <div className="pt-8 space-y-4">
             <div className="flex items-center gap-2 mb-3">
                <HiOutlineShieldCheck className="text-cloudo-accent w-4 h-4" />
                <h2 className="text-[11px] font-black uppercase tracking-[0.2em] text-cloudo-text">Advisor Tips</h2>
              </div>
              <div className="space-y-3">
                {suggestions.map((s) => (
                  <div key={s.id} className={`p-3 border-l-2 bg-cloudo-accent/10 ${
                    s.type === 'warning' ? 'border-cloudo-warn' :
                    s.type === 'success' ? 'border-green-500' : 'border-cloudo-accent'
                  }`}>
                    <div className="flex items-center gap-2 mb-1">
                      {s.type === 'warning' && <HiOutlineExclamationCircle className="text-cloudo-warn w-3 h-3" />}
                      {s.type === 'success' && <HiOutlineCheck className="text-green-500 w-3 h-3" />}
                      {s.type === 'info' && <HiOutlineInformationCircle className="text-cloudo-accent w-3 h-3" />}
                      <span className="text-[10px] font-bold text-cloudo-text uppercase tracking-tighter">{s.text}</span>
                    </div>
                    <p className="text-[10px] text-cloudo-muted italic opacity-60 leading-tight">
                      {s.impact}
                    </p>
                  </div>
                ))}
              </div>
          </div>
        </div>

        {/* Center: Editor */}
        <div className="flex-1 flex flex-col bg-cloudo-dark overflow-hidden relative">
          <div className="absolute top-0 left-0 w-full h-[1px] bg-cloudo-accent/10 pointer-events-none" />
          <div className="flex items-center justify-between px-6 py-2 bg-cloudo-panel-2 border-b border-cloudo-border shrink-0">
             <div className="flex items-center gap-3">
                <span className="text-[11px] font-bold text-cloudo-accent uppercase tracking-widest flex items-center gap-1.5">
                   <div className="w-2 h-2 bg-cloudo-accent rounded-full animate-pulse" />
                   Editor_Session: active
                </span>
             </div>
             <span className="text-[11px] font-mono text-cloudo-muted opacity-70 uppercase tracking-widest">
                Lang: {selectedTemplate.lang} // UTF-8
             </span>
          </div>
          <div className="flex-1 relative group">
             {/* Row Numbers Simulation */}
             <div className="absolute left-0 top-0 w-12 h-full bg-cloudo-panel-2/50 border-r border-cloudo-border flex flex-col items-center py-6 text-[11px] text-cloudo-muted/80 font-mono select-none pointer-events-none">
                {Array.from({length: 40}).map((_, i) => (
                  <div key={i} className="leading-6">{i + 1}</div>
                ))}
             </div>
             <textarea
               className="w-full h-full bg-transparent text-cloudo-text font-mono text-sm p-6 pl-16 outline-none resize-none leading-6 placeholder:text-cloudo-muted/80 custom-scrollbar"
               spellCheck={false}
               value={code}
               onChange={(e) => setCode(e.target.value)}
             />
          </div>
        </div>

        {/* Right Sidebar: Handbook & Simulator */}
        <div className="w-96 border-l border-cloudo-border bg-cloudo-accent/5 flex flex-col shrink-0">
          {/* Tabs Header */}
          <div className="flex border-b border-cloudo-border bg-cloudo-panel-2/30">
            <button
              onClick={() => setRightTab('simulator')}
              className={`flex-1 py-3 text-[10px] font-black uppercase tracking-[0.2em] transition-all flex items-center justify-center gap-2 ${
                rightTab === 'simulator' ? 'text-cloudo-accent border-b border-cloudo-accent bg-cloudo-accent/5' : 'text-cloudo-muted hover:text-cloudo-text'
              }`}
            >
              <HiOutlinePlay className="w-3 h-3" />
              Simulator
            </button>
            <button
              onClick={() => setRightTab('handbook')}
              className={`flex-1 py-3 text-[10px] font-black uppercase tracking-[0.2em] transition-all flex items-center justify-center gap-2 ${
                rightTab === 'handbook' ? 'text-cloudo-accent border-b border-cloudo-accent bg-cloudo-accent/5' : 'text-cloudo-muted hover:text-cloudo-text'
              }`}
            >
              <HiOutlineBookOpen className="w-3 h-3" />
              Handbook
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-6">
            {rightTab === 'simulator' ? (
              <div className="space-y-8">
                {/* Payload Editor */}
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <HiOutlineDatabase className="text-cloudo-accent w-4 h-4" />
                      <h2 className="text-[11px] font-black uppercase tracking-[0.2em] text-cloudo-text">Input Payload</h2>
                    </div>
                  </div>
                  <div className="relative group">
                    <textarea
                      className={`w-full h-48 bg-cloudo-accent/10 border p-3 text-[11px] font-mono text-cloudo-text outline-none transition-colors custom-scrollbar resize-none ${
                        jsonError ? 'border-cloudo-warn/50 focus:border-cloudo-warn' : 'border-cloudo-border focus:border-cloudo-accent/50'
                      }`}
                      value={payload}
                      onChange={(e) => setPayload(e.target.value)}
                      spellCheck={false}
                    />
                    {jsonError && (
                      <div className="absolute bottom-0 left-0 w-full bg-cloudo-warn/10 text-cloudo-warn text-[9px] p-2 border-t border-cloudo-warn/20 font-bold uppercase tracking-tighter">
                        JSON_ERROR: {jsonError}
                      </div>
                    )}
                    <div className="absolute top-2 right-2 text-[9px] text-cloudo-muted/80 font-bold uppercase tracking-tighter pointer-events-none">
                      Mock_JSON
                    </div>
                  </div>
                </div>

                {/* Execution Button */}
                <button
                  onClick={runSimulation}
                  disabled={isSimulating || !!jsonError}
                  className={`w-full py-4 border flex items-center justify-center gap-3 transition-all active:scale-[0.98] ${
                    isSimulating || !!jsonError
                    ? 'border-cloudo-muted/80 bg-cloudo-panel/50 cursor-not-allowed text-cloudo-muted opacity-50'
                    : 'border-cloudo-accent bg-cloudo-accent/20 hover:bg-cloudo-accent/30 text-cloudo-text'
                  }`}
                >
                  <HiOutlinePlay className={`w-5 h-5 ${isSimulating ? 'animate-spin' : ''}`} />
                  <span className="text-xs font-black uppercase tracking-[0.3em]">
                    {isSimulating ? 'Executing...' : 'Run Simulation'}
                  </span>
                </button>

                {/* Console Output */}
                <div className="space-y-4">
                   <div className="flex items-center gap-2">
                      <HiOutlineClipboardList className="text-cloudo-accent w-4 h-4" />
                      <h2 className="text-[11px] font-black uppercase tracking-[0.2em] text-cloudo-text">Execution Logs</h2>
                    </div>
                    <div className="bg-cloudo-dark border border-cloudo-border p-4 h-64 overflow-y-auto custom-scrollbar font-mono">
                      {simulationOutput.length === 0 && !isSimulating && (
                        <div className="h-full flex flex-col items-center justify-center text-cloudo-muted/80 text-center space-y-2">
                          <HiOutlineTerminal className="w-8 h-8 opacity-40" />
                          <p className="text-[10px] uppercase tracking-widest">Awaiting execution...</p>
                        </div>
                      )}
                      {simulationOutput.map((line, i) => (
                        <div key={i} className={`text-[10px] leading-relaxed mb-1 ${
                          line.startsWith('STDERR') ? 'text-cloudo-warn' :
                          line.startsWith('STDOUT') ? 'text-green-400' : 'text-cloudo-muted'
                        }`}>
                          {line}
                        </div>
                      ))}
                      {isSimulating && (
                        <div className="text-[10px] text-cloudo-accent animate-pulse">
                          _ RUNNING_PROCESS...
                        </div>
                      )}
                    </div>
                </div>
              </div>
            ) : (
              <div className="space-y-6">
                <HandbookSection title="Runtime Context" icon={<HiOutlineCube />}>
                    Il Worker inietta i parametri JSON nella variabile d'ambiente <code className="text-cloudo-accent">CLOUDO_PAYLOAD</code>. In Python: <code className="text-cloudo-accent">os.environ.get('CLOUDO_PAYLOAD')</code>.
                </HandbookSection>

                <HandbookSection title="Output Capture" icon={<HiOutlineTerminal />}>
                    ClouDO cattura sia <code className="text-cloudo-text">stdout</code> che <code className="text-cloudo-text">stderr</code>. Usa <code className="text-cloudo-text">stderr</code> per la telemetria e <code className="text-cloudo-accent">stdout</code> per i dati finali.
                </HandbookSection>

                <HandbookSection title="Common Variables" icon={<HiOutlineVariable />}>
                    <div className="space-y-2 mt-2">
                      <VarItem name="CLOUDO_EXEC_ID" desc="UUID univoco dell'esecuzione." />
                      <VarItem name="CLOUDO_REQUESTED_AT" desc="Timestamp ISO della richiesta." />
                      <VarItem name="CLOUDO_NAME" desc="Nome dell'operazione o schema." />
                      <VarItem name="CLOUDO_RUNBOOK" desc="Path del runbook in esecuzione." />
                      <VarItem name="CLOUDO_WORKER" desc="ID del worker pool di target." />
                      <VarItem name="CLOUDO_ONCALL" desc="Flag per allarmi critici (true/false)." />
                    </div>
                </HandbookSection>

                <HandbookSection title="Deployment" icon={<HiOutlineDocumentText />}>
                    Salva lo script sul Worker Node nel path configurato (es: <code className="text-cloudo-text">/opt/cloudo/runbooks/</code>) e crea uno Schema nel Registry che lo punti.
                </HandbookSection>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Notifications Overlay */}
      <div className="fixed bottom-8 right-8 z-50 flex flex-col gap-3 pointer-events-none">
        {notifications.map((n) => (
          <div
            key={n.id}
            className={`flex items-center gap-3 px-6 py-4 border animate-in slide-in-from-right-full duration-300 pointer-events-auto ${
              n.type === 'success' ? 'bg-green-500/10 border-green-500 text-green-500' :
              n.type === 'error' ? 'bg-cloudo-err/10 border-cloudo-err text-cloudo-err' :
              'bg-cloudo-accent/10 border-cloudo-accent text-cloudo-accent'
            }`}
          >
            {n.type === 'success' && <HiOutlineCheck className="w-5 h-5" />}
            {n.type === 'error' && <HiOutlineExclamationCircle className="w-5 h-5" />}
            {n.type === 'info' && <HiOutlineInformationCircle className="w-5 h-5" />}
            <span className="text-xs font-black uppercase tracking-[0.2em]">{n.message}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function TipItem({ text }: { text: string }) {
  return (
    <li className="flex gap-2 text-[11px] text-cloudo-muted leading-relaxed italic border-l border-cloudo-border/40 pl-3">
      {text}
    </li>
  );
}

function HandbookSection({ title, icon, children }: { title: string, icon: React.ReactNode, children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-cloudo-text/80">
        <span className="text-cloudo-accent">{icon}</span>
        <span className="text-[11px] font-black uppercase tracking-widest">{title}</span>
      </div>
      <div className="text-[11px] text-cloudo-muted leading-relaxed font-bold opacity-80">
        {children}
      </div>
    </div>
  );
}

function VarItem({ name, desc }: { name: string, desc: string }) {
  return (
    <div className="flex flex-col gap-0.5 border-b border-cloudo-border/20 pb-2">
       <code className="text-cloudo-accent text-[11px] font-black">{name}</code>
       <span className="text-[10px] text-cloudo-muted opacity-60 uppercase tracking-tighter">{desc}</span>
    </div>
  );
}
