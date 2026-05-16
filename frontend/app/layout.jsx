import { Pixelify_Sans, VT323, Press_Start_2P } from "next/font/google";
import "./globals.css";

// Stardew-style pixel UI: chunky, highly readable, cream-on-wood palette.
const pixelifySans = Pixelify_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-body",
  display: "swap"
});

const pressStart = Press_Start_2P({
  subsets: ["latin"],
  weight: ["400"],
  variable: "--font-display",
  display: "swap"
});

const vt323 = VT323({
  subsets: ["latin"],
  weight: ["400"],
  variable: "--font-mono",
  display: "swap"
});

export const metadata = {
  title: "Sora the Explorer",
  description: "An Imagined Roguelike — language-learning adventure powered by Pioneer, fal, SLNG, Gradium, OpenAI, and Tavily"
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" className={`${pixelifySans.variable} ${pressStart.variable} ${vt323.variable}`} suppressHydrationWarning>
      <body suppressHydrationWarning>{children}</body>
    </html>
  );
}
