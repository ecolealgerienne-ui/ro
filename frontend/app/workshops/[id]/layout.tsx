import { AppSidebar } from '@/components/app-sidebar';

export default async function WorkshopLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <div className="flex h-screen overflow-hidden bg-slate-50">
      <AppSidebar workshopId={id} />
      <div className="flex flex-1 flex-col overflow-hidden">
        <main className="flex-1 overflow-auto">{children}</main>
      </div>
    </div>
  );
}
