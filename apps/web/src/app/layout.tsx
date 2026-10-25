import type { Metadata } from "next";
import { Geist } from "next/font/google";
const geist = Geist({ subsets: ["latin"], display: "swap" });
import { Header } from "@/components/app";
import "./globals.css";
export const metadata: Metadata = {
  title: "Winner Signal — real-world signals for AI",
  description:
    "Connect AI-assisted work to evidence that its outputs function, get used, and create value. Better signals for AI evaluation and training beyond benchmark pass rates.",
};
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={geist.className}>
        <Header />
        <main>{children}</main>
        <footer>
          <span>Winner Signal</span>
          <span>Build. Share. Learn.</span>
        </footer>
      </body>
    </html>
  );
}
