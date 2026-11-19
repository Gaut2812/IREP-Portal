"use client";

import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { API_BASE } from "@/lib/api";
import { clearKeycloakSession, keycloakLogoutUrl } from "@/lib/oidc";

export type Role = "student" | "trainer" | "college" | "parent";

export interface UserProfile {
  id: string;
  email: string;
  role: Role;
  name: string;
  avatar: string;
  college_id: string;
  language_pref?: string;
}

interface AuthContextType {
  user: UserProfile | null;
  token: string | null;
  isLoaded: boolean;
  switching: boolean;
  login: (token: string, user: UserProfile) => void;
  logout: () => void;
  switchRoleDemo: (role: Role) => Promise<void>;
}

/** The API uses `college_admin`; the web app uses the short `college`. */
export function toWebRole(apiRole: string): Role {
  if (apiRole === "college_admin" || apiRole === "college") return "college";
  if (apiRole === "trainer" || apiRole === "parent" || apiRole === "student") return apiRole;
  return "student";
}

const demoProfiles: Record<Role, UserProfile> = {
  student: { id: "usr_priya_01", email: "priya.r@demo.edu", role: "student", name: "Priya R", avatar: "PR", college_id: "col_demo_001" },
  trainer: { id: "usr_arun_01", email: "arun.k@demo.edu", role: "trainer", name: "Arun Kumar", avatar: "AK", college_id: "col_demo_001" },
  college: { id: "usr_kavitha_01", email: "admin@demo.edu", role: "college", name: "Dr. Kavitha", avatar: "DC", college_id: "col_demo_001" },
  parent: { id: "usr_ramesh_01", email: "ramesh.k@example.com", role: "parent", name: "Mr. Ramesh K", avatar: "RK", college_id: "col_demo_001" },
};

/** Seeded demo credentials used by the "View as" switcher and the Playwright helper. */
export const DEMO_CREDENTIALS: Record<Role, { identifier: string; password: string; phone?: string }> = {
  student: { identifier: "priya.r@demo.edu", password: "password123" },
  trainer: { identifier: "arun.k@demo.edu", password: "password123" },
  college: { identifier: "admin@demo.edu", password: "password123" },
  parent: { identifier: "ramesh.k@example.com", password: "password123", phone: "9876543210" },
};

const MOCK_TOKENS = new Set(["mock_jwt_token_demo", "mock_token"]);

/** Perform a real demo login against the API and return the JWT + normalised profile. */
export async function demoLogin(role: Role): Promise<{ token: string; user: UserProfile }> {
  const creds = DEMO_CREDENTIALS[role];
  let data: any;
  if (role === "parent") {
    const req = await fetch(`${API_BASE}/auth/parent/otp/request`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ phone: creds.phone }),
    });
    const reqData = await req.json();
    const res = await fetch(`${API_BASE}/auth/parent/otp/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ phone: creds.phone, otp: reqData.demo_otp || "123456" }),
    });
    if (!res.ok) throw new Error("Parent OTP login failed");
    data = await res.json();
  } else {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role, identifier: creds.identifier, password: creds.password }),
    });
    if (!res.ok) throw new Error("Demo login failed");
    data = await res.json();
  }
  const user: UserProfile = { ...data.user, role: toWebRole(data.user.role) };
  return { token: data.access_token, user };
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  token: null,
  isLoaded: false,
  switching: false,
  login: () => {},
  logout: () => {},
  switchRoleDemo: async () => {},
});

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoaded, setIsLoaded] = useState(false);
  const [switching, setSwitching] = useState(false);
  const router = useRouter();

  const persist = useCallback((newToken: string, newUser: UserProfile) => {
    setUser(newUser);
    setToken(newToken);
    localStorage.setItem("irep_user", JSON.stringify(newUser));
    localStorage.setItem("irep_token", newToken);
  }, []);

  useEffect(() => {
    const saved = localStorage.getItem("irep_user");
    const savedToken = localStorage.getItem("irep_token");
    let savedUser: UserProfile | null = null;
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        savedUser = { ...parsed, role: toWebRole(parsed.role) };
        setUser(savedUser);
        setToken(savedToken);
      } catch {
        setUser(null);
      }
    }
    setIsLoaded(true);

    // Stale sessions from the old mock-token era: silently upgrade to a real JWT.
    if (savedUser && (!savedToken || MOCK_TOKENS.has(savedToken))) {
      demoLogin(savedUser.role)
        .then(({ token: t, user: u }) => persist(t, u))
        .catch(() => {
          /* API offline: keep the stored profile; fetchApi falls back to X-Demo-Role */
        });
    }
  }, [persist]);

  const login = (newToken: string, newUser: UserProfile) => {
    const normalised = { ...newUser, role: toWebRole(newUser.role) };
    persist(newToken, normalised);

    if (normalised.role === "student") router.push("/student");
    else if (normalised.role === "trainer") router.push("/trainer");
    else if (normalised.role === "college") router.push("/college");
    else if (normalised.role === "parent") router.push("/parent");
  };

  const logout = () => {
    setUser(null);
    setToken(null);
    localStorage.removeItem("irep_user");
    localStorage.removeItem("irep_token");
    // Keycloak sign-in: end the SSO session too, or the next sign-in is silent
    const sso = keycloakLogoutUrl();
    clearKeycloakSession();
    if (sso) {
      window.location.assign(sso);
      return;
    }
    router.push("/login");
  };

  /** "View as" switcher: performs a real login with the seeded demo account for that role. */
  const switchRoleDemo = async (role: Role) => {
    setSwitching(true);
    try {
      const { token: t, user: u } = await demoLogin(role);
      login(t, u);
    } catch {
      // API unreachable: fall back to the stored demo profile so the UI still navigates.
      login("mock_jwt_token_demo", demoProfiles[role]);
    } finally {
      setSwitching(false);
    }
  };

  return (
    <AuthContext.Provider value={{ user, token, isLoaded, switching, login, logout, switchRoleDemo }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
