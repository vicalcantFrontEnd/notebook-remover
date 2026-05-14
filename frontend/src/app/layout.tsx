import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ClearMark — Removedor de Marca de Agua con IA",
  description: "Elimina marcas de agua de videos, imágenes, PDFs y presentaciones con inteligencia artificial",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es" className="dark">
      <body className="min-h-screen bg-ctp-crust text-ctp-text antialiased" suppressHydrationWarning>
        <div className="fixed inset-0 -z-10 overflow-hidden pointer-events-none" aria-hidden="true">
          <div style={{ position:"absolute", top:"-180px", left:"-180px", width:"780px", height:"780px", borderRadius:"50%", background:"radial-gradient(circle, rgba(203,166,247,0.13) 0%, transparent 70%)", filter:"blur(50px)" }} />
          <div style={{ position:"absolute", bottom:"-160px", right:"-80px", width:"650px", height:"650px", borderRadius:"50%", background:"radial-gradient(circle, rgba(137,180,250,0.11) 0%, transparent 70%)", filter:"blur(50px)" }} />
          <div style={{ position:"absolute", top:"45%", left:"55%", transform:"translate(-50%,-50%)", width:"1000px", height:"500px", borderRadius:"50%", background:"radial-gradient(circle, rgba(180,190,254,0.05) 0%, transparent 70%)", filter:"blur(70px)" }} />
        </div>
        {children}
      </body>
    </html>
  );
}
