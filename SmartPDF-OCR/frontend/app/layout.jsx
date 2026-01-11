import "./globals.css";
// Fonts are now handled in globals.css for static export compatibility

export const metadata = {
  title: "SmartPDF OCR Studio",
  description: "Fast OCR workspace for PDF documents"
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body className="font-sans">
        <div className="noise" />
        {children}
      </body>
    </html>
  );
}
