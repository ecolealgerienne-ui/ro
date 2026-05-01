import type { Metadata } from 'next';
import './globals.css';
import { QueryProvider } from '@/lib/query-provider';

export const metadata: Metadata = {
  title: 'ro — chef d\'atelier',
  description: 'SaaS d\'ordonnancement IA pour la sous-traitance mécanique de précision',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="font-sans antialiased">
        <QueryProvider>{children}</QueryProvider>
      </body>
    </html>
  );
}
