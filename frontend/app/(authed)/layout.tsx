import { BottomNav } from "@/components/bottom-nav";
import { HomeHeader } from "@/components/home-header";

export default function AuthedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-dvh pb-16 bg-background flex flex-col">
      <HomeHeader />
      <div className="flex-1 flex flex-col bg-neutral-50">{children}</div>
      <BottomNav />
    </div>
  );
}
