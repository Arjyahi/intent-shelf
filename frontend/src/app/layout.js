import { Cormorant_Garamond, Outfit } from "next/font/google";

import "./globals.css";

const bodyFont = Outfit({
  subsets: ["latin"],
  variable: "--font-body",
  weight: ["300", "400", "500", "600", "700"],
});

const displayFont = Cormorant_Garamond({
  subsets: ["latin"],
  variable: "--font-display",
  weight: ["400", "500", "600", "700"],
});

export const metadata = {
  title: "IntentShelf",
  description:
    "Discover fashion through an image-first feed shaped by what you browse, save, and search.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body className={`${bodyFont.variable} ${displayFont.variable}`}>
        {children}
      </body>
    </html>
  );
}
