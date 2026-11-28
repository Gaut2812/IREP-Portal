"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/AuthContext";

export default function RootPage() {
  const router = useRouter();
  const { user, isLoaded } = useAuth();

  useEffect(() => {
    if (!isLoaded) return;
    if (!user) router.replace("/login");
    else if (user.role === "trainer") router.replace("/trainer");
    else if (user?.role === "college") router.replace("/college");
    else if (user?.role === "parent") router.replace("/parent");
    else router.replace("/student");
  }, [user, isLoaded, router]);

  return (
    <div className="h-screen w-screen flex items-center justify-center bg-line-soft">
      <div className="text-center space-y-3">
        <div className="w-10 h-10 rounded-card bg-gradient-to-tr from-teal to-brand flex items-center justify-center font-semibold text-white text-base shadow-card mx-auto animate-pulse">
          IR
        </div>
        <p className="text-xs text-muted font-medium">Loading IREP Portal...</p>
      </div>
    </div>
  );
}
