"use client";

import * as React from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

function formatNumber(value: number): string {
  try {
    return new Intl.NumberFormat("fa-IR").format(value);
  } catch {
    return String(value);
  }
}

export function InsufficientBalanceDialog({
  open,
  onOpenChange,
  required,
  available,
  onTopup,
}: {
  open: boolean;
  onOpenChange: (b: boolean) => void;
  required: number;
  available: number;
  onTopup: () => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>موجودی کافی نیست</DialogTitle>
          <DialogDescription>
            برای ساخت محصول جدید به {formatNumber(required)} اعتبار نیاز داری.
            موجودی فعلی: {formatNumber(available)}.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter className="gap-2">
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
          >
            انصراف
          </Button>
          <Button
            type="button"
            onClick={() => {
              onOpenChange(false);
              onTopup();
            }}
          >
            افزایش موجودی
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
