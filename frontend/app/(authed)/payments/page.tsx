"use client";

import * as React from "react";
import { useInfiniteQuery } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { TopupDialog } from "@/components/topup-dialog";
import {
  api,
  type Paginated,
  type TransactionOut,
} from "@/lib/api";
import { formatDateFa, signedAmountFa } from "@/lib/format";

type StatusVariant = "default" | "secondary" | "destructive" | "outline";

const STATUS_MAP: Record<
  TransactionOut["status"],
  { label: string; variant: StatusVariant }
> = {
  PENDING: { label: "در انتظار", variant: "outline" },
  COMPLETED: { label: "انجام شده", variant: "secondary" },
  FAILED: { label: "ناموفق", variant: "destructive" },
  REVERSED: { label: "برگشت داده شد", variant: "outline" },
};

function transactionLabel(tx: TransactionOut): string {
  const { general_type, reference_type } = tx;
  if (general_type === "DEPOSIT") {
    switch (reference_type) {
      case "GIFT":
        return "هدیه ثبت‌نام";
      case "REQUEST_AMOUNT":
        return "افزایش موجودی";
      case "REFERRAL":
        return "هدیه دعوت";
      case "PAYMENT":
        return "پرداخت موفق";
      case "SUBSCRIPTION":
        return "تمدید اشتراک";
      default:
        return "تراکنش";
    }
  }
  if (general_type === "WITHDRAW") {
    if (reference_type === "PRODUCT") return "ساخت محصول";
    return "برداشت";
  }
  return "تراکنش";
}

function TransactionRow({ tx }: { tx: TransactionOut }) {
  const status = STATUS_MAP[tx.status];
  const isWithdraw = tx.general_type === "WITHDRAW";
  const amountClass = isWithdraw ? "text-destructive" : "text-emerald-600";
  const subtitle = tx.note?.trim() || formatDateFa(tx.created_at);

  return (
    <Card className="flex items-center justify-between gap-3 p-3">
      <div className="flex items-center gap-3 min-w-0">
        <Badge variant={status.variant} className="shrink-0">
          {status.label}
        </Badge>
        <div className="min-w-0">
          <div className="text-sm font-medium truncate">
            {transactionLabel(tx)}
          </div>
          <div className="text-xs text-muted-foreground truncate">
            {subtitle}
          </div>
        </div>
      </div>
      <div className={`text-sm font-semibold shrink-0 ${amountClass}`}>
        {signedAmountFa(tx.amount, tx.general_type)} تومان
      </div>
    </Card>
  );
}

function TransactionSkeleton() {
  return (
    <Card className="flex items-center justify-between gap-3 p-3">
      <div className="flex items-center gap-3 min-w-0 flex-1">
        <Skeleton className="h-5 w-16 rounded-md" />
        <div className="min-w-0 flex-1 space-y-2">
          <Skeleton className="h-4 w-1/2" />
          <Skeleton className="h-3 w-1/3" />
        </div>
      </div>
      <Skeleton className="h-4 w-20" />
    </Card>
  );
}

export default function PaymentsPage() {
  const [topupOpen, setTopupOpen] = React.useState(false);

  const {
    data,
    isLoading,
    isFetchingNextPage,
    hasNextPage,
    fetchNextPage,
  } = useInfiniteQuery({
    queryKey: ["transactions"],
    initialPageParam: 1,
    queryFn: ({ pageParam }) =>
      api.get<Paginated<TransactionOut>>(
        `/ledger/transactions?page=${pageParam}&page_size=50`,
      ),
    getNextPageParam: (lastPage) =>
      lastPage.has_more ? lastPage.page + 1 : undefined,
  });

  const items = data?.pages.flatMap((p) => p.items) ?? [];
  const isEmpty = !isLoading && items.length === 0;

  return (
    <>
      <header className="sticky top-0 z-30 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 border-b">
        <div className="flex items-center justify-between gap-3 px-4 h-14">
          <h1 className="text-sm font-semibold truncate">
            پرداخت‌ها و موجودی
          </h1>
          <Button
            size="sm"
            onClick={() => setTopupOpen(true)}
            className="shrink-0"
          >
            <Plus className="h-4 w-4 ms-1" />
            افزایش موجودی
          </Button>
        </div>
      </header>

      <main className="px-4 py-4 space-y-3">
        {isLoading ? (
          <>
            <TransactionSkeleton />
            <TransactionSkeleton />
            <TransactionSkeleton />
          </>
        ) : isEmpty ? (
          <div className="flex flex-col items-center justify-center text-center py-16">
            <p className="text-sm text-muted-foreground">
              هنوز تراکنشی نداری
            </p>
          </div>
        ) : (
          <>
            {items.map((tx) => (
              <TransactionRow key={tx.id} tx={tx} />
            ))}
            {hasNextPage ? (
              <div className="pt-2 flex justify-center">
                <Button
                  variant="outline"
                  onClick={() => fetchNextPage()}
                  disabled={isFetchingNextPage}
                >
                  {isFetchingNextPage ? "در حال بارگیری..." : "بارگیری بیشتر"}
                </Button>
              </div>
            ) : null}
          </>
        )}
      </main>

      <TopupDialog open={topupOpen} onOpenChange={setTopupOpen} />
    </>
  );
}
