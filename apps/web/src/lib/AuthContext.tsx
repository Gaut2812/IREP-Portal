"use client";

import React, { createContext, useContext, useState, useEffect } from "react";
import { useRouter } from "next/navigation";

export type Role = "student" | "trainer" | "college" | "parent";

export interface UserProfile {
  id: string;
  email: string;
  role: Role;
  name: string;
  avatar: string;
  college_id: string;
}

interface AuthContextType {
  user: UserProfile | null;
  token: string | null;
  login: (token: string, user: UserProfile) => void;
  logout: () => void;
  switchRoleDemo: (role: Role) => void;
}

const demoProfiles: Record<Role, UserProfile> = {
  student: {
    id: "usr_priya_01",
    email: "priya.r@demo.edu",
    role: "student",
    name: "Priya R",
    avatar: "PR",
    college_id: "col_demo_001"
  },
  trainer: {
    id: "usr_arun_01",
    email: "arun.k@demo.edu",
    role: "trainer",
    name: "Arun Kumar",
    avatar: "AK",
    college_id: "col_demo_001"
  },
  college: {
    id: "usr_kavitha_01",
    email: "admin@demo.edu",
    role: "college",
    name: "Dr. Kavitha",
    avatar: "DC",
    college_id: "col_demo_001"
  },
  parent: {
    id: "usr_ramesh_01",
    email: "ramesh.k@example.com",
    role: "parent",
    name: "Mr. Ramesh K",
    avatar: "RK",
    college_id: "col_demo_001"
  }
};

const AuthContext = createContext<AuthContextType>({
  user: null,
  token: null,
  login: () => {},
  logout: () => {},
  switchRoleDemo: () => {},
});

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserProfile | null>(demoProfiles.student);
  const [token, setToken] = useState<string | null>("mock_jwt_token_demo");
  const router = useRouter();

  useEffect(() => {
    const saved = localStorage.getItem("irep_user");
    const savedToken = localStorage.getItem("irep_token");
    if (saved) {
      try {
        setUser(JSON.parse(saved));
        setToken(savedToken || "mock_jwt_token_demo");
      } catch (e) {
        setUser(demoProfiles.student);
      }
    }
  }, []);

  const login = (newToken: string, newUser: UserProfile) => {
    setUser(newUser);
    setToken(newToken);
    localStorage.setItem("irep_user", JSON.stringify(newUser));
    localStorage.setItem("irep_token", newToken);
    
    // Redirect by role
    if (newUser.role === "student") router.push("/student");
    else if (newUser.role === "trainer") router.push("/trainer");
    else if (newUser.role === "college") router.push("/college");
    else if (newUser.role === "parent") router.push("/parent");
  };

  const logout = () => {
    setUser(null);
    setToken(null);
    localStorage.removeItem("irep_user");
    localStorage.removeItem("irep_token");
    router.push("/login");
  };

  const switchRoleDemo = (role: Role) => {
    const profile = demoProfiles[role];
    login("mock_jwt_token_demo", profile);
  };

  return (
    <AuthContext.Provider value={{ user, token, login, logout, switchRoleDemo }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);

