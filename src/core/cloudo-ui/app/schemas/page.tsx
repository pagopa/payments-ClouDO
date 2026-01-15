"use client";

import { useState, useEffect, useMemo } from "react";
import { cloudoFetch } from "@/lib/api";
import {
  HiOutlinePlus,
  HiOutlineSearch,
  HiOutlineChip,
  HiOutlineTerminal,
  HiOutlineUserGroup,
  HiOutlineShieldCheck,
  HiOutlineTrash,
  HiOutlinePlay,
  HiOutlinePencil,
  HiOutlineX,
  HiOutlineClipboardCopy,
  HiOutlineCheck,
  HiOutlineCheckCircle,
  HiOutlineExclamationCircle,
  HiOutlineRefresh,
  HiOutlineCloud,
  HiOutlineChevronLeft,
  HiOutlineChevronRight,
  HiOutlineEye,
} from "react-icons/hi";
import { MdOutlineSchema } from "react-icons/md";
import { SiTerraform } from "react-icons/si";
import { DeleteConfirmationModal } from "../utils/modals";

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
  monitor_condition?: string;
  tags?: string;
}

interface Notification {
  id: string;
  type: "success" | "error";
  message: string;
}

export default function SchemasPage() {
  const [schemas, setSchemas] = useState<Schema[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeFilter, setActiveFilter] = useState<"all" | "terraform" | "ui">(
    "all",
  );
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const [modalMode, setModalMode] = useState<"create" | "edit" | "view" | null>(
    null,
  );
  const [selectedSchema, setSelectedSchema] = useState<Schema | null>(null);
  const [schemaToDelete, setSchemaToDelete] = useState<Schema | null>(null);
  const [confirmRunId, setConfirmRunId] = useState<string | null>(null);
  const [executingId, setExecutingId] = useState<string | null>(null);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [user, setUser] = useState<{ role: string } | null>(null);

  const [runbookContent, setRunbookContent] = useState<string | null>(null);
  const [isRunbookModalOpen, setIsRunbookModalOpen] = useState(false);
  const [fetchingRunbook, setFetchingRunbook] = useState(false);
  const [availableRunbooks, setAvailableRunbooks] = useState<string[]>([]);
  const [availableWorkers, setAvailableWorkers] = useState<string[]>([]);

  // Pagination state
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  const addNotification = (type: "success" | "error", message: string) => {
    const id = Date.now().toString();
    setNotifications((prev) => [...prev, { id, type, message }]);
    setTimeout(() => {
      setNotifications((prev) => prev.filter((n) => n.id !== id));
    }, 4000);
  };

  useEffect(() => {
    fetchSchemas();
    const userData = localStorage.getItem("cloudo_user");
    if (userData) {
      try {
        setUser(JSON.parse(userData));
      } catch (e) {
        console.error("Failed to parse user data", e);
      }
    }
  }, []);

  const fetchSchemas = async () => {
    setLoading(true);
    try {
      const res = await cloudoFetch(`/schemas`);
      const data = await res.json();
      setSchemas(Array.isArray(data) ? data : []);
    } catch {
      setSchemas([]);
    } finally {
      setLoading(false);
    }
  };

  const fetchAvailableRunbooks = async () => {
    try {
      const res = await cloudoFetch(`/runbooks/list`);
      const data = await res.json();
      if (res.ok && Array.isArray(data.runbooks)) {
        setAvailableRunbooks(data.runbooks);
      }
    } catch {
      console.error("Failed to fetch available runbooks");
    }
  };

  const fetchWorkers = async () => {
    try {
      const res = await cloudoFetch(`/workers`);
      const data = await res.json();
      if (res.ok && Array.isArray(data)) {
        // Use PartitionKey as the capability as requested
        const capabilities = Array.from(
          new Set(
            data
              .map((w: { PartitionKey?: string }) => w.PartitionKey)
              .filter((c) => c),
          ),
        ) as string[];
        setAvailableWorkers(capabilities);
      }
    } catch {
      console.error("Failed to fetch available workers");
    }
  };

  const copyToClipboard = (id: string) => {
    navigator.clipboard.writeText(id);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleRun = async (id: string) => {
    setExecutingId(id);
    setConfirmRunId(null);
    try {
      const response = await cloudoFetch(`/Trigger?id=${id}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ source: "schemas-manual" }),
      });

      if (!response.ok) {
        const error = await response.text();
        addNotification("error", `Execution failed: ${error}`);
      } else {
        addNotification("success", `Execution triggered for ${id}`);
      }
    } catch {
      addNotification("error", "Network error // execution failed");
    } finally {
      setExecutingId(null);
    }
  };

  const fetchRunbookContent = async (runbook: string) => {
    setFetchingRunbook(true);
    setRunbookContent(null);
    setIsRunbookModalOpen(true);
    try {
      const res = await cloudoFetch(
        `/runbooks/content?name=${encodeURIComponent(runbook)}`,
      );
      const data = await res.json();
      if (res.ok) {
        setRunbookContent(data.content);
      } else {
        setRunbookContent(`Error: ${data.error || "Failed to fetch content"}`);
      }
    } catch {
      setRunbookContent(
        "Error: Network failure while fetching runbook content",
      );
    } finally {
      setFetchingRunbook(false);
    }
  };

  const isTerraform = (tags?: string) =>
    tags
      ?.split(",")
      .map((t) => t.trim().toLowerCase())
      .includes("terraform");

  const filteredSchemas = useMemo(() => {
    return schemas.filter((s) => {
      const matchesSearch =
        s.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        s.id?.toLowerCase().includes(searchQuery.toLowerCase());

      const isTf = isTerraform(s.tags);
      const matchesFilter =
        activeFilter === "all" ||
        (activeFilter === "terraform" && isTf) ||
        (activeFilter === "ui" && !isTf);

      return matchesSearch && matchesFilter;
    });
  }, [schemas, searchQuery, activeFilter]);

  // Reset pagination when filters change
  useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery, activeFilter]);

  const totalPages = Math.ceil(filteredSchemas.length / pageSize);
  const paginatedSchemas = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return filteredSchemas.slice(start, start + pageSize);
  }, [filteredSchemas, currentPage, pageSize]);

  const stats = useMemo(() => {
    return {
      total: schemas.length,
      approvalRequired: schemas.filter((s) => s.require_approval).length,
      onCall: schemas.filter((s) => s.oncall === "true").length,
    };
  }, [schemas]);

  return (
    <div className="flex flex-col h-full bg-cloudo-dark text-cloudo-text font-mono selection:bg-cloudo-accent/30">
      {/* Notification Toast Container */}
      <div className="fixed top-4 right-4 z-[100] space-y-2 pointer-events-none">
        {notifications.map((notif) => (
          <div
            key={notif.id}
            className={`pointer-events-auto min-w-[320px] p-4 border shadow-2xl animate-in slide-in-from-right-5 duration-300 ${
              notif.type === "success"
                ? "bg-cloudo-panel border-cloudo-ok/30 text-cloudo-ok"
                : "bg-cloudo-panel border-cloudo-err/30 text-cloudo-err"
            }`}
          >
            <div className="flex items-center gap-3">
              {notif.type === "success" ? (
                <HiOutlineCheckCircle className="w-5 h-5 flex-shrink-0" />
              ) : (
                <HiOutlineExclamationCircle className="w-5 h-5 flex-shrink-0" />
              )}
              <p className="text-[10px] font-black uppercase tracking-widest">
                {notif.message}
              </p>
            </div>
          </div>
        ))}
      </div>

      {/* Top Bar - Solid Technical Style */}
      <div className="flex flex-col border-b border-cloudo-border bg-cloudo-panel sticky top-0 z-20">
        <div className="flex items-center justify-between px-8 py-4">
          <div className="flex items-center gap-4 shrink-0">
            <div className="p-2 bg-cloudo-accent/5 border border-cloudo-accent/20 shrink-0">
              <MdOutlineSchema className="text-cloudo-accent w-4 h-4" />
            </div>
            <div>
              <h1 className="text-sm font-black tracking-[0.2em] text-cloudo-text uppercase">
                Runbook Schemas
              </h1>
              <p className="text-[11px] text-cloudo-muted font-bold uppercase tracking-[0.3em] opacity-70">
                System Inventory // ASSET_DB
              </p>
            </div>
          </div>

          <div className="flex items-center gap-6">
            <div className="relative group">
              <HiOutlineSearch className="absolute left-3 top-1/2 -translate-y-1/2 text-cloudo-muted/70 w-4 h-4 group-focus-within:text-cloudo-accent transition-colors" />
              <input
                type="text"
                placeholder="Search schemas..."
                className="input input-icon w-64 h-10 border-cloudo-border/50 focus:border-cloudo-accent/50"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
            {(user?.role === "ADMIN" || user?.role === "OPERATOR") && (
              <button
                onClick={() => {
                  setSelectedSchema(null);
                  setModalMode("create");
                  fetchAvailableRunbooks();
                  fetchWorkers();
                }}
                className="btn btn-primary h-10 px-4 flex items-center gap-2 group"
              >
                <HiOutlinePlus className="w-4 h-4 group-hover:rotate-90 transition-transform" />{" "}
                New Schema
              </button>
            )}
          </div>
        </div>

        {/* Filter Bar */}
        <div className="flex items-center gap-2 px-8 pb-4">
          <button
            onClick={() => setActiveFilter("all")}
            className={`px-3 py-1.5 text-[10px] font-black uppercase tracking-widest border transition-all ${
              activeFilter === "all"
                ? "bg-cloudo-accent border-cloudo-accent text-cloudo-dark"
                : "bg-cloudo-accent/5 border-cloudo-border text-cloudo-muted hover:border-cloudo-accent/30"
            }`}
          >
            All Schemas
          </button>
          <button
            onClick={() => setActiveFilter("terraform")}
            className={`px-3 py-1.5 text-[10px] font-black uppercase tracking-widest border transition-all flex items-center gap-2 ${
              activeFilter === "terraform"
                ? "bg-[#7B42BC] border-[#7B42BC] text-white"
                : "bg-[#7B42BC]/5 border-cloudo-border text-cloudo-muted hover:border-[#7B42BC]/40"
            }`}
          >
            <SiTerraform className="w-3 h-3" /> Terraform Only
          </button>
          <button
            onClick={() => setActiveFilter("ui")}
            className={`px-3 py-1.5 text-[10px] font-black uppercase tracking-widest border transition-all flex items-center gap-2 ${
              activeFilter === "ui"
                ? "bg-cloudo-accent border-cloudo-accent text-cloudo-dark"
                : "bg-cloudo-accent/5 border-cloudo-border text-cloudo-muted hover:border-cloudo-accent/30"
            }`}
          >
            <HiOutlineCloud className="w-3 h-3" /> UI Entry
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-8 space-y-8">
        <div className="max-w-[1400px] mx-auto space-y-8">
          {/* Statistics Grid */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <StatSmall
              title="Total Assets"
              value={stats.total}
              icon={<HiOutlineTerminal />}
              label="SCHEMAS_LOAD"
            />
            <StatSmall
              title="Gate Required"
              value={stats.approvalRequired}
              icon={<HiOutlineShieldCheck />}
              label="AUTH_PENDING"
              color="text-cloudo-warn"
            />
            <StatSmall
              title="Active On-Call"
              value={stats.onCall}
              icon={<HiOutlineUserGroup />}
              label="CRITICAL_PATH"
              color="text-cloudo-accent"
            />
          </div>

          <div className="border border-cloudo-border bg-cloudo-panel overflow-hidden relative group/table">
            {/* Decorative corners for table container */}
            <div className="absolute top-0 left-0 w-8 h-8 border-t border-l border-cloudo-accent/20 pointer-events-none" />
            <div className="absolute bottom-0 right-0 w-8 h-8 border-b border-r border-cloudo-accent/20 pointer-events-none" />

            <table className="w-full text-left border-collapse table-fixed text-sm">
              <thead>
                <tr className="border-b border-cloudo-border bg-cloudo-accent/10">
                  <th className="w-[25%] px-8 py-5 font-black text-cloudo-muted uppercase tracking-[0.3em] text-[11px]">
                    Identification
                  </th>
                  <th className="w-[20%] px-8 py-5 font-black text-cloudo-muted uppercase tracking-[0.3em] text-[11px]">
                    Execution Path
                  </th>
                  <th className="w-[15%] px-8 py-5 font-black text-cloudo-muted uppercase tracking-[0.3em] text-[11px]">
                    Worker Capability
                  </th>
                  <th className="w-[15%] px-8 py-5 font-black text-cloudo-muted uppercase tracking-[0.3em] text-[11px]">
                    Policy
                  </th>
                  <th className="w-[10%] px-8 py-5 font-black text-cloudo-muted uppercase tracking-[0.3em] text-[11px]">
                    Tags
                  </th>
                  <th className="w-[15%] px-8 py-5 font-black text-cloudo-muted uppercase tracking-[0.3em] text-right text-[11px]">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-cloudo-border/30">
                {loading ? (
                  <tr key="loading-row">
                    <td
                      colSpan={6}
                      className="py-32 text-center text-cloudo-muted italic animate-pulse uppercase tracking-[0.5em] font-black opacity-50"
                    >
                      Refreshing Schema Data...
                    </td>
                  </tr>
                ) : filteredSchemas.length === 0 ? (
                  <tr key="empty-row">
                    <td
                      colSpan={6}
                      className="py-32 text-center text-sm font-black uppercase tracking-[0.5em] opacity-40 italic"
                    >
                      NO_ENTRIES_FOUND
                    </td>
                  </tr>
                ) : (
                  paginatedSchemas.map((schema) => (
                    <tr
                      key={schema.RowKey}
                      className="group hover:bg-cloudo-accent/[0.02] transition-colors relative border-l-2 border-l-transparent hover:border-l-cloudo-accent/40"
                    >
                      <td className="px-8 py-6">
                        <div className="flex flex-col gap-2">
                          <span className="text-sm font-black text-cloudo-text tracking-[0.1em] uppercase group-hover:text-cloudo-accent transition-colors">
                            {schema.name}
                          </span>
                          <button
                            onClick={() => copyToClipboard(schema.id)}
                            className="text-xs font-mono text-cloudo-muted/70 flex items-center gap-2 hover:text-cloudo-text w-fit transition-colors group/id"
                          >
                            <span className="opacity-70">ID:</span>
                            <span className="font-bold">{schema.id}</span>
                            {copiedId === schema.id ? (
                              <HiOutlineCheck className="text-cloudo-ok" />
                            ) : (
                              <HiOutlineClipboardCopy className="opacity-0 group-hover/id:opacity-400" />
                            )}
                          </button>
                        </div>
                      </td>
                      <td className="px-8 py-6 text-cloudo-accent/60 font-mono">
                        <div className="flex items-center gap-3">
                          <button
                            onClick={() => fetchRunbookContent(schema.runbook)}
                            className="p-1.5 bg-cloudo-accent/10 border border-cloudo-border group-hover:border-cloudo-accent/20 hover:bg-cloudo-accent/20 transition-all cursor-pointer"
                            title="View Source Code"
                          >
                            <HiOutlineTerminal className="opacity-150 w-4 h-4" />
                          </button>
                          <div className="flex flex-col min-w-0">
                            <span
                              className="truncate text-cloudo-text/80 font-bold transition-all cursor-pointer"
                              onClick={() =>
                                fetchRunbookContent(schema.runbook)
                              }
                            >
                              {schema.runbook}
                            </span>
                            <span className="text-[11px] text-cloudo-muted/70 uppercase tracking-widest mt-1">
                              Asset_Source
                            </span>
                          </div>
                        </div>
                      </td>
                      <td className="px-8 py-6 font-bold text-cloudo-text/70">
                        <div className="flex items-center gap-3">
                          <HiOutlineChip className="opacity-60 w-4 h-4 text-cloudo-accent" />
                          <div className="flex flex-col">
                            <span className="uppercase tracking-[0.1em]">
                              {schema.worker}
                            </span>
                            <span className="text-[10px] text-cloudo-muted/70 uppercase mt-0.5 font-black tracking-widest">
                              CAPABILITY_ID
                            </span>
                          </div>
                        </div>
                      </td>
                      <td className="px-8 py-6">
                        <div className="flex flex-col gap-3">
                          <div className="flex flex-wrap items-center gap-2">
                            {/* Approval Badge */}
                            <div
                              title={
                                schema.require_approval
                                  ? "Approval Gate Active"
                                  : "Auto-Execute"
                              }
                              className={`status-badge ${
                                schema.require_approval
                                  ? "status-pending"
                                  : "status-succeeded"
                              } flex items-center gap-1.5 px-2 py-0.5 text-[11px] border-cloudo-border/40`}
                            >
                              <HiOutlineShieldCheck className="w-3.5 h-3.5" />
                              {schema.require_approval ? "Gate" : "Auto"}
                            </div>

                            {/* OnCall Badge */}
                            {schema.oncall === "true" && (
                              <div className="status-badge status-running flex items-center gap-1.5 px-2 py-0.5 text-[11px] border-cloudo-accent/40">
                                <HiOutlineUserGroup className="w-3.5 h-3.5" />
                                OnCall
                              </div>
                            )}
                          </div>
                        </div>
                      </td>
                      <td className="px-8 py-6">
                        <div className="flex flex-wrap gap-1.5">
                          {schema.tags
                            ?.split(",")
                            .map((t) => t.trim())
                            .filter((t) => t !== "")
                            .map((tag, idx) => {
                              const isTf = tag.toLowerCase() === "terraform";
                              return (
                                <span
                                  key={idx}
                                  className={`px-1.5 py-0.5 border text-[9px] font-black uppercase tracking-tighter flex items-center gap-1 ${
                                    isTf
                                      ? "bg-[#7B42BC]/20 border-[#7B42BC]/40 text-[#7B42BC]"
                                      : "bg-cloudo-accent/5 border-cloudo-accent/20 text-cloudo-accent"
                                  }`}
                                >
                                  {isTf ? (
                                    <SiTerraform
                                      className="w-3.5 h-3.5"
                                      title="Terraform"
                                    />
                                  ) : (
                                    tag
                                  )}
                                </span>
                              );
                            })}
                        </div>
                      </td>
                      <td className="px-8 py-6 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <div className="relative group/run">
                            <button
                              onClick={() => {
                                if (confirmRunId === schema.id) {
                                  handleRun(schema.id);
                                } else {
                                  setConfirmRunId(schema.id);
                                  setTimeout(() => setConfirmRunId(null), 3000);
                                }
                              }}
                              disabled={executingId === schema.id}
                              className={`p-2.5 border transition-all flex items-center gap-2 ${
                                confirmRunId === schema.id
                                  ? "bg-cloudo-accent border-cloudo-accent text-cloudo-dark"
                                  : "bg-cloudo-accent/10 border-cloudo-border text-cloudo-accent hover:border-cloudo-accent/40"
                              } ${
                                executingId === schema.id
                                  ? "opacity-50 cursor-wait"
                                  : ""
                              }`}
                            >
                              {executingId === schema.id ? (
                                <HiOutlineRefresh className="w-4 h-4 animate-spin" />
                              ) : (
                                <HiOutlinePlay
                                  className={`w-4 h-4 ${
                                    confirmRunId === schema.id
                                      ? "scale-110"
                                      : ""
                                  }`}
                                />
                              )}
                              {confirmRunId === schema.id && (
                                <span className="text-[9px] font-black uppercase tracking-tighter">
                                  Confirm?
                                </span>
                              )}
                            </button>
                            {!confirmRunId && !executingId && (
                              <div className="absolute bottom-full right-0 mb-2 px-2 py-1 bg-cloudo-panel border border-cloudo-border text-[9px] text-cloudo-text uppercase tracking-widest opacity-0 group-hover/run:opacity-400 transition-opacity whitespace-nowrap pointer-events-none">
                                Run Procedure
                              </div>
                            )}
                          </div>
                          {(user?.role === "ADMIN" ||
                            user?.role === "OPERATOR") && (
                            <>
                              <button
                                onClick={() => {
                                  setSelectedSchema(schema);
                                  setModalMode(
                                    isTerraform(schema.tags) ? "view" : "edit",
                                  );
                                  fetchAvailableRunbooks();
                                  fetchWorkers();
                                }}
                                className={`p-2.5 bg-cloudo-accent/10 border border-cloudo-border transition-all group/btn hover:border-white/20 text-cloudo-muted hover:text-cloudo-text`}
                                title={
                                  isTerraform(schema.tags)
                                    ? "Managed by Terraform - Read Only"
                                    : "Edit Configuration"
                                }
                              >
                                {isTerraform(schema.tags) ? (
                                  <HiOutlineEye
                                    className={`w-4 h-4 ${
                                      !isTerraform(schema.tags) &&
                                      "group-hover/btn:scale-110"
                                    } transition-transform`}
                                  />
                                ) : (
                                  <HiOutlinePencil
                                    className={`w-4 h-4 ${
                                      !isTerraform(schema.tags) &&
                                      "group-hover/btn:scale-110"
                                    } transition-transform`}
                                  />
                                )}
                              </button>
                              <button
                                onClick={() => setSchemaToDelete(schema)}
                                disabled={isTerraform(schema.tags)}
                                className={`p-2.5 bg-cloudo-accent/10 border border-cloudo-border transition-all group/btn ${
                                  isTerraform(schema.tags)
                                    ? "opacity-20 cursor-not-allowed grayscale"
                                    : "hover:border-cloudo-err/40 text-cloudo-err hover:bg-cloudo-err hover:text-cloudo-text"
                                }`}
                                title={
                                  isTerraform(schema.tags)
                                    ? "Managed by Terraform - Protected"
                                    : "Delete Schema Entry"
                                }
                              >
                                <HiOutlineTrash
                                  className={`w-4 h-4 ${
                                    !isTerraform(schema.tags) &&
                                    "group-hover/btn:scale-110"
                                  } transition-transform`}
                                />
                              </button>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination Controls */}
          {filteredSchemas.length > 0 && (
            <div className="flex flex-col md:flex-row items-center justify-between gap-4 px-2 py-4 border-t border-cloudo-border/30 bg-cloudo-panel/30">
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-1">
                  <span className="text-[10px] font-black text-cloudo-muted uppercase tracking-widest">
                    Show
                  </span>
                  <select
                    value={pageSize}
                    onChange={(e) => {
                      setPageSize(Number(e.target.value));
                      setCurrentPage(1);
                    }}
                    className="bg-cloudo-dark border border-cloudo-border text-cloudo-text text-[10px] font-black px-2 py-1 outline-none focus:border-cloudo-accent/50 transition-colors cursor-pointer"
                  >
                    {[5, 10, 25, 50].map((size) => (
                      <option key={size} value={size}>
                        {size}
                      </option>
                    ))}
                  </select>
                  <span className="text-[10px] font-black text-cloudo-muted uppercase tracking-widest ml-1">
                    Entries
                  </span>
                </div>
                <div className="h-4 w-[1px] bg-cloudo-border/30" />
                <span className="text-[10px] font-black text-cloudo-muted uppercase tracking-widest">
                  Showing{" "}
                  <span className="text-cloudo-text">
                    {(currentPage - 1) * pageSize + 1}
                  </span>{" "}
                  to{" "}
                  <span className="text-cloudo-text">
                    {Math.min(currentPage * pageSize, filteredSchemas.length)}
                  </span>{" "}
                  of{" "}
                  <span className="text-cloudo-text">
                    {filteredSchemas.length}
                  </span>
                </span>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() =>
                    setCurrentPage((prev) => Math.max(1, prev - 1))
                  }
                  disabled={currentPage === 1}
                  className="p-2 border border-cloudo-border text-cloudo-muted hover:text-cloudo-accent hover:border-cloudo-accent/40 disabled:opacity-20 disabled:cursor-not-allowed transition-all"
                >
                  <HiOutlineChevronLeft className="w-4 h-4" />
                </button>

                <div className="flex items-center gap-1 mx-2">
                  <input
                    type="number"
                    min={1}
                    max={totalPages}
                    value={currentPage}
                    onChange={(e) => {
                      const val = parseInt(e.target.value);
                      if (!isNaN(val) && val >= 1 && val <= totalPages) {
                        setCurrentPage(val);
                      }
                    }}
                    className="w-12 bg-cloudo-dark border border-cloudo-border text-cloudo-text text-[10px] font-black px-2 py-1 text-center outline-none focus:border-cloudo-accent/50 transition-colors"
                  />
                  <span className="text-[10px] font-black text-cloudo-muted uppercase tracking-widest mx-1">
                    of
                  </span>
                  <span className="text-[10px] font-black text-cloudo-text uppercase tracking-widest">
                    {totalPages}
                  </span>
                </div>

                <button
                  onClick={() =>
                    setCurrentPage((prev) => Math.min(totalPages, prev + 1))
                  }
                  disabled={currentPage === totalPages}
                  className="p-2 border border-cloudo-border text-cloudo-muted hover:text-cloudo-accent hover:border-cloudo-accent/40 disabled:opacity-20 disabled:cursor-not-allowed transition-all"
                >
                  <HiOutlineChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Form Modal */}
      {modalMode && (
        <div
          className="fixed inset-0 bg-cloudo-dark/90 backdrop-blur-sm flex items-center justify-center z-50 p-4"
          onClick={() => setModalMode(null)}
        >
          <div
            className="bg-cloudo-panel border border-cloudo-border shadow-2xl w-full max-w-xl overflow-hidden animate-in zoom-in-95 duration-200 relative"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Decorative corner */}
            <div className="absolute top-0 right-0 w-12 h-12 overflow-hidden pointer-events-none">
              <div className="absolute top-[-24px] right-[-24px] w-12 h-12 bg-cloudo-border rotate-45" />
            </div>

            <div className="px-8 py-5 border-b border-cloudo-border flex justify-between items-center bg-cloudo-accent/5">
              <div className="flex items-center gap-3">
                <div className="w-1.5 h-1.5 bg-cloudo-accent animate-pulse" />
                <h3 className="text-[10px] font-black uppercase tracking-[0.3em] text-cloudo-text">
                  {modalMode === "create"
                    ? "Register New Schema"
                    : "Update Configuration"}
                </h3>
              </div>
              <button
                onClick={() => setModalMode(null)}
                className="p-1.5 hover:bg-cloudo-err hover:text-cloudo-text border border-cloudo-border text-cloudo-muted transition-colors"
              >
                <HiOutlineX className="w-4 h-4" />
              </button>
            </div>

            <SchemaForm
              initialData={selectedSchema}
              mode={modalMode}
              availableRunbooks={availableRunbooks}
              availableWorkers={availableWorkers}
              onSuccess={(message) => {
                fetchSchemas();
                setModalMode(null);
                addNotification("success", message);
              }}
              onCancel={() => setModalMode(null)}
              onError={(message) => addNotification("error", message)}
            />
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {schemaToDelete && (
        <DeleteConfirmationModal
          schema={schemaToDelete}
          type="schemas"
          onClose={() => setSchemaToDelete(null)}
          onSuccess={(message) => {
            fetchSchemas();
            addNotification("success", message);
          }}
          onError={(message) => addNotification("error", message)}
        />
      )}

      {/* Runbook Source Modal */}
      {isRunbookModalOpen && (
        <div
          className="fixed inset-0 bg-cloudo-dark/95 backdrop-blur-md flex items-center justify-center z-[70] p-4"
          onClick={() => setIsRunbookModalOpen(false)}
        >
          <div
            className="bg-cloudo-panel border border-cloudo-border shadow-2xl w-full max-w-4xl max-h-[80vh] flex flex-col animate-in zoom-in-95 duration-200 relative"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="px-8 py-4 border-b border-cloudo-border flex justify-between items-center bg-cloudo-accent/5">
              <div className="flex items-center gap-3">
                <HiOutlineTerminal className="text-cloudo-accent w-4 h-4" />
                <h3 className="text-[10px] font-black uppercase tracking-[0.3em] text-cloudo-text">
                  Runbook Source Viewer
                </h3>
              </div>
              <button
                onClick={() => setIsRunbookModalOpen(false)}
                className="p-1.5 hover:bg-cloudo-err hover:text-cloudo-text border border-cloudo-border text-cloudo-muted transition-colors"
              >
                <HiOutlineX className="w-4 h-4" />
              </button>
            </div>

            <div className="flex-1 overflow-auto p-6 font-mono text-xs bg-black/40">
              {fetchingRunbook ? (
                <div className="flex items-center justify-center h-64 text-cloudo-accent animate-pulse uppercase tracking-widest font-black">
                  Retrieving Source from Git...
                </div>
              ) : (
                <pre className="text-cloudo-text/90 whitespace-pre-wrap break-all leading-relaxed">
                  {runbookContent || "No content available."}
                </pre>
              )}
            </div>

            <div className="px-8 py-3 border-t border-cloudo-border bg-cloudo-panel flex justify-between items-center">
              <span className="text-[9px] text-cloudo-muted uppercase font-bold tracking-widest opacity-60">
                System Isolated Viewer // READ_ONLY
              </span>
              <button
                onClick={() => {
                  if (runbookContent) {
                    navigator.clipboard.writeText(runbookContent);
                    addNotification("success", "Source copied to clipboard");
                  }
                }}
                disabled={!runbookContent || fetchingRunbook}
                className="flex items-center gap-2 text-[9px] font-black uppercase tracking-widest text-cloudo-accent hover:text-white transition-colors disabled:opacity-30"
              >
                <HiOutlineClipboardCopy className="w-3.5 h-3.5" /> Copy Code
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function StatSmall({
  title,
  value,
  icon,
  label,
  color = "text-cloudo-text",
}: {
  title: string;
  value: number;
  icon: React.ReactNode;
  label: string;
  color?: string;
}) {
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

function LabelWithTooltip({
  children,
  tooltip,
}: {
  children: React.ReactNode;
  tooltip: string;
}) {
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

function SchemaForm({
  initialData,
  mode,
  availableRunbooks,
  availableWorkers,
  onSuccess,
  onCancel,
  onError,
}: {
  initialData?: Schema | null;
  mode: "create" | "edit" | "view";
  availableRunbooks: string[];
  availableWorkers: string[];
  onSuccess: (message: string) => void;
  onCancel: () => void;
  onError: (message: string) => void;
}) {
  const [formData, setFormData] = useState({
    id: initialData?.id || "",
    name: initialData?.name || "",
    description: initialData?.description || "",
    runbook: initialData?.runbook || "",
    run_args: initialData?.run_args || "",
    worker: initialData?.worker || "",
    oncall: initialData?.oncall || "",
    require_approval: initialData?.require_approval || false,
    severity: initialData?.severity || "",
    monitor_condition: initialData?.monitor_condition || "",
    tags: (initialData?.tags || (mode === "create" ? "ui" : ""))
      .split(",")
      .map((t) => t.trim())
      .filter((t) => t !== "ui")
      .join(", "),
  });
  const [submitting, setSubmitting] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Prevent saving if it's a terraform-managed schema (extra safety)
    const originalTags = initialData?.tags || "";
    const isTf = originalTags
      .split(",")
      .map((t) => t.trim().toLowerCase())
      .includes("terraform");
    if (mode === "view" && isTf) {
      onError("Cannot modify Terraform-managed schema");
      return;
    }

    setSubmitting(true);

    // Ensure 'ui' tag is always present
    const userTags = formData.tags
      .split(",")
      .map((t) => t.trim())
      .filter((t) => t !== "");
    const finalTags = ["ui", ...userTags].join(", ");

    try {
      const response = await cloudoFetch(`/schemas`, {
        method: mode === "create" ? "POST" : "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          PartitionKey: "RunbookSchema",
          RowKey: formData.id,
          ...formData,
          tags: finalTags,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        onError(data.error || "Operation failed");
        setSubmitting(false);
        return;
      }

      onSuccess(
        mode === "create" ? "Schema registered" : "Configuration updated",
      );
    } catch (e) {
      onError("Network error // uplink failed");
      console.error(e);
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={submit} className="p-8 grid grid-cols-2 gap-x-8 gap-y-6">
      <div className="space-y-2">
        <LabelWithTooltip tooltip="Unique identifier for the schema. Cannot be changed after creation.">
          SCHEMA_ID // ALERT_ID *
        </LabelWithTooltip>
        <input
          type="text"
          required
          disabled={mode != "create"}
          className="input font-mono text-cloudo-accent w-full"
          value={formData.id}
          onChange={(e) => setFormData({ ...formData, id: e.target.value })}
          placeholder="e.g. aks-pod-restart"
        />
      </div>
      <div className="space-y-2">
        <LabelWithTooltip tooltip="Human-readable name for this schema.">
          Schema Name *
        </LabelWithTooltip>
        <input
          type="text"
          required
          className="input w-full"
          value={formData.name}
          onChange={(e) => setFormData({ ...formData, name: e.target.value })}
          placeholder="e.g. AKS Cleanup Task"
        />
      </div>

      <div className="space-y-2 col-span-2">
        <LabelWithTooltip tooltip="Detailed explanation of what this automation does.">
          Purpose Description
        </LabelWithTooltip>
        <textarea
          className="input min-h-[100px] py-4 resize-none w-full"
          value={formData.description}
          onChange={(e) =>
            setFormData({ ...formData, description: e.target.value })
          }
          placeholder="Objective of this automation..."
        />
      </div>

      <div className="space-y-2">
        <LabelWithTooltip tooltip="Path to the script or executable in the runbook repository.">
          Runbook Path *
        </LabelWithTooltip>
        <div className="relative group">
          <div className="absolute inset-y-0 left-0 w-10 flex items-center justify-center border-r border-cloudo-border/30 group-focus-within:border-cloudo-accent/50 bg-cloudo-accent/5">
            <HiOutlineTerminal className="text-cloudo-muted/70 w-4 h-4" />
          </div>
          <input
            type="text"
            required
            className="input input-icon font-mono w-full"
            value={formData.runbook}
            onChange={(e) =>
              setFormData({ ...formData, runbook: e.target.value })
            }
            placeholder="script.sh"
            list="runbooks-list"
          />
          <datalist id="runbooks-list">
            {availableRunbooks.map((rb) => (
              <option key={rb} value={rb} />
            ))}
          </datalist>
        </div>
      </div>
      <div className="space-y-2">
        <LabelWithTooltip tooltip="The required worker capability to execute this schema.">
          Worker Capability *
        </LabelWithTooltip>
        <div className="relative group">
          <div className="absolute inset-y-0 left-0 w-10 flex items-center justify-center border-r border-cloudo-border/30 group-focus-within:border-cloudo-accent/50 bg-cloudo-accent/5">
            <HiOutlineChip className="text-cloudo-muted/70 w-4 h-4" />
          </div>
          <select
            required
            className="input input-icon font-mono w-full appearance-none cursor-pointer"
            value={formData.worker}
            onChange={(e) =>
              setFormData({ ...formData, worker: e.target.value })
            }
          >
            <option
              value=""
              disabled
              className="bg-cloudo-panel text-cloudo-muted italic"
            >
              Select Worker Capability...
            </option>
            {availableWorkers.map((worker) => (
              <option
                key={worker}
                value={worker}
                className="bg-cloudo-panel text-cloudo-text py-2"
              >
                {worker}
              </option>
            ))}
          </select>
          <div className="absolute inset-y-0 right-0 flex items-center px-4 pointer-events-none text-cloudo-muted">
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M19 9l-7 7-7-7"
              />
            </svg>
          </div>
        </div>
      </div>

      <div className="space-y-2 col-span-2">
        <LabelWithTooltip tooltip="Optional arguments passed to the script during execution.">
          Run Arguments
        </LabelWithTooltip>
        <div className="relative group">
          <div className="absolute inset-y-0 left-0 w-10 flex items-center justify-center border-r border-cloudo-border/30 group-focus-within:border-cloudo-accent/50 bg-cloudo-accent/5">
            <HiOutlineTerminal className="text-cloudo-muted/70 w-4 h-4 opacity-50" />
          </div>
          <input
            type="text"
            className="input input-icon font-mono text-cloudo-warn/80 w-full"
            value={formData.run_args}
            onChange={(e) =>
              setFormData({ ...formData, run_args: e.target.value })
            }
            placeholder="--force --silent"
          />
        </div>
      </div>

      <div className="space-y-2 col-span-2">
        <LabelWithTooltip tooltip="Metadata tags for categorization.">
          Tags (comma separated)
        </LabelWithTooltip>
        <div className="flex gap-2">
          <div className="h-10 px-4 bg-cloudo-accent/10 border border-cloudo-accent/30 text-cloudo-accent text-[11px] font-black flex items-center uppercase tracking-widest">
            ui
          </div>
          <input
            type="text"
            className="input flex-1"
            value={formData.tags}
            onChange={(e) => setFormData({ ...formData, tags: e.target.value })}
            placeholder="e.g. production, urgent"
          />
        </div>
      </div>

      <div
        className="flex items-center justify-between p-4 bg-cloudo-accent/10 border border-cloudo-border group hover:border-cloudo-accent/40 transition-all cursor-pointer"
        onClick={() =>
          setFormData({
            ...formData,
            require_approval: !formData.require_approval,
          })
        }
      >
        <div className="space-y-1">
          <p className="text-[11px] font-black text-cloudo-text uppercase tracking-widest">
            Approval Gate
          </p>
          <p className="text-[10px] text-cloudo-muted uppercase font-bold opacity-70">
            Manual Auth
          </p>
        </div>
        <div
          className={`w-5 h-5 border flex items-center justify-center transition-all ${
            formData.require_approval
              ? "bg-cloudo-accent border-cloudo-accent text-cloudo-dark"
              : "border-cloudo-border"
          }`}
        >
          {formData.require_approval && <HiOutlineCheck className="w-4 h-4" />}
        </div>
      </div>

      <div
        className="flex items-center justify-between p-4 bg-cloudo-accent/10 border border-cloudo-border group hover:border-cloudo-accent/40 transition-all cursor-pointer"
        onClick={() =>
          setFormData({
            ...formData,
            oncall: formData.oncall === "true" ? "false" : "true",
          })
        }
      >
        <div className="space-y-1">
          <p className="text-[11px] font-black text-cloudo-text uppercase tracking-widest">
            On-Call Flow
          </p>
          <p className="text-[10px] text-cloudo-muted uppercase font-bold opacity-70">
            Notify Team
          </p>
        </div>
        <div
          className={`w-5 h-5 border flex items-center justify-center transition-all ${
            formData.oncall === "true"
              ? "bg-cloudo-accent border-cloudo-accent text-cloudo-dark"
              : "border-cloudo-border"
          }`}
        >
          {formData.oncall === "true" && <HiOutlineCheck className="w-4 h-4" />}
        </div>
      </div>

      <div className="flex gap-4 pt-6 border-t border-cloudo-border col-span-2">
        <button
          type="button"
          onClick={onCancel}
          className="btn btn-ghost px-8 h-12"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={submitting}
          className="btn btn-primary flex-1 h-12"
        >
          {submitting ? "Saving..." : "Save Schema"}
        </button>
      </div>
    </form>
  );
}
