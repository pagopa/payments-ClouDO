'use client';

import { Inter } from "next/font/google";
import "./globals.css";
import { Sidebar } from "./components/Sidebar";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const pathname = usePathname();
  const router = useRouter();
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);

  useEffect(() => {
    const auth = typeof window !== 'undefined' ? localStorage.getItem('cloudo_auth') : null;
    const authed = auth === 'true';

    // Update state only if it changed to avoid redundant renders
    setIsAuthenticated(prev => {
      if (prev !== authed) return authed;
      return prev;
    });

    if (!authed && pathname !== '/login') {
      router.push('/login');
    }
  }, [pathname, router]);

  const isLoginPage = pathname === '/login';

  // Prevent flash of content or sidebar
  if (isAuthenticated === null && !isLoginPage) {
    return (
      <html lang="en">
        <body className={`${inter.variable} antialiased bg-cloudo-dark`} />
      </html>
    );
  }

  return (
    <html lang="en">
      <body className={`${inter.variable} antialiased`}>
        <div className="flex h-screen overflow-hidden">
          {!isLoginPage && isAuthenticated && <Sidebar />}
          <main className="flex-1 overflow-y-auto bg-cloudo-dark">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
