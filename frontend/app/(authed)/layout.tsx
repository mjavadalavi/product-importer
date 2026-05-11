import { BottomNav } from "@/components/bottom-nav";

export default function AuthedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-dvh pb-16 bg-background">
      {children}
      <BottomNav />
    </div>
  );
}
