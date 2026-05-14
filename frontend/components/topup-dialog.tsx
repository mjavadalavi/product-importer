"use client";

import * as React from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { api } from "@/lib/api";
import { digitsOnly, formatNumberFa } from "@/lib/format";

const MIN_AMOUNT = 1000;
const MAX_AMOUNT = 100_000_000;
const PRESETS = [100_000, 200_000, 500_000, 1_000_000];

export function TopupDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (b: boolean) => void;
}) {
  const [amount, setAmount] = React.useState<string>("");
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const numericValue = amount ? Number(amount) : 0;
  const isValid =
    Number.isFinite(numericValue) &&
    numericValue >= MIN_AMOUNT &&
    numericValue <= MAX_AMOUNT;

  const mutation = useMutation({
    mutationFn: async (value: number) => {
      return api.post<{
        transaction_id: string;
        token: string;
        url: string;
        bypass: boolean;
      }>("/wallet/topup", { amount: value });
    },
    onSuccess: (result) => {
      // Always invalidate so the PENDING deposit shows up in the wallet
      // card even if the user never finishes the gateway flow.
      queryClient.invalidateQueries({ queryKey: ["me"] });
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
      setAmount("");
      onOpenChange(false);

      if (result.bypass) {
        toast({
          title: "درگاه پرداخت در حالت تست",
          description: "تراکنش به‌صورت آزمایشی ثبت شد.",
        });
        return;
      }

      if (typeof window !== "undefined" && result.url) {
        // Redirect to gateway; it will redirect back to /payment/callback
        window.location.href = result.url;
      } else {
        toast({
          title: "آدرس درگاه دریافت نشد",
          description: "لطفاً دوباره تلاش کنید.",
          variant: "destructive",
        });
      }
    },
    onError: (err: unknown) => {
      const message =
        (err as { message?: string })?.message || "خطا در ثبت درخواست";
      toast({
        title: "خطا",
        description: message,
        variant: "destructive",
      });
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!isValid) {
      toast({
        title: "مقدار نامعتبر",
        description: `مبلغ باید بین ${formatNumberFa(MIN_AMOUNT)} و ${formatNumberFa(MAX_AMOUNT)} تومان باشد.`,
        variant: "destructive",
      });
      return;
    }
    mutation.mutate(numericValue);
  };

  const handleOpenChange = (next: boolean) => {
    if (!next) setAmount("");
    onOpenChange(next);
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setAmount(digitsOnly(e.target.value));
  };

  const displayValue = amount ? formatNumberFa(amount) : "";

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent>
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>افزایش موجودی</DialogTitle>
            <DialogDescription>
              مبلغ مورد نظر را به تومان وارد کن یا یکی از مبلغ‌های پیشنهادی را انتخاب کن.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="topup-amount">مبلغ (تومان)</Label>
              <Input
                id="topup-amount"
                type="text"
                inputMode="numeric"
                autoComplete="off"
                value={displayValue}
                onChange={handleChange}
                placeholder="۵۰،۰۰۰"
                disabled={mutation.isPending}
                dir="ltr"
                className="text-right tabular-nums text-lg"
                required
              />
              <p className="text-xs text-muted-foreground">
                {amount
                  ? `${formatNumberFa(amount)} تومان`
                  : `بین ${formatNumberFa(MIN_AMOUNT)} تا ${formatNumberFa(MAX_AMOUNT)} تومان`}
              </p>
            </div>

            <div className="flex flex-wrap gap-2">
              {PRESETS.map((value) => (
                <Button
                  key={value}
                  type="button"
                  variant={Number(amount) === value ? "default" : "outline"}
                  size="sm"
                  onClick={() => setAmount(String(value))}
                  disabled={mutation.isPending}
                >
                  {formatNumberFa(value)} تومان
                </Button>
              ))}
            </div>
          </div>

          <DialogFooter className="gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => handleOpenChange(false)}
              disabled={mutation.isPending}
            >
              انصراف
            </Button>
            <Button type="submit" disabled={mutation.isPending || !isValid}>
              {mutation.isPending ? "در حال ثبت..." : "ثبت درخواست"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
