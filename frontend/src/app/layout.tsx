import type { Metadata } from "next";
import "./globals.css";
import { SubjectProvider } from "@/contexts/SubjectContext";
import { CitationProvider } from "@/contexts/CitationContext";
import { ThemeProvider } from "@/contexts/ThemeContext";

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
    <html lang="en" suppressHydrationWarning>
      <body className="font-sans antialiased bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 transition-colors">
        <ThemeProvider>
          <SubjectProvider>
            <CitationProvider>
              {children}
            </CitationProvider>
          </SubjectProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
