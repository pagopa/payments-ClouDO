"use client";

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
    const auth =
      typeof window !== "undefined"
        ? localStorage.getItem("cloudo_auth")
        : null;
    const expiresAt =
      typeof window !== "undefined"
        ? localStorage.getItem("cloudo_expires_at")
        : null;

    let authed = auth === "true" && !!expiresAt;

    if (authed && expiresAt) {
      const now = new Date();
      const expirationDate = new Date(expiresAt);
      if (now >= expirationDate) {
        // Session expired
        localStorage.removeItem("cloudo_auth");
        localStorage.removeItem("cloudo_user");
        localStorage.removeItem("cloudo_expires_at");
        localStorage.removeItem("cloudo_token");
        authed = false;
      }
    }

    if (isAuthenticated !== authed) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setIsAuthenticated(authed);
    }

    const isPublicPage = pathname === "/login" || pathname === "/register";

    if (!authed && !isPublicPage) {
      router.push("/login");
    }
  }, [pathname, router, isAuthenticated]);

  const isPublicPage = pathname === "/login" || pathname === "/register";

  const [theme, setTheme] = useState<"dark" | "light">("dark");

  useEffect(() => {
    const savedTheme = localStorage.getItem("cloudo_theme") as "dark" | "light";
    if (savedTheme && theme !== savedTheme) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setTheme(savedTheme);
    }
  }, [theme]);

  useEffect(() => {
    const handleStorageChange = () => {
      const savedTheme = localStorage.getItem("cloudo_theme") as
        | "dark"
        | "light";
      if (savedTheme && savedTheme !== theme) {
        setTheme(savedTheme);
      }
    };

    window.addEventListener("storage", handleStorageChange);
    // Also listen for our custom dispatch if it's the same window
    window.addEventListener("theme-change", handleStorageChange);

    return () => {
      window.removeEventListener("storage", handleStorageChange);
      window.removeEventListener("theme-change", handleStorageChange);
    };
  }, [theme]);

  const toggleTheme = () => {
    const newTheme = theme === "dark" ? "light" : "dark";
    setTheme(newTheme);
    localStorage.setItem("cloudo_theme", newTheme);
  };

  // Prevent flash of content or sidebar
  if (isAuthenticated === null && !isPublicPage) {
    return (
      <html lang="en">
        <body className={`${inter.variable} antialiased bg-cloudo-dark`} />
      </html>
    );
  }

  return (
    <html lang="en">
      <body className={`${inter.variable} antialiased ${theme}`}>
        <div className="flex h-screen overflow-hidden">
          {!isPublicPage && isAuthenticated && (
            <Sidebar theme={theme} toggleTheme={toggleTheme} />
          )}
          <main
            className={`flex-1 overflow-y-auto bg-cloudo-dark transition-colors duration-300`}
          >
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
