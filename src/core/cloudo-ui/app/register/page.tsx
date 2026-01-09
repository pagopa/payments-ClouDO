"use client";

import { useState, useEffect } from "react";
import { cloudoFetch } from "@/lib/api";
import { useRouter } from "next/navigation";
import {
  HiOutlineLockClosed,
  HiOutlineUser,
  HiOutlineCloud,
  HiOutlineMail,
  HiOutlineSun,
  HiOutlineMoon,
  HiOutlineShieldCheck,
  HiOutlineArrowLeft,
} from "react-icons/hi";
import { motion, AnimatePresence } from "framer-motion";
import Link from "next/link";

export default function RegisterPage() {
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const router = useRouter();

  useEffect(() => {
    const savedTheme = localStorage.getItem("cloudo_theme") as "dark" | "light";
    if (savedTheme) {
      setTheme(savedTheme);
    }
  }, []);

  const toggleTheme = () => {
    const newTheme = theme === "dark" ? "light" : "dark";
    setTheme(newTheme);
    localStorage.setItem("cloudo_theme", newTheme);
    window.dispatchEvent(new Event("theme-change"));
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError("");

    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      setIsLoading(false);
      return;
    }

    try {
      const res = await cloudoFetch(`/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, email, password }),
      });

      const data = await res.json();

      if (res.ok && data.success) {
        router.push("/login?registered=true");
      } else {
        setError(data.error || "Registration failed. Access denied.");
        setIsLoading(false);
      }
    } catch (err) {
      console.error("Registration error:", err);
      setError("Uplink to Auth Gate failed. System isolated.");
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-screen p-4 bg-cloudo-dark font-mono overflow-hidden">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8 }}
        className="w-full max-w-md relative z-10"
      >
        <div className="flex flex-col items-center mb-10">
          <motion.div
            whileHover={{ scale: 1.05 }}
            className="p-5 bg-cloudo-accent/5 border border-cloudo-accent/20 mb-6 relative"
          >
            <div className="absolute -top-1 -left-1 w-2 h-2 border-t border-l border-cloudo-accent" />
            <div className="absolute -top-1 -right-1 w-2 h-2 border-t border-r border-cloudo-accent" />
            <div className="absolute -bottom-1 -left-1 w-2 h-2 border-b border-l border-cloudo-accent" />
            <div className="absolute -bottom-1 -right-1 w-2 h-2 border-b border-r border-cloudo-accent" />
            <HiOutlineCloud className="text-cloudo-accent w-12 h-12 shrink-0" />
          </motion.div>
          <motion.h1
            initial={{ letterSpacing: "0.5em", opacity: 0 }}
            animate={{ letterSpacing: "0.2em", opacity: 1 }}
            transition={{ duration: 1, delay: 0.2 }}
            className="text-4xl font-black tracking-[0.2em] text-cloudo-text uppercase"
          >
            <span className="text-cloudo-accent">Clou</span>DO
          </motion.h1>
        </div>

        <motion.div
          initial={{ x: -20, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          transition={{ duration: 0.5, delay: 0.5 }}
          className="border border-cloudo-border bg-cloudo-panel relative"
        >
          <div className="border-b border-cloudo-border p-6 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 bg-cloudo-accent animate-pulse" />
              <h2 className="text-sm font-black uppercase tracking-[0.3em] text-cloudo-text">
                Identity Provisioning
              </h2>
            </div>
            <div className="flex items-center gap-4">
              <button
                onClick={toggleTheme}
                className="p-1.5 border border-cloudo-border text-cloudo-muted hover:text-cloudo-accent hover:border-cloudo-accent transition-all"
              >
                {theme === "dark" ? (
                  <HiOutlineSun className="w-3.5 h-3.5" />
                ) : (
                  <HiOutlineMoon className="w-3.5 h-3.5" />
                )}
              </button>
            </div>
          </div>

          <form onSubmit={handleRegister} className="p-8 space-y-6">
            <div className="space-y-4">
              <div className="relative group">
                <div className="absolute inset-y-0 left-0 w-12 flex items-center justify-center border-r border-cloudo-border/30 group-focus-within:border-cloudo-accent/50 transition-colors bg-cloudo-accent/5">
                  <HiOutlineUser className="text-cloudo-muted w-5 h-5 shrink-0 group-focus-within:text-cloudo-accent" />
                </div>
                <input
                  type="text"
                  placeholder="USERNAME"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="w-full bg-cloudo-accent/10 border border-cloudo-border/50 rounded-none pl-16 pr-4 py-4 text-sm font-bold tracking-[0.2em] text-cloudo-text outline-none focus:border-cloudo-accent/40 focus:bg-cloudo-accent/5 transition-all placeholder:text-cloudo-muted/80"
                  required
                />
              </div>

              <div className="relative group">
                <div className="absolute inset-y-0 left-0 w-12 flex items-center justify-center border-r border-cloudo-border/30 group-focus-within:border-cloudo-accent/50 transition-colors bg-cloudo-accent/5">
                  <HiOutlineMail className="text-cloudo-muted w-5 h-5 shrink-0 group-focus-within:text-cloudo-accent" />
                </div>
                <input
                  type="email"
                  placeholder="EMAIL ADDRESS"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full bg-cloudo-accent/10 border border-cloudo-border/50 rounded-none pl-16 pr-4 py-4 text-sm font-bold tracking-[0.2em] text-cloudo-text outline-none focus:border-cloudo-accent/40 focus:bg-cloudo-accent/5 transition-all placeholder:text-cloudo-muted/80"
                  required
                />
              </div>

              <div className="relative group">
                <div className="absolute inset-y-0 left-0 w-12 flex items-center justify-center border-r border-cloudo-border/30 group-focus-within:border-cloudo-accent/50 transition-colors bg-cloudo-accent/5">
                  <HiOutlineLockClosed className="text-cloudo-muted w-5 h-5 shrink-0 group-focus-within:text-cloudo-accent" />
                </div>
                <input
                  type="password"
                  placeholder="PASSWORD"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full bg-cloudo-accent/10 border border-cloudo-border/50 rounded-none pl-16 pr-4 py-4 text-sm font-bold tracking-[0.2em] text-cloudo-text outline-none focus:border-cloudo-accent/40 focus:bg-cloudo-accent/5 transition-all placeholder:text-cloudo-muted/80"
                  required
                />
              </div>

              <div className="relative group">
                <div className="absolute inset-y-0 left-0 w-12 flex items-center justify-center border-r border-cloudo-border/30 group-focus-within:border-cloudo-accent/50 transition-colors bg-cloudo-accent/5">
                  <HiOutlineLockClosed className="text-cloudo-muted w-5 h-5 shrink-0 group-focus-within:text-cloudo-accent" />
                </div>
                <input
                  type="password"
                  placeholder="CONFIRM PASSWORD"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="w-full bg-cloudo-accent/10 border border-cloudo-border/50 rounded-none pl-16 pr-4 py-4 text-sm font-bold tracking-[0.2em] text-cloudo-text outline-none focus:border-cloudo-accent/40 focus:bg-cloudo-accent/5 transition-all placeholder:text-cloudo-muted/80"
                  required
                />
              </div>
            </div>

            {error && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                className="bg-cloudo-err/5 border-l-2 border-cloudo-err p-4 text-cloudo-err text-[11px] font-black uppercase tracking-widest leading-relaxed overflow-hidden"
              >
                {error}
              </motion.div>
            )}

            <button
              type="submit"
              disabled={isLoading}
              className={`w-full bg-transparent border border-cloudo-accent text-cloudo-accent hover:bg-cloudo-accent hover:text-cloudo-dark py-4 text-[11px] font-black uppercase tracking-[0.4em] transition-all relative overflow-hidden group ${
                isLoading ? "opacity-50 cursor-not-allowed" : ""
              }`}
            >
              <span className="relative z-10">
                {isLoading ? "Provisioning..." : "Request Access"}
              </span>
              <div className="absolute inset-0 bg-cloudo-accent translate-y-full group-hover:translate-y-0 transition-transform duration-300" />
            </button>

            <div className="flex justify-center mt-4">
              <Link
                href="/login"
                className="flex items-center gap-2 text-[10px] text-cloudo-muted hover:text-cloudo-accent transition-colors uppercase tracking-widest font-bold"
              >
                <HiOutlineArrowLeft className="w-3 h-3" />
                Back to Login
              </Link>
            </div>
          </form>
        </motion.div>
      </motion.div>
    </div>
  );
}
