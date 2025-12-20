'use client';

import { useState, useEffect, useMemo } from 'react';
import {
  HiOutlinePlus, HiOutlineSearch, HiOutlineChip, HiOutlineTerminal,
  HiOutlineUserGroup, HiOutlineShieldCheck, HiOutlineTrash,
  HiOutlinePlay, HiOutlinePencil, HiOutlineX, HiOutlineClipboardCopy, HiOutlineCheck,
  HiOutlineCheckCircle, HiOutlineExclamationCircle
} from "react-icons/hi";
import { MdOutlineSchema } from "react-icons/md";

interface Schema {
  PartitionKey: string;
  RowKey: string;
  id: string;
  name: string;
  description: string;
  runbook: string;
  run_args: string;
  worker: string;
  oncall: string;
  require_approval: boolean;
  severity?: string;
}

interface Notification {
  id: string;
  type: 'success' | 'error';
  message: string;
}

export default function SchemasPage() {
  const [schemas, setSchemas] = useState<Schema[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const [modalMode, setModalMode] = useState<'create' | 'edit' | null>(null);
  const [selectedSchema, setSelectedSchema] = useState<Schema | null>(null);
  const [schemaToDelete, setSchemaToDelete] = useState<Schema | null>(null);
  const [notifications, setNotifications] = useState<Notification[]>([]);

  const addNotification = (type: 'success' | 'error', message: string) => {
    const id = Date.now().toString();
    setNotifications(prev => [...prev, { id, type, message }]);
    setTimeout(() => {
      setNotifications(prev => prev.filter(n => n.id !== id));
    }, 4000);
  };

  useEffect(() => { fetchSchemas(); }, []);

  const fetchSchemas = async () => {
    setLoading(true);
    try {
      const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:7071/api';
      const res = await fetch(`${API_URL}/schemas`);
      const data = await res.json();
      setSchemas(Array.isArray(data) ? data : []);
    } catch (e) { setSchemas([]); } finally { setLoading(false); }
  };

  const copyToClipboard = (id: string) => {
    navigator.clipboard.writeText(id);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const filteredSchemas = useMemo(() => {
    return schemas.filter(s =>
      s.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.id?.toLowerCase().includes(searchQuery.toLowerCase())
    );
  }, [schemas, searchQuery]);

  return (
    <div className="flex flex-col h-full bg-[#0a0c10] text-cloudo-text font-sans selection:bg-cloudo-accent/30">
      {/* Notification Toast Container */}
      <div className="fixed top-4 right-4 z-[100] space-y-2 pointer-events-none">
        {notifications.map((notif) => (
          <div
            key={notif.id}
            className={`pointer-events-auto min-w-[320px] p-4 rounded-lg border shadow-2xl animate-in slide-in-from-right-5 duration-300 ${
              notif.type === 'success'
                ? 'bg-[#0b0e14] border-green-500/30 text-green-400'
                : 'bg-[#0b0e14] border-red-500/30 text-red-400'
            }`}
          >
            <div className="flex items-center gap-3">
              {notif.type === 'success' ? (
                <HiOutlineCheckCircle className="w-5 h-5 flex-shrink-0" />
              ) : (
                <HiOutlineExclamationCircle className="w-5 h-5 flex-shrink-0" />
              )}
              <p className="text-xs font-bold uppercase tracking-wider">{notif.message}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Top Bar - High Density UI */}
      <div className="flex items-center justify-between px-8 py-4 border-b border-cloudo-border/20 bg-[#0d1117]/80 backdrop-blur-xl sticky top-0 z-20">
        <div className="flex items-center gap-4">
          <div className="p-2 bg-cloudo-accent/10 rounded-lg border border-cloudo-accent/20">
            <MdOutlineSchema className="text-cloudo-accent w-5 h-5" />
          </div>
          <div>
            <h1 className="text-sm font-bold tracking-tight text-white uppercase">Runbook Registry</h1>
            <p className="text-[10px] text-cloudo-muted font-bold uppercase tracking-[0.2em] opacity-60">System Inventory</p>
          </div>
        </div>

        <div className="flex items-center gap-6">
          <div className="relative group">
            <HiOutlineSearch className="absolute left-3 top-1/2 -translate-y-1/2 text-cloudo-muted w-3.5 h-3.5 group-focus-within:text-cloudo-accent transition-colors" />
            <input
              type="text"
              placeholder="Search registry..."
              className="bg-black/40 border border-cloudo-border/30 rounded-md pl-9 pr-4 py-1.5 text-xs w-64 focus:border-cloudo-accent/50 focus:ring-1 ring-cloudo-accent/20 outline-none transition-all placeholder:text-cloudo-muted/40"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
          <button
            onClick={() => { setSelectedSchema(null); setModalMode('create'); }}
            className="bg-cloudo-accent hover:bg-cloudo-accent/90 text-white px-4 py-1.5 rounded-md text-[11px] font-black uppercase tracking-widest transition-all flex items-center gap-2 shadow-lg shadow-cloudo-accent/10"
          >
            <HiOutlinePlus className="w-4 h-4" /> New Schema
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-8">
        <div className="max-w-[1400px] mx-auto">
          <div className="border border-cloudo-border/20 rounded-xl bg-[#0d1117]/40 shadow-2xl overflow-hidden">
            <table className="w-full text-left border-collapse table-fixed text-xs">
              <thead>
                <tr className="border-b border-cloudo-border/20 bg-white/[0.02]">
                  <th className="w-[30%] px-8 py-4 text-[10px] font-black text-cloudo-muted uppercase tracking-[0.2em]">Identification</th>
                  <th className="w-[25%] px-8 py-4 text-[10px] font-black text-cloudo-muted uppercase tracking-[0.2em]">Runbook Asset</th>
                  <th className="w-[15%] px-8 py-4 text-[10px] font-black text-cloudo-muted uppercase tracking-[0.2em]">Worker Pool</th>
                  <th className="w-[15%] px-8 py-4 text-[10px] font-black text-cloudo-muted uppercase tracking-[0.2em]">Compliance</th>
                  <th className="w-[15%] px-8 py-4 text-[10px] font-black text-cloudo-muted uppercase tracking-[0.2em] text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-cloudo-border/10">
                {loading ? (
                  <tr><td colSpan={5} className="py-24 text-center text-cloudo-muted italic animate-pulse">Syncing Registry Data...</td></tr>
                ) : filteredSchemas.length === 0 ? (
                  <tr><td colSpan={5} className="py-24 text-center text-[10px] font-black uppercase tracking-widest opacity-20">No Entries</td></tr>
                ) : (
                  filteredSchemas.map((schema) => (
                    <tr key={schema.RowKey} className="group hover:bg-cloudo-accent/[0.02] transition-colors">
                      <td className="px-8 py-5">
                        <div className="flex flex-col gap-1">
                          <span className="text-sm font-bold text-white tracking-tight">{schema.name}</span>
                          <button
                            onClick={() => copyToClipboard(schema.id)}
                            className="text-[10px] font-mono text-cloudo-muted flex items-center gap-2 hover:text-cloudo-accent w-fit transition-colors"
                          >
                            {schema.id}
                            {copiedId === schema.id ? <HiOutlineCheck className="text-cloudo-ok" /> : <HiOutlineClipboardCopy className="opacity-0 group-hover:opacity-100" />}
                          </button>
                        </div>
                      </td>
                      <td className="px-8 py-5 text-cloudo-accent/70 font-mono">
                        <div className="flex items-center gap-2">
                          <HiOutlineTerminal className="opacity-30 w-3.5 h-3.5" />
                          <span className="truncate">{schema.runbook}</span>
                        </div>
                      </td>
                      <td className="px-8 py-5 font-bold text-white/80">
                        <div className="flex items-center gap-2">
                          <HiOutlineChip className="opacity-30 w-3.5 h-3.5" />
                          {schema.worker}
                        </div>
                      </td>
                      <td className="px-8 py-5">
                        <div className="flex items-center gap-4">
                          <div
                            title={schema.require_approval ? "Approval Gate Active" : "Auto-Execute"}
                            className={`w-2 h-2 rounded-full ${schema.require_approval ? 'bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.3)]' : 'bg-cloudo-ok shadow-[0_0_8px_rgba(34,197,94,0.3)]'}`}
                          />
                          {schema.oncall && (
                            <span className="text-[9px] font-black text-blue-400 bg-blue-500/10 px-1.5 py-0.5 rounded border border-blue-500/20 uppercase tracking-tight">
                              {schema.oncall}
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-8 py-5 text-right">
                        <div className="flex items-center justify-end gap-1 opacity-0 group-hover:opacity-100 transition-all">
                          <button onClick={() => { setSelectedSchema(schema); setModalMode('edit'); }} className="p-2 hover:bg-white/5 rounded text-cloudo-muted hover:text-white"><HiOutlinePencil className="w-4 h-4" /></button>
                          <button className="p-2 hover:bg-cloudo-accent/10 rounded text-cloudo-accent"><HiOutlinePlay className="w-4 h-4" /></button>
                          <button onClick={() => setSchemaToDelete(schema)} className="p-2 hover:bg-red-500/10 rounded text-red-400"><HiOutlineTrash className="w-4 h-4" /></button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Form Modal */}
      {modalMode && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-md flex items-center justify-center z-50 p-4" onClick={() => setModalMode(null)}>
          <div className="bg-[#0b0e14] border border-cloudo-border shadow-2xl rounded-xl w-full max-w-xl overflow-hidden animate-in zoom-in-95 duration-200" onClick={e => e.stopPropagation()}>
            <div className="px-8 py-6 border-b border-cloudo-border/30 flex justify-between items-center bg-white/[0.02]">
              <div>
                <h3 className="text-xs font-black uppercase tracking-[0.2em] text-white">
                  {modalMode === 'create' ? 'Register New Schema' : 'Edit Configuration'}
                </h3>
              </div>
              <button onClick={() => setModalMode(null)} className="p-1 hover:bg-white/5 rounded text-cloudo-muted hover:text-white transition-colors">
                <HiOutlineX className="w-5 h-5" />
              </button>
            </div>

            <SchemaForm
              initialData={selectedSchema}
              mode={modalMode}
              onSuccess={(message) => { fetchSchemas(); setModalMode(null); addNotification('success', message); }}
              onCancel={() => setModalMode(null)}
              onError={(message) => addNotification('error', message)}
            />
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {schemaToDelete && (
        <DeleteConfirmationModal
          schema={schemaToDelete}
          onClose={() => setSchemaToDelete(null)}
          onSuccess={(message) => { fetchSchemas(); addNotification('success', message); }}
          onError={(message) => addNotification('error', message)}
        />
      )}
    </div>
  );
}

function SchemaForm({ initialData, mode, onSuccess, onCancel, onError }: {
  initialData?: Schema | null,
  mode: 'create' | 'edit',
  onSuccess: (message: string) => void,
  onCancel: () => void,
  onError: (message: string) => void
}) {
  const [formData, setFormData] = useState({
    id: initialData?.id || '',
    name: initialData?.name || '',
    description: initialData?.description || '',
    runbook: initialData?.runbook || '',
    run_args: initialData?.run_args || '',
    worker: initialData?.worker || '',
    oncall: initialData?.oncall || '',
    require_approval: initialData?.require_approval || false,
  });
  const [submitting, setSubmitting] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:7071/api';
      const response = await fetch(`${API_URL}/schemas`, {
        method: mode === 'create' ? 'POST' : 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ PartitionKey: 'RunbookSchema', RowKey: formData.id, ...formData }),
      });

      const data = await response.json();

      if (!response.ok) {
        onError(data.error || 'Operation failed');
        setSubmitting(false);
        return;
      }

      onSuccess(mode === 'create' ? 'Schema created successfully' : 'Schema updated successfully');
    } catch (e) {
      onError('Network error. Please try again.');
      console.error(e);
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={submit} className="p-8 space-y-6">
      <div className="grid grid-cols-2 gap-6">
        <div className="space-y-2">
          <label className="text-[10px] font-black uppercase tracking-widest text-cloudo-muted ml-1">Registry ID *</label>
          <input
            type="text"
            required
            disabled={mode === 'edit'}
            className="w-full bg-black/40 border border-cloudo-border/50 rounded-md px-4 py-2.5 text-xs font-mono text-cloudo-accent outline-none focus:border-cloudo-accent/60 focus:ring-1 focus:ring-cloudo-accent/20 transition-all disabled:opacity-50"
            value={formData.id}
            onChange={e => setFormData({...formData, id: e.target.value})}
            placeholder="e.g. aks-pod-restart"
          />
        </div>
        <div className="space-y-2">
          <label className="text-[10px] font-black uppercase tracking-widest text-cloudo-muted ml-1">Schema Name *</label>
          <input
            type="text"
            required
            className="w-full bg-black/40 border border-cloudo-border/50 rounded-md px-4 py-2.5 text-xs text-white outline-none focus:border-cloudo-accent/60 focus:ring-1 focus:ring-cloudo-accent/20 transition-all"
            value={formData.name}
            onChange={e => setFormData({...formData, name: e.target.value})}
            placeholder="e.g. AKS Cleanup Task"
          />
        </div>
      </div>

      <div className="space-y-2">
        <label className="text-[10px] font-black uppercase tracking-widest text-cloudo-muted ml-1">Purpose Description</label>
        <textarea
          className="w-full bg-black/40 border border-cloudo-border/50 rounded-md px-4 py-2.5 text-xs text-cloudo-text min-h-[80px] outline-none focus:border-cloudo-accent/60 focus:ring-1 focus:ring-cloudo-accent/20 transition-all resize-none"
          value={formData.description}
          onChange={e => setFormData({...formData, description: e.target.value})}
          placeholder="What is the objective of this automation?"
        />
      </div>

      <div className="grid grid-cols-2 gap-6">
        <div className="space-y-2">
          <label className="text-[10px] font-black uppercase tracking-widest text-cloudo-muted ml-1">Runbook Path *</label>
          <div className="relative">
            <HiOutlineTerminal className="absolute left-3.5 top-1/2 -translate-y-1/2 text-cloudo-muted/40 w-4 h-4" />
            <input
              type="text"
              required
              className="w-full bg-black/40 border border-cloudo-border/50 rounded-md pl-10 pr-4 py-2.5 text-xs font-mono text-white/90 outline-none focus:border-cloudo-accent/60 focus:ring-1 focus:ring-cloudo-accent/20 transition-all"
              value={formData.runbook}
              onChange={e => setFormData({...formData, runbook: e.target.value})}
              placeholder="script.sh"
            />
          </div>
        </div>
        <div className="space-y-2">
          <label className="text-[10px] font-black uppercase tracking-widest text-cloudo-muted ml-1">Worker Pool *</label>
          <div className="relative">
            <HiOutlineChip className="absolute left-3.5 top-1/2 -translate-y-1/2 text-cloudo-muted/40 w-4 h-4" />
            <input
              type="text"
              required
              className="w-full bg-black/40 border border-cloudo-border/50 rounded-md pl-10 pr-4 py-2.5 text-xs font-mono text-white/90 outline-none focus:border-cloudo-accent/60 focus:ring-1 focus:ring-cloudo-accent/20 transition-all"
              value={formData.worker}
              onChange={e => setFormData({...formData, worker: e.target.value})}
              placeholder="pool-01"
            />
          </div>
        </div>
      </div>

      <div className="flex items-center justify-between p-4 bg-white/[0.02] rounded-lg border border-cloudo-border/20 group hover:border-cloudo-accent/30 transition-all cursor-pointer" onClick={() => setFormData({...formData, require_approval: !formData.require_approval})}>
        <div className="space-y-1">
          <p className="text-[11px] font-black text-white uppercase tracking-wider">Manual Approval Gate</p>
          <p className="text-[9px] text-cloudo-muted uppercase font-bold opacity-50">Authorize execution via orchestrator</p>
        </div>
        <input
          type="checkbox"
          checked={formData.require_approval}
          onChange={() => {}}
          className="w-5 h-5 rounded border-cloudo-border/50 bg-black text-cloudo-accent focus:ring-0 focus:ring-offset-0 transition-all pointer-events-none"
        />
      </div>

      <div className="flex items-center justify-between p-4 bg-white/[0.02] rounded-lg border border-cloudo-border/20 group hover:border-cloudo-accent/30 transition-all cursor-pointer" onClick={() => setFormData({...formData, oncall: !formData.oncall})}>
        <div className="space-y-1">
          <p className="text-[11px] font-black text-white uppercase tracking-wider">OnCall process?</p>
          <p className="text-[9px] text-cloudo-muted uppercase font-bold opacity-50">This runbook had oncall lifecycle</p>
        </div>
        <input
          type="checkbox"
          checked={formData.oncall}
          onChange={() => {}}
          className="w-5 h-5 rounded border-cloudo-border/50 bg-black text-cloudo-accent focus:ring-0 focus:ring-offset-0 transition-all pointer-events-none"
        />
      </div>


      <div className="flex gap-4 pt-4 border-t border-cloudo-border/10">
        <button
          type="button"
          onClick={onCancel}
          className="px-6 py-2.5 text-[10px] font-black uppercase tracking-[0.2em] text-cloudo-muted hover:text-white transition-all"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={submitting}
          className="flex-1 bg-cloudo-accent text-white px-6 py-2.5 rounded-md text-[10px] font-black uppercase tracking-[0.2em] hover:bg-cloudo-accent/90 shadow-xl shadow-cloudo-accent/10 disabled:opacity-50 transition-all"
        >
          {submitting ? 'Committing...' : 'Commit Registry Entry'}
        </button>
      </div>
    </form>
  );
}

function DeleteConfirmationModal({ schema, onClose, onSuccess, onError }: {
  schema: Schema,
  onClose: () => void,
  onSuccess: (message: string) => void,
  onError: (message: string) => void
}) {
  const [isDeleting, setIsDeleting] = useState(false);

  const handleDelete = async () => {
    setIsDeleting(true);
    try {
      const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:7071/api';
      const response = await fetch(`${API_URL}/schemas?id=${schema.id}`, { method: 'DELETE' });
      const data = await response.json();

      if (!response.ok) {
        onError(data.error || 'Delete failed');
        setIsDeleting(false);
        return;
      }

      onSuccess(`Schema "${schema.name}" deleted successfully`);
      onClose();
    } catch (e) {
      onError('Network error. Please try again.');
      setIsDeleting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-[60] p-4">
      <div className="bg-[#0b0e14] border border-red-500/30 rounded-xl max-w-sm w-full p-8 text-center space-y-6 shadow-2xl animate-in zoom-in-95">
        <div className="w-12 h-12 bg-red-500/10 rounded-full flex items-center justify-center mx-auto border border-red-500/20">
          <HiOutlineTrash className="w-6 h-6 text-red-500" />
        </div>
        <div className="space-y-2">
          <h3 className="text-xs font-black text-white uppercase tracking-[0.2em]">Delete Registry Entry</h3>
          <p className="text-[10px] text-cloudo-muted uppercase font-bold leading-relaxed opacity-60">
            Resource: <span className="text-white">{schema.name}</span>
          </p>
        </div>

        <div className="flex flex-col gap-2 pt-2">
          <button onClick={handleDelete} disabled={isDeleting} className="bg-red-600 hover:bg-red-700 text-white py-3 rounded-md text-[10px] font-black uppercase tracking-[0.2em] transition-all disabled:opacity-50">
            {isDeleting ? 'Destroying...' : 'Destroy Entry'}
          </button>
          <button onClick={onClose} disabled={isDeleting} className="text-cloudo-muted hover:text-white py-2 text-[10px] font-black uppercase tracking-[0.2em] transition-all disabled:opacity-50">Cancel Action</button>
        </div>
      </div>
    </div>
  );
}
