"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { api, type MeResponse } from "@/lib/api";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { TopupDialog } from "@/components/topup-dialog";

function formatBalance(value: number | undefined | null): string {
  if (value === undefined || value === null || Number.isNaN(value)) return "-";
  try {
    return new Intl.NumberFormat("fa-IR").format(value);
  } catch {
    return String(value);
  }
}

export function HomeHeader() {
  const [topupOpen, setTopupOpen] = React.useState(false);

  const { data: me, isLoading } = useQuery({
    queryKey: ["me"],
    queryFn: () => api.get<MeResponse>("/auth/me"),
  });

  const fallbackLetter =
    me?.name?.trim()?.charAt(0)?.toUpperCase() || "؟";

  return (
    <header className="sticky top-0 z-30 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 border-b">
      <div className="flex items-center justify-between gap-3 px-4 h-14">
        <div className="flex items-center gap-2 min-w-0">
          {isLoading ? (
            <>
              <Skeleton className="h-9 w-9 rounded-full" />
              <Skeleton className="h-4 w-24" />
            </>
          ) : (
            <>
              <Avatar className="h-9 w-9">
                {me?.avatar_url ? (
                  <AvatarImage src={me.avatar_url} alt={me?.name || ""} />
                ) : null}
                <AvatarFallback>{fallbackLetter}</AvatarFallback>
              </Avatar>
              <span className="text-sm font-semibold truncate">
                {me?.name || ""}
              </span>
            </>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {isLoading ? (
            <Skeleton className="h-6 w-24" />
          ) : (
            <Badge variant="secondary">
              موجودی: {formatBalance(me?.balance)}
            </Badge>
          )}
          <Button
            size="icon"
            variant="default"
            onClick={() => setTopupOpen(true)}
            aria-label="افزایش موجودی"
          >
            <Plus className="h-4 w-4" />
          </Button>
        </div>
      </div>
      <TopupDialog open={topupOpen} onOpenChange={setTopupOpen} />
    </header>
  );
}
