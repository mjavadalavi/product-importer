"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home, Wallet, LifeBuoy } from "lucide-react";
import { cn } from "@/lib/utils";

type Tab = {
  href: string;
  label: string;
  Icon: React.ComponentType<{ className?: string }>;
};

const TABS: Tab[] = [
  { href: "/home", label: "خانه", Icon: Home },
  { href: "/payments", label: "پرداخت‌ها", Icon: Wallet },
  { href: "/support", label: "پشتیبانی", Icon: LifeBuoy },
];

export function BottomNav() {
  const pathname = usePathname();

  return (
    <nav
      className="fixed bottom-0 inset-x-0 z-40 border-t bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60"
      aria-label="پیمایش اصلی"
    >
      <ul className="grid grid-cols-3 h-16">
        {TABS.map(({ href, label, Icon }) => {
          const active = pathname === href || pathname?.startsWith(`${href}/`);
          return (
            <li key={href}>
              <Link
                href={href}
                className={cn(
                  "flex flex-col items-center justify-center gap-1 text-xs h-full w-full",
                  active ? "text-primary" : "text-muted-foreground",
                )}
                aria-current={active ? "page" : undefined}
              >
                <Icon className="h-5 w-5" />
                <span>{label}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
