import Link from "next/link";
import { LogIn, ShoppingBag } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function LoginPage() {
  return (
    <main className="min-h-dvh bg-background flex flex-col">
      <div className="flex-1 flex flex-col justify-center px-6 py-12 max-w-sm mx-auto w-full">
        <div className="flex items-center gap-3 mb-12">
          <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-primary text-primary-foreground">
            <ShoppingBag className="w-5 h-5" />
          </div>
          <span className="text-xl font-bold">افزودن سریع محصول</span>
        </div>

        <div className="space-y-3 mb-10">
          <h1 className="text-3xl font-bold tracking-tight">ورود به غرفه</h1>
          <p className="text-base text-muted-foreground leading-relaxed">
            از حساب باسلام خودت استفاده کن. هیچ رمزی اینجا وارد نمی‌شه — فقط روی دکمه‌ی زیر بزن.
          </p>
        </div>

        <Button asChild size="lg" className="w-full">
          <a href="/api/proxy/auth/basalam/login">
            <LogIn />
            ورود با باسلام
          </a>
        </Button>
      </div>

      <div className="px-6 py-8 max-w-sm mx-auto w-full text-center">
        <p className="text-sm text-muted-foreground">
          مشکل در ورود؟{" "}
          <Link href="/support" className="text-primary hover:underline">
            با ما در تماس باش.
          </Link>
        </p>
      </div>
    </main>
  );
}
