'use client';

import { useState, useEffect, Suspense } from 'react';
import { cloudoFetch } from '@/lib/api';
import { useRouter, useSearchParams } from 'next/navigation';
import { HiOutlineLockClosed, HiOutlineUser, HiOutlineLightningBolt, HiOutlineCheckCircle, HiOutlineSun, HiOutlineMoon, HiOutlineShieldCheck, HiOutlineDatabase, HiOutlineServer } from 'react-icons/hi';
import { motion, AnimatePresence } from 'framer-motion';

function LoadingOverlay() {
  const [steps, setSteps] = useState([
    { id: 1, text: 'INITIALIZING UPLINK...', status: 'pending' },
    { id: 2, text: 'CONNECTION STATUS...', status: 'pending' },
    { id: 3, text: 'DECRYPTING DATA...', status: 'pending' },
    { id: 4, text: 'AUTHORIZING ACCESS...', status: 'pending' },
  ]);

  useEffect(() => {
    const intervals = steps.map((_, i) => {
      return setTimeout(() => {
        setSteps(prev => prev.map((step, idx) =>
          idx === i ? { ...step, status: 'complete' } : step
        ));
      }, (i + 1) * 600);
    });

    return () => intervals.forEach(clearTimeout);
  }, []);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-cloudo-dark/95 backdrop-blur-sm"
    >
      <div className="w-full max-w-xs space-y-6">
        <div className="flex flex-col items-center mb-8">
          <motion.div
            animate={{
              scale: [1, 1.1, 1],
              rotate: [0, 90, 180, 270, 360],
              borderColor: ['rgba(var(--color-cloudo-accent), 0.2)', 'rgba(var(--color-cloudo-accent), 1)', 'rgba(var(--color-cloudo-accent), 0.2)']
            }}
            transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
            className="w-16 h-16 border-2 border-cloudo-accent flex items-center justify-center mb-4"
          >
            <HiOutlineShieldCheck className="text-cloudo-accent w-8 h-8" />
          </motion.div>
          <div className="h-1 w-full bg-cloudo-accent/10 overflow-hidden relative">
            <motion.div
              initial={{ left: '-100%' }}
              animate={{ left: '100%' }}
              transition={{ duration: 1.5, repeat: Infinity, ease: "easeInOut" }}
              className="absolute top-0 bottom-0 w-1/3 bg-cloudo-accent"
            />
          </div>
        </div>

        <div className="space-y-3 font-mono">
          {steps.map((step) => (
            <div key={step.id} className="flex items-center gap-3">
              <div className={`w-2 h-2 ${step.status === 'complete' ? 'bg-cloudo-accent shadow-[0_0_8px_rgba(var(--color-cloudo-accent),0.8)]' : 'bg-cloudo-border animate-pulse'}`} />
              <span className={`text-[10px] tracking-[0.2em] font-bold ${step.status === 'complete' ? 'text-cloudo-text' : 'text-cloudo-muted'}`}>
                {step.text}
              </span>
              {step.status === 'complete' && (
                <motion.span
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="text-cloudo-accent text-[10px]"
                >
                  [OK]
                </motion.span>
              )}
            </div>
          ))}
        </div>

        <div className="mt-8 pt-4 border-t border-cloudo-border/30">
          <div className="flex justify-between items-center text-[8px] text-cloudo-muted/50 tracking-widest uppercase">
            <span>Kernel: CLOUDO-V2</span>
            <span className="animate-pulse">Active Session</span>
          </div>
        </div>
      </div>
    </motion.div>
  );
}

function LoginForm() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [theme, setTheme] = useState<'dark' | 'light'>('dark');
  const router = useRouter();
  const searchParams = useSearchParams();
  const registered = searchParams.get('registered') === 'true';

  useEffect(() => {
    const auth = localStorage.getItem('cloudo_auth');
    const expiresAt = localStorage.getItem('cloudo_expires_at');

    if (auth === 'true' && expiresAt) {
      const now = new Date();
      const expirationDate = new Date(expiresAt);
      if (now < expirationDate) {
        router.push('/');
      } else {
        localStorage.removeItem('cloudo_auth');
        localStorage.removeItem('cloudo_user');
        localStorage.removeItem('cloudo_expires_at');
      }
    } else if (auth === 'true' && !expiresAt) {
      localStorage.removeItem('cloudo_auth');
      localStorage.removeItem('cloudo_user');
      localStorage.removeItem('cloudo_expires_at');
    }
  }, [router]);

  useEffect(() => {
    const savedTheme = localStorage.getItem('cloudo_theme') as 'dark' | 'light';
    if (savedTheme && theme !== savedTheme) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setTheme(savedTheme);
    }
  }, [theme]);

  const toggleTheme = () => {
    const newTheme = theme === 'dark' ? 'light' : 'dark';
    setTheme(newTheme);
    localStorage.setItem('cloudo_theme', newTheme);
    // Dispatch a custom event to notify the RootLayout (same window)
    window.dispatchEvent(new Event('theme-change'));
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError('');

    try {
      const res = await cloudoFetch(`/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
      });

      const data = await res.json();

      if (res.ok && data.success && data.expires_at) {
        localStorage.setItem('cloudo_auth', 'true');
        localStorage.setItem('cloudo_user', JSON.stringify(data.user));
        localStorage.setItem('cloudo_expires_at', data.expires_at);
        router.push('/');
      } else if (res.ok && data.success && !data.expires_at) {
        setError('Login successful but no expiration provided. Security protocol violated.');
        setIsLoading(false);
      } else {
        setError(data.error || 'Invalid credentials. Access denied.');
        setIsLoading(false);
      }
    } catch (err) {
      console.error('Login error:', err);
      setError('Uplink to Auth Gate failed. System isolated.');
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-screen p-4 bg-cloudo-dark font-mono overflow-hidden">
      <AnimatePresence>
        {isLoading && <LoadingOverlay />}
      </AnimatePresence>

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
            <HiOutlineLightningBolt className="text-cloudo-accent w-12 h-12 shrink-0" />
          </motion.div>
          <motion.h1
            initial={{ letterSpacing: '0.5em', opacity: 0 }}
            animate={{ letterSpacing: '0.2em', opacity: 1 }}
            transition={{ duration: 1, delay: 0.2 }}
            className="text-4xl font-black tracking-[0.2em] text-cloudo-text uppercase"
          >
            <span className="text-cloudo-accent">Clou</span>DO
          </motion.h1>
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: 64 }}
            transition={{ duration: 0.8, delay: 0.5 }}
            className="h-[1px] bg-cloudo-accent/30 my-4"
          />
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 0.8 }}
            transition={{ duration: 1, delay: 0.8 }}
            className="text-cloudo-muted text-[11px] font-bold uppercase tracking-[0.25em] text-center max-w-[350px] leading-loose"
          >
            Centralized runbook automation for manual or event-driven execution
          </motion.p>
        </div>

        <motion.div
          initial={{ x: -20, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          transition={{ duration: 0.5, delay: 1 }}
          className="border border-cloudo-border bg-cloudo-panel relative"
        >
          {/* Decorative corner */}
          <div className="absolute top-0 right-0 w-16 h-16 overflow-hidden pointer-events-none">
            <div className="absolute top-[-32px] right-[-32px] w-16 h-16 bg-cloudo-border rotate-45" />
          </div>

          <div className="border-b border-cloudo-border p-6 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 bg-cloudo-accent animate-pulse" />
              <h2 className="text-sm font-black uppercase tracking-[0.3em] text-cloudo-text">System Access Gate</h2>
            </div>
            <div className="flex items-center gap-4">
              <button
                onClick={toggleTheme}
                className="p-1.5 border border-cloudo-border text-cloudo-muted hover:text-cloudo-accent hover:border-cloudo-accent transition-all"
                title={theme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
              >
                {theme === 'dark' ? <HiOutlineSun className="w-3.5 h-3.5" /> : <HiOutlineMoon className="w-3.5 h-3.5" />}
              </button>
              <span className="text-[10px] font-mono text-cloudo-muted/70">GATE-AUTH</span>
            </div>
          </div>

          <form onSubmit={handleLogin} className="p-8 space-y-8">
            {registered && (
              <motion.div
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                className="bg-cloudo-ok/5 border-l-2 border-cloudo-ok p-4 text-cloudo-ok text-[11px] font-black uppercase tracking-widest leading-relaxed"
              >
                <div className="flex items-center gap-2 mb-1">
                  <HiOutlineCheckCircle className="w-4 h-4" />
                  <span>Registration Success</span>
                </div>
                Identity provisioned. Establish connection with credentials.
              </motion.div>
            )}
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
            </div>

            {error && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                className="bg-cloudo-err/5 border-l-2 border-cloudo-err p-4 text-cloudo-err text-[11px] font-black uppercase tracking-widest leading-relaxed overflow-hidden"
              >
                <div className="flex items-center gap-2 mb-1">
                  <div className="w-1.5 h-1.5 bg-cloudo-err" />
                  <span>Access Denied</span>
                </div>
                {error}
              </motion.div>
            )}

            <button
              type="submit"
              disabled={isLoading}
              className={`w-full bg-transparent border border-cloudo-accent text-cloudo-accent hover:bg-cloudo-accent hover:text-cloudo-dark py-4 text-[11px] font-black uppercase tracking-[0.4em] transition-all relative overflow-hidden group ${
                isLoading ? 'opacity-50 cursor-not-allowed' : ''
              }`}
            >
              <span className="relative z-10">{isLoading ? 'Authenticating...' : 'Establish Connection'}</span>
              <div className="absolute inset-0 bg-cloudo-accent translate-y-full group-hover:translate-y-0 transition-transform duration-300" />
              {isLoading && (
                <motion.div
                  initial={{ left: '-100%' }}
                  animate={{ left: '100%' }}
                  transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                  className="absolute top-0 bottom-0 w-1/4 bg-cloudo-text/20 skew-x-12 z-20"
                />
              )}
            </button>
          </form>

          <div className="border-t border-cloudo-border p-4 bg-cloudo-accent/5 flex justify-center">
            <p className="text-[10px] text-cloudo-muted font-bold uppercase tracking-[0.2em] opacity-70">
              Terminal Node: CLOUDO-AUTH-01 // P-SECURE
            </p>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 0.6 }}
          transition={{ duration: 0.5, delay: 1.2 }}
          className="mt-8 flex justify-between items-center px-2"
        >
            <div className="h-[1px] flex-1 bg-cloudo-border" />
            <span className="mx-4 text-[10px] font-black uppercase tracking-widest text-cloudo-muted">Authorized Access Only</span>
            <div className="h-[1px] flex-1 bg-cloudo-border" />
        </motion.div>
      </motion.div>

      {/* Background decoration */}
      <div className="fixed inset-0 pointer-events-none opacity-5">
        <div className="absolute top-0 left-0 w-full h-full bg-[radial-gradient(circle_at_center,var(--color-cloudo-accent)_0%,transparent_70%)] opacity-20" />
        <div className="grid grid-cols-12 h-full w-full">
          {Array.from({ length: 12 }).map((_, i) => (
            <div key={i} className="border-r border-cloudo-accent/20 h-full" />
          ))}
        </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={
      <div className="flex items-center justify-center min-h-screen bg-cloudo-dark font-mono">
        <div className="text-cloudo-accent animate-pulse uppercase tracking-[0.3em] text-sm">
          Initializing Security Protocol...
        </div>
      </div>
    }>
      <LoginForm />
    </Suspense>
  );
}
