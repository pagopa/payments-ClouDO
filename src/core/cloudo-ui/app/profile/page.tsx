"use client";

import { useState, useEffect } from "react";
import { cloudoFetch } from "@/lib/api";
import { useRouter } from "next/navigation";
import {
  HiOutlineUser,
  HiOutlineSave,
  HiOutlineRefresh,
  HiOutlineCheckCircle,
  HiOutlineExclamationCircle,
  HiOutlineShieldCheck,
} from "react-icons/hi";

interface Notification {
  id: string;
  type: "success" | "error";
  message: string;
}

interface User {
  username: string | null;
  email: string | null;
  password: string | null;
  role: string | null;
}

export default function ProfilePage() {
  const router = useRouter();
  const [user, setUser] = useState<User>();
  const [profile, setProfile] = useState({
    username: "",
    email: "",
    password: "",
    confirmPassword: "",
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [notifications, setNotifications] = useState<Notification[]>([]);

  const addNotification = (type: "success" | "error", message: string) => {
    const id = Date.now().toString();
    setNotifications((prev) => [...prev, { id, type, message }]);
    setTimeout(() => {
      setNotifications((prev) => prev.filter((n) => n.id !== id));
    }, 4000);
  };

  useEffect(() => {
    const userData = localStorage.getItem("cloudo_user");
    if (userData) {
      try {
        const parsedUser = JSON.parse(userData);
        setUser(parsedUser);
        fetchProfile();
      } catch {
        router.push("/login");
      }
    } else {
      router.push("/login");
    }
  }, [router]);

  const fetchProfile = async () => {
    setLoading(true);
    try {
      const res = await cloudoFetch(`/auth/profile`);
      if (res.ok) {
        const data = await res.json();
        setProfile((prev) => ({
          ...prev,
          username: data.username,
          email: data.email,
        }));
      }
    } catch (err) {
      console.error("Failed to fetch profile", err);
    } finally {
      setLoading(false);
    }
  };

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    if (profile.password && profile.password !== profile.confirmPassword) {
      addNotification("error", "Passwords do not match");
      return;
    }

    setSaving(true);
    try {
      const res = await cloudoFetch(`/auth/profile`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: profile.email,
          password: profile.password || undefined,
        }),
      });

      if (res.ok) {
        addNotification("success", "Profile updated successfully");
        setProfile((prev) => ({ ...prev, password: "", confirmPassword: "" }));
        // Update local storage email if it changed
        const userData = localStorage.getItem("cloudo_user");
        if (userData) {
          const u = JSON.parse(userData);
          u.email = profile.email;
          localStorage.setItem("cloudo_user", JSON.stringify(u));
        }
      } else {
        const data = await res.json();
        addNotification("error", data.error || "Failed to update profile");
      }
    } catch {
      addNotification("error", "Uplink failed");
    } finally {
      setSaving(false);
    }
  };

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

      {/* Top Bar */}
      <div className="flex items-center justify-between px-8 py-4 border-b border-cloudo-border bg-cloudo-panel sticky top-0 z-20">
        <div className="flex items-center gap-4 shrink-0">
          <div className="p-2 bg-cloudo-accent/5 border border-cloudo-accent/20 shrink-0">
            <HiOutlineUser className="text-cloudo-accent w-5 h-5" />
          </div>
          <div>
            <h1 className="text-sm font-black tracking-[0.2em] text-cloudo-text uppercase">
              Personal Profile
            </h1>
            <p className="text-[11px] text-cloudo-muted font-bold uppercase tracking-[0.3em] opacity-70">
              Identity Management // PROFILE_GATE
            </p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <button
            onClick={fetchProfile}
            className="btn btn-ghost h-10 px-4 flex items-center gap-2"
          >
            <HiOutlineRefresh
              className={`w-4 h-4 ${loading ? "animate-spin" : ""}`}
            />
            Sync
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-8">
        <div className="max-w-4xl mx-auto">
          <div className="bg-cloudo-panel border border-cloudo-border relative overflow-hidden">
            {/* Decorative corner */}
            <div className="absolute top-0 right-0 w-16 h-16 overflow-hidden pointer-events-none">
              <div className="absolute top-[-32px] right-[-32px] w-16 h-16 bg-cloudo-border rotate-45" />
            </div>

            <div className="p-8 border-b border-cloudo-border flex items-center gap-4 bg-cloudo-accent/5">
              <div className="w-16 h-16 bg-cloudo-accent text-cloudo-dark flex items-center justify-center font-black text-2xl uppercase border-2 border-cloudo-accent/20">
                {profile.username?.slice(0, 2) || "??"}
              </div>
              <div>
                <h2 className="text-xl font-black text-cloudo-text uppercase tracking-widest">
                  {profile.username || "OPERATOR"}
                </h2>
                <div className="flex items-center gap-2 mt-1">
                  <span className="px-2 py-0.5 border border-cloudo-accent/30 text-[10px] font-black text-cloudo-accent uppercase tracking-widest bg-cloudo-accent/5">
                    {user?.role || "L-GUEST"}
                  </span>
                  <span className="text-[10px] text-cloudo-muted font-bold uppercase tracking-widest">
                    Authorized Terminal User
                  </span>
                </div>
              </div>
            </div>

            <form onSubmit={handleSaveProfile} className="p-8 space-y-8">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                <div className="space-y-2">
                  <label className="text-[11px] font-black uppercase tracking-widest text-cloudo-muted ml-1 block">
                    Identity (Username)
                  </label>
                  <input
                    type="text"
                    className="input h-11 w-full opacity-50 cursor-not-allowed bg-cloudo-accent/5"
                    value={profile.username}
                    readOnly
                    disabled
                  />
                  <p className="text-[10px] text-cloudo-muted/70 uppercase tracking-tight ml-1">
                    System identifier cannot be modified
                  </p>
                </div>

                <div className="space-y-2">
                  <label className="text-[11px] font-black uppercase tracking-widest text-cloudo-muted ml-1 block">
                    Email Endpoint
                  </label>
                  <input
                    type="email"
                    className="input h-11 w-full"
                    value={profile.email}
                    onChange={(e) =>
                      setProfile({ ...profile, email: e.target.value })
                    }
                    required
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-[11px] font-black uppercase tracking-widest text-cloudo-muted ml-1 block">
                    New Password
                  </label>
                  <input
                    type="password"
                    className="input h-11 w-full"
                    placeholder="Leave empty to keep current"
                    value={profile.password}
                    onChange={(e) =>
                      setProfile({ ...profile, password: e.target.value })
                    }
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-[11px] font-black uppercase tracking-widest text-cloudo-muted ml-1 block">
                    Confirm New Password
                  </label>
                  <input
                    type="password"
                    className="input h-11 w-full"
                    placeholder="Verify security credentials"
                    value={profile.confirmPassword}
                    onChange={(e) =>
                      setProfile({
                        ...profile,
                        confirmPassword: e.target.value,
                      })
                    }
                  />
                </div>
              </div>

              <div className="flex justify-end pt-8 border-t border-cloudo-border">
                <button
                  type="submit"
                  disabled={saving}
                  className="btn btn-primary h-11 px-10 flex items-center gap-2 relative overflow-hidden group"
                >
                  <HiOutlineSave className="w-4 h-4 relative z-10" />
                  <span className="relative z-10">
                    {saving ? "Updating Profile..." : "Commit Profile Changes"}
                  </span>
                  <div className="absolute inset-0 bg-cloudo-accent translate-y-full group-hover:translate-y-0 transition-transform duration-300" />
                </button>
              </div>
            </form>
          </div>

          <div className="mt-8 p-6 bg-cloudo-accent/5 border border-cloudo-accent/20 flex gap-4 items-start">
            <HiOutlineShieldCheck className="text-cloudo-accent w-6 h-6 shrink-0 mt-1" />
            <div className="space-y-2">
              <h3 className="text-[11px] font-black text-cloudo-text uppercase tracking-widest">
                Security Protocol
              </h3>
              <p className="text-[10px] text-cloudo-muted uppercase font-bold leading-relaxed">
                Your profile data is stored in the ClouDO Identity Vault.
                Passwords are encrypted using industry-standard hashing. Changes
                to your email may affect your notification preferences.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
