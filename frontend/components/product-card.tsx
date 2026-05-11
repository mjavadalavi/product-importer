"use client";

import * as React from "react";
import Link from "next/link";
import { ChevronLeft } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { formatPriceToman } from "@/lib/format";
import type { ProductListItem } from "@/lib/api";

type StatusVariant = "default" | "secondary" | "destructive" | "outline";

function statusInfo(status: string): { variant: StatusVariant; label: string } {
  switch (status) {
    case "DRAFT":
    case "PROCESSING":
      return { variant: "secondary", label: "در حال پردازش" };
    case "READY":
      return { variant: "outline", label: "نیاز به تکمیل" };
    case "SUBMITTED":
      return { variant: "default", label: "ثبت شد" };
    case "FAILED":
      return { variant: "destructive", label: "ناموفق" };
    default:
      return { variant: "secondary", label: status };
  }
}

export function ProductCard({ product }: { product: ProductListItem }) {
  const status = statusInfo(product.status);
  const title = product.name || "بدون نام";
  const subtitle = product.category_title || "...";

  return (
    <Card className="flex gap-3 p-3">
      <div className="shrink-0">
        {product.primary_image_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={product.primary_image_url}
            alt={title}
            className="w-20 h-20 object-cover rounded-md"
          />
        ) : (
          <Skeleton className="w-20 h-20 rounded-md" />
        )}
      </div>

      <div className="flex-1 min-w-0 flex flex-col gap-1">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <div className="font-semibold truncate">{title}</div>
            <div className="text-sm text-muted-foreground truncate">
              {subtitle}
            </div>
          </div>
          <Badge variant={status.variant} className="shrink-0">
            {status.label}
          </Badge>
        </div>

        <div className="text-sm">
          {formatPriceToman(product.price_final)}
        </div>

        <div className="mt-1 flex justify-start">
          <Button variant="ghost" size="sm" asChild>
            <Link href={`/products/${product.id}`}>
              <span>مشاهده جزئیات</span>
              <ChevronLeft className="h-4 w-4" />
            </Link>
          </Button>
        </div>
      </div>
    </Card>
  );
}
