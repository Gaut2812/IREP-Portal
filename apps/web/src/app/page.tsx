"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/AuthContext";

export default function RootPage() {
  const router = useRouter();
  const { user } = useAuth();

  useEffect(() => {
    if (user?.role === "trainer") router.replace("/trainer");
    else if (user?.role === "college") router.replace("/college");
    else if (user?.role === "parent") router.replace("/parent");
    else router.replace("/student");
  }, [user, router]);

  return (
    <div className="h-screen w-screen flex items-center justify-center bg-[#F1F5F9]">
      <div className="text-center space-y-3">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-[#2BB3A0] to-[#2B5CD0] flex items-center justify-center font-bold text-white text-base shadow mx-auto animate-pulse">
          IR
        </div>
        <p className="text-xs text-[#64748B] font-medium">Loading IREP Portal...</p>
      </div>
    </div>
  );
}
