"use client";
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api } from "./api";

export type User = {
  id: number;
  email: string;
  full_name: string;
  role: "admin" | "school_admin" | "teacher" | "student";
  school_id: number | null;
  school_name?: string | null;
  locale: string;
  student_id?: number | null;
};

type Ctx = { user: User | null; loading: boolean; login: (e: string, p: string) => Promise<User>; logout: () => Promise<void>; refresh: () => Promise<void> };
const AuthContext = createContext<Ctx | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const refresh = useCallback(async () => {
    try {
      setUser(await api<User>("/auth/me"));
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    if (window.location.pathname.startsWith("/login")) setLoading(false);
    else refresh();
  }, [refresh]);
  const login = async (email: string, password: string) => {
    const r = await api<{ user: User }>("/auth/login", { method: "POST", json: { email, password } });
    setUser(r.user);
    return r.user;
  };
  const logout = async () => {
    await api("/auth/logout", { method: "POST" }).catch(() => {});
    setUser(null);
    window.location.href = "/login";
  };
  return <AuthContext.Provider value={{ user, loading, login, logout, refresh }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const c = useContext(AuthContext);
  if (!c) throw new Error("useAuth outside provider");
  return c;
}

export const isStaff = (u: User | null) => !!u && u.role !== "student";
export const isAdmin = (u: User | null) => !!u && (u.role === "admin" || u.role === "school_admin");
