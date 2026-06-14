import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider } from "@/lib/auth-context";
import { ChatbotWidget } from "@/components/chatbot-widget";

/* Inter — closest open-source substitute for Airbnb Cereal VF */
const inter = Inter({
  variable: "--font-sans",
  subsets: ["latin", "vietnamese"],
  weight: ["400", "500", "600", "700"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Flashcard AI",
  description: "Generate flashcards using RAG and AI — learn smarter with spaced repetition.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className={`${inter.variable} min-h-full font-sans`}>
        <AuthProvider>
          <TooltipProvider>
            {children}
            <Toaster position="top-right" richColors />
            <ChatbotWidget />
          </TooltipProvider>
        </AuthProvider>
      </body>
    </html>
  );
}

