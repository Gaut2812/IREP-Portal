import type { Metadata } from "next";
import "./globals.css";
import { LanguageProvider } from "@/lib/LanguageContext";
import { AuthProvider } from "@/lib/AuthContext";

export const metadata: Metadata = {
  title: "IREP Training Portal",
  description: "Industry-Ready Engineer Program · B.Tech Semesters 2 to 7",
  manifest: "/manifest.json",
  applicationName: "IREP Parent",
  appleWebApp: { capable: true, title: "IREP Parent", statusBarStyle: "default" },
};

export const viewport = {
  themeColor: "#14284B",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased font-sans">
        <LanguageProvider>
          <AuthProvider>
            {children}
          </AuthProvider>
        </LanguageProvider>
      </body>
    </html>
  );
}
