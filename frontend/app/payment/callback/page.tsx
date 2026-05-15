"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { api } from "@/lib/api";
import { formatNumberFa } from "@/lib/format";

type VerifyResponse = {
  transaction_id: string | null;
  success: boolean;
  status: string;
  amount: number;
  ref_id: string | null;
};

function PaymentCallbackFallback() {
  return (
    <div className="min-h-dvh flex items-center justify-center bg-neutral-50 p-4">
      <Card className="w-full max-w-md">
        <CardContent className="p-8 text-center space-y-4">
          <Loader2 className="mx-auto h-12 w-12 text-primary animate-spin" />
          <h2 className="text-lg font-semibold">در حال آماده‌سازی...</h2>
        </CardContent>
      </Card>
    </div>
  );
}

export default function PaymentCallbackPage() {
  // useSearchParams forces the page out of static prerendering, which crashes
  // `next build` unless it sits inside a Suspense boundary. Wrap the body so
  // the build can render the fallback statically and stream the rest.
  return (
    <React.Suspense fallback={<PaymentCallbackFallback />}>
      <PaymentCallbackContent />
    </React.Suspense>
  );
}

function PaymentCallbackContent() {
  const router = useRouter();
  const params = useSearchParams();
  const queryClient = useQueryClient();

  // Most gateways pass either `authority` or `token`. Try both.
  const authority =
    params?.get("authority") || params?.get("token") || params?.get("Authority");
  const gatewayStatus = params?.get("status") || params?.get("Status");

  const verify = useMutation({
    mutationFn: async () => {
      if (!authority) throw new Error("شناسهٔ پرداخت ارسال نشده است.");
      return api.post<VerifyResponse>("/wallet/verify", { authority });
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["me"] });
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
    },
  });

  React.useEffect(() => {
    if (!authority) return;
    verify.mutate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authority]);

  const isLoading = !authority ? false : verify.isPending || verify.isIdle;
  const result = verify.data;
  const errorMessage =
    (verify.error as { message?: string } | undefined)?.message ||
    (!authority ? "شناسهٔ پرداخت در آدرس بازگشت وجود ندارد." : null);

  return (
    <div className="min-h-dvh flex items-center justify-center bg-neutral-50 p-4">
      <Card className="w-full max-w-md">
        <CardContent className="p-8 text-center space-y-4">
          {isLoading ? (
            <>
              <Loader2 className="mx-auto h-12 w-12 text-primary animate-spin" />
              <h2 className="text-lg font-semibold">در حال تأیید پرداخت...</h2>
              <p className="text-sm text-muted-foreground">
                لطفاً صفحه را نبندید.
              </p>
            </>
          ) : result?.success ? (
            <>
              <CheckCircle2 className="mx-auto h-12 w-12 text-emerald-600" />
              <h2 className="text-lg font-semibold">پرداخت موفق</h2>
              <p className="text-sm text-muted-foreground">
                مبلغ <span className="font-medium tabular-nums">
                  {formatNumberFa(result.amount)}
                </span>{" "}
                تومان به موجودی شما اضافه شد.
              </p>
              {result.ref_id ? (
                <p className="text-xs text-muted-foreground tabular-nums">
                  شناسهٔ پرداخت: {result.ref_id}
                </p>
              ) : null}
              <Button className="w-full" onClick={() => router.replace("/home")}>
                بازگشت به داشبورد
              </Button>
            </>
          ) : (
            <>
              <XCircle className="mx-auto h-12 w-12 text-rose-600" />
              <h2 className="text-lg font-semibold">پرداخت ناموفق</h2>
              <p className="text-sm text-muted-foreground">
                {errorMessage ||
                  "پرداخت تأیید نشد. در صورت کسر وجه، طی ۷۲ ساعت برگشت داده می‌شود."}
              </p>
              {gatewayStatus ? (
                <p className="text-xs text-muted-foreground">
                  وضعیت درگاه: {gatewayStatus}
                </p>
              ) : null}
              <div className="flex gap-2">
                <Button
                  className="flex-1"
                  variant="outline"
                  onClick={() => router.replace("/home")}
                >
                  بازگشت
                </Button>
                <Button
                  className="flex-1"
                  onClick={() => verify.mutate()}
                  disabled={!authority || verify.isPending}
                >
                  تلاش مجدد
                </Button>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
