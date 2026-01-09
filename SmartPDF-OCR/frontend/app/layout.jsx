import "./globals.css";
import { Space_Grotesk, Fraunces } from "next/font/google";

const sans = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-sans",
  weight: ["400", "500", "600", "700"]
});

const display = Fraunces({
  subsets: ["latin"],
  variable: "--font-display",
  weight: ["600", "700"]
});

export const metadata = {
  title: "SmartPDF OCR Studio",
  description: "Fast OCR workspace for PDF documents"
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body className={`${sans.variable} ${display.variable} font-sans`}>
        <div className="noise" />
        {children}
      </body>
    </html>
  );
}
