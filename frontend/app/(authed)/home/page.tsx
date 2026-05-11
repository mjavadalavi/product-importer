"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { Sparkles } from "lucide-react";
import { HomeHeader } from "@/components/home-header";
import { ProductCard } from "@/components/product-card";
import { FAB } from "@/components/fab";
import { InsufficientBalanceDialog } from "@/components/insufficient-balance-dialog";
import { TopupDialog } from "@/components/topup-dialog";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api, type Paginated, type ProductListItem } from "@/lib/api";

function ProductSkeletonCard() {
  return (
    <Card className="flex gap-3 p-3">
      <Skeleton className="w-20 h-20 rounded-md shrink-0" />
      <div className="flex-1 min-w-0 flex flex-col gap-2">
        <Skeleton className="h-4 w-2/3" />
        <Skeleton className="h-3 w-1/3" />
        <Skeleton className="h-3 w-1/4" />
        <Skeleton className="h-7 w-28 mt-1" />
      </div>
    </Card>
  );
}

export default function HomePage() {
  const [insufficientOpen, setInsufficientOpen] = React.useState(false);
  const [insufficientInfo, setInsufficientInfo] = React.useState<{
    required: number;
    available: number;
  }>({ required: 0, available: 0 });
  const [topupOpen, setTopupOpen] = React.useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["products", { page: 1 }],
    queryFn: () =>
      api.get<Paginated<ProductListItem>>("/products?page=1&page_size=50"),
    refetchInterval: (query) => {
      const items = query.state.data?.items;
      const hasProcessing = !!items?.some(
        (item) => item.status === "PROCESSING",
      );
      return hasProcessing ? 3000 : false;
    },
  });

  const items = data?.items ?? [];
  const isEmpty = !isLoading && items.length === 0;

  const handleInsufficient = (required: number, available: number) => {
    setInsufficientInfo({ required, available });
    setInsufficientOpen(true);
  };

  return (
    <>
      <HomeHeader />
      <main className="px-4 py-4 pt-2 space-y-3">
        {isLoading ? (
          <>
            <ProductSkeletonCard />
            <ProductSkeletonCard />
            <ProductSkeletonCard />
          </>
        ) : isEmpty ? (
          <div className="flex flex-col items-center justify-center text-center gap-4 py-16">
            <div className="h-28 w-28 rounded-full bg-primary/10 flex items-center justify-center">
              <Sparkles className="h-12 w-12 text-primary" />
            </div>
            <h2 className="text-lg font-semibold">هنوز محصولی نساختی</h2>
            <p className="text-sm text-muted-foreground max-w-xs">
              برای ساخت محصول جدید، روی دکمه ی + پایین صفحه بزن.
            </p>
          </div>
        ) : (
          items.map((p) => <ProductCard key={p.id} product={p} />)
        )}
      </main>

      <FAB onInsufficient={handleInsufficient} />

      <InsufficientBalanceDialog
        open={insufficientOpen}
        onOpenChange={setInsufficientOpen}
        required={insufficientInfo.required}
        available={insufficientInfo.available}
        onTopup={() => setTopupOpen(true)}
      />

      <TopupDialog open={topupOpen} onOpenChange={setTopupOpen} />
    </>
  );
}
