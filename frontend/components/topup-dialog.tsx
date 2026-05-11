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

const MIN_AMOUNT = 1000;
const MAX_AMOUNT = 100000000;

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

  const mutation = useMutation({
    mutationFn: async (value: number) => {
      return api.post("/ledger/topup", { amount: value });
    },
    onSuccess: () => {
      toast({
        title: "درخواست شما ثبت شد",
        description: "پس از تأیید ادمین به موجودی اضافه می‌شه.",
      });
      queryClient.invalidateQueries({ queryKey: ["me"] });
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
      setAmount("");
      onOpenChange(false);
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
    const value = Number(amount);
    if (!Number.isFinite(value) || value < MIN_AMOUNT || value > MAX_AMOUNT) {
      toast({
        title: "مقدار نامعتبر",
        description: `مبلغ باید بین ${MIN_AMOUNT} و ${MAX_AMOUNT} باشد.`,
        variant: "destructive",
      });
      return;
    }
    mutation.mutate(value);
  };

  const handleOpenChange = (next: boolean) => {
    if (!next) {
      setAmount("");
    }
    onOpenChange(next);
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent>
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>افزایش موجودی</DialogTitle>
            <DialogDescription>
              مبلغ مورد نظر را به تومان وارد کن.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-2 py-4">
            <Label htmlFor="topup-amount">مبلغ</Label>
            <Input
              id="topup-amount"
              type="number"
              inputMode="numeric"
              min={MIN_AMOUNT}
              max={MAX_AMOUNT}
              step={1000}
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="مثلاً 50000"
              disabled={mutation.isPending}
              required
            />
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
            <Button type="submit" disabled={mutation.isPending}>
              ثبت درخواست
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
