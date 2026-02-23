import { Analytics } from "@vercel/analytics/next";

export const metadata = {
  title: "Que hacemos — Eventos en Lima",
  description: "Eventos en Lima",
};

export default function RootLayout({ children }) {
  return (
    <html lang="es" className="dark">
      <body>
        {children}
        <Analytics />
      </body>
    </html>
  );
}
