"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { Sparkles } from "lucide-react";
import { DraftCard, ProductCard } from "@/components/product-card";
import { DraftBanner } from "@/components/draft-banner";
import { BulkImageAssigner } from "@/components/bulk-image-assigner";
import { FAB } from "@/components/fab";
import { InsufficientBalanceDialog } from "@/components/insufficient-balance-dialog";
import { TopupDialog } from "@/components/topup-dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusFilterChips, type StatusFilter } from "@/components/status-filter-chips";
import { SelectionBar } from "@/components/selection-bar";
import { api, type Paginated, type ProductListItem } from "@/lib/api";

function ProductSkeletonCard() {
  return (
    <div className="flex gap-3 bg-white px-4 py-3">
      <Skeleton className="h-16 w-16 rounded-md shrink-0" />
      <div className="flex-1 min-w-0 flex flex-col gap-2">
        <Skeleton className="h-4 w-2/3" />
        <Skeleton className="h-3 w-1/3" />
        <div className="flex gap-3 mt-1">
          <Skeleton className="h-3 w-14" />
          <Skeleton className="h-3 w-14" />
        </div>
        <div className="flex justify-between mt-1">
          <Skeleton className="h-4 w-20" />
          <Skeleton className="h-5 w-20 rounded-md" />
        </div>
      </div>
    </div>
  );
}

function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <div className="px-4 pt-4 pb-2 text-xs font-semibold text-neutral-500 uppercase tracking-wide">
      {children}
    </div>
  );
}

const STATUS_HEADINGS: Record<StatusFilter, string> = {
  ALL: "همه محصولات",
  DRAFT: "پیش‌نویس‌ها",
  PROCESSING: "در حال پردازش",
  READY: "نیاز به تکمیل",
  SUBMITTED: "ثبت شده",
  FAILED: "ناموفق",
};

export default function HomePage() {
  const [insufficientOpen, setInsufficientOpen] = React.useState(false);
  const [insufficientInfo, setInsufficientInfo] = React.useState<{
    required: number;
    available: number;
  }>({ required: 0, available: 0 });
  const [topupOpen, setTopupOpen] = React.useState(false);
  const [bulkPickerOpen, setBulkPickerOpen] = React.useState(false);

  // Multi-select state — only applies to DRAFT items
  const [selectedDraftIds, setSelectedDraftIds] = React.useState<Set<string>>(
    new Set(),
  );

  // Status filter
  const [activeFilter, setActiveFilter] = React.useState<StatusFilter>("ALL");

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

  // Derived counts for chips
  const drafts = items.filter((p) => p.status === "DRAFT");
  const processing = items.filter((p) => p.status === "PROCESSING");
  const ready = items.filter((p) => p.status === "READY");
  const submitted = items.filter((p) => p.status === "SUBMITTED");
  const failed = items.filter((p) => p.status === "FAILED");
  const others = items.filter((p) => p.status !== "DRAFT");

  const filterCounts = {
    all: items.length,
    draft: drafts.length,
    processing: processing.length,
    ready: ready.length,
    submitted: submitted.length,
    failed: failed.length,
  };

  const isEmpty = !isLoading && items.length === 0;
  const hasBoth = drafts.length > 0 && others.length > 0;

  const showDraftBanner =
    drafts.length > 0 &&
    (activeFilter === "ALL" || activeFilter === "DRAFT");

  // Items visible under the current filter (for non-ALL views)
  const filteredItems =
    activeFilter === "ALL"
      ? items
      : items.filter((p) => p.status === activeFilter);

  const handleInsufficient = (required: number, available: number) => {
    setInsufficientInfo({ required, available });
    setInsufficientOpen(true);
  };

  const handleToggleSelect = (id: string) => {
    setSelectedDraftIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const handleClearSelection = () => {
    setSelectedDraftIds(new Set());
  };

  // When filter changes away from DRAFT/ALL, clear selection to avoid stale ids
  const handleFilterChange = (value: StatusFilter) => {
    setActiveFilter(value);
    if (value !== "DRAFT" && value !== "ALL") {
      setSelectedDraftIds(new Set());
    }
  };

  const hasSelection = selectedDraftIds.size > 0;

  return (
    <>
      <main
        className={[
          "bg-neutral-50 flex-1",
          hasSelection ? "pb-32" : "pb-16",
        ].join(" ")}
      >
        {isLoading ? (
          <div className="divide-y divide-neutral-100 bg-white">
            <ProductSkeletonCard />
            <ProductSkeletonCard />
            <ProductSkeletonCard />
          </div>
        ) : isEmpty ? (
          <div className="flex flex-col items-center justify-center text-center gap-4 py-16 px-6">
            <div className="h-28 w-28 rounded-full bg-primary/10 flex items-center justify-center">
              <Sparkles className="h-12 w-12 text-primary" />
            </div>
            <h2 className="text-lg font-semibold">هنوز محصولی نساختی</h2>
            <p className="text-sm text-muted-foreground max-w-xs">
              برای ساخت محصول جدید، روی دکمه ی + پایین صفحه بزن.
            </p>
          </div>
        ) : (
          <div className="flex flex-col">
            {/* DraftBanner — only when drafts exist and filter is ALL or DRAFT */}
            {showDraftBanner ? (
              <DraftBanner
                drafts={drafts}
                onOpenBulkPicker={() => setBulkPickerOpen(true)}
                onInsufficient={handleInsufficient}
              />
            ) : null}

            {/* Status filter chip strip */}
            <div className="bg-white border-b border-neutral-100">
              <StatusFilterChips
                counts={filterCounts}
                active={activeFilter}
                onChange={handleFilterChange}
              />
            </div>

            {/* ALL view — two-section layout unchanged */}
            {activeFilter === "ALL" ? (
              <>
                {drafts.length > 0 ? (
                  <>
                    {hasBoth ? (
                      <SectionHeading>پیش‌نویس‌ها</SectionHeading>
                    ) : null}
                    <div className="bg-white">
                      {drafts.map((p) => (
                        <DraftCard
                          key={p.id}
                          product={p}
                          onInsufficient={handleInsufficient}
                          selected={selectedDraftIds.has(p.id)}
                          onToggleSelect={handleToggleSelect}
                        />
                      ))}
                    </div>
                  </>
                ) : null}

                {others.length > 0 ? (
                  <>
                    {hasBoth ? (
                      <SectionHeading>محصولات</SectionHeading>
                    ) : null}
                    <div className="divide-y divide-neutral-100 bg-white">
                      {others.map((p) => (
                        <ProductCard key={p.id} product={p} onInsufficient={handleInsufficient} />
                      ))}
                    </div>
                  </>
                ) : null}
              </>
            ) : filteredItems.length === 0 ? (
              /* Empty filter state */
              <div className="flex flex-col items-center justify-center text-center gap-4 py-16 px-6">
                <p className="text-sm text-muted-foreground">
                  هیچ محصولی با این وضعیت نداری
                </p>
                <button
                  type="button"
                  onClick={() => handleFilterChange("ALL")}
                  className="text-sm font-medium text-primary underline underline-offset-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded"
                >
                  نمایش همه محصولات
                </button>
              </div>
            ) : (
              /* Single-status filtered view */
              <>
                <SectionHeading>
                  {STATUS_HEADINGS[activeFilter]}
                </SectionHeading>
                <div
                  className={[
                    "bg-white",
                    activeFilter !== "DRAFT"
                      ? "divide-y divide-neutral-100"
                      : "",
                  ].join(" ")}
                >
                  {filteredItems.map((p) =>
                    activeFilter === "DRAFT" ? (
                      <DraftCard
                        key={p.id}
                        product={p}
                        onInsufficient={handleInsufficient}
                        selected={selectedDraftIds.has(p.id)}
                        onToggleSelect={handleToggleSelect}
                      />
                    ) : (
                      <ProductCard key={p.id} product={p} onInsufficient={handleInsufficient} />
                    ),
                  )}
                </div>
              </>
            )}
          </div>
        )}
      </main>

      <FAB onInsufficient={handleInsufficient} />

      {/* Multi-select action bar — sits above BottomNav */}
      <SelectionBar
        selectedIds={selectedDraftIds}
        drafts={drafts}
        onClearSelection={handleClearSelection}
        onInsufficient={handleInsufficient}
      />

      <BulkImageAssigner
        open={bulkPickerOpen}
        onOpenChange={setBulkPickerOpen}
        drafts={drafts}
      />

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
