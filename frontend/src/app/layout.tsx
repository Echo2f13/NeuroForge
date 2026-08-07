import type { Metadata } from "next";
import "./globals.css";
import { SubjectProvider } from "@/contexts/SubjectContext";

export const metadata: Metadata = {
  title: "NeuroForge - Adaptive Learning Engine",
  description: "Transform study material into personalized learning experiences",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="font-sans antialiased">
        <SubjectProvider>
          {children}
        </SubjectProvider>
      </body>
    </html>
  );
}
