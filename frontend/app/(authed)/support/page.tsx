"use client";

import * as React from "react";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useToast } from "@/hooks/use-toast";
import {
  api,
  type Paginated,
  type SupportTicketOut,
} from "@/lib/api";
import { formatDateFa } from "@/lib/format";

type StatusVariant = "default" | "secondary" | "destructive" | "outline";

const STATUS_MAP: Record<
  SupportTicketOut["status"],
  { label: string; variant: StatusVariant }
> = {
  OPEN: { label: "باز", variant: "default" },
  IN_PROGRESS: { label: "در حال بررسی", variant: "secondary" },
  CLOSED: { label: "بسته", variant: "outline" },
};

function truncate(text: string, max: number): string {
  if (text.length <= max) return text;
  return text.slice(0, max) + "…";
}

function TicketCard({ ticket }: { ticket: SupportTicketOut }) {
  const status = STATUS_MAP[ticket.status];
  return (
    <Card className="p-3 space-y-2">
      <div className="flex items-center justify-between gap-2">
        <div className="font-semibold text-sm truncate">{ticket.subject}</div>
        <Badge variant={status.variant} className="shrink-0">
          {status.label}
        </Badge>
      </div>
      <p className="text-xs text-muted-foreground line-clamp-2">
        {truncate(ticket.body ?? "", 120)}
      </p>
      <div className="text-xs text-muted-foreground">
        {formatDateFa(ticket.created_at)}
      </div>
    </Card>
  );
}

function TicketSkeleton() {
  return (
    <Card className="p-3 space-y-2">
      <div className="flex items-center justify-between gap-2">
        <Skeleton className="h-4 w-1/2" />
        <Skeleton className="h-5 w-16 rounded-md" />
      </div>
      <Skeleton className="h-3 w-full" />
      <Skeleton className="h-3 w-1/3" />
    </Card>
  );
}

function NewTicketDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (b: boolean) => void;
}) {
  const [subject, setSubject] = React.useState("");
  const [body, setBody] = React.useState("");
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: async (payload: { subject: string; body: string }) => {
      return api.post("/support/tickets", payload);
    },
    onSuccess: () => {
      toast({ title: "تیکت ثبت شد" });
      queryClient.invalidateQueries({ queryKey: ["tickets"] });
      setSubject("");
      setBody("");
      onOpenChange(false);
    },
    onError: (err: unknown) => {
      const message =
        (err as { message?: string })?.message || "خطا در ثبت تیکت";
      toast({
        title: "خطا",
        description: message,
        variant: "destructive",
      });
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmedSubject = subject.trim();
    const trimmedBody = body.trim();
    if (!trimmedSubject || !trimmedBody) {
      toast({
        title: "اطلاعات ناقص",
        description: "موضوع و متن تیکت الزامی است.",
        variant: "destructive",
      });
      return;
    }
    mutation.mutate({ subject: trimmedSubject, body: trimmedBody });
  };

  const handleOpenChange = (next: boolean) => {
    if (!next) {
      setSubject("");
      setBody("");
    }
    onOpenChange(next);
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent>
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>تیکت جدید</DialogTitle>
            <DialogDescription>
              موضوع و توضیحات مشکل خود را وارد کنید.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-3 py-4">
            <div className="grid gap-2">
              <Label htmlFor="ticket-subject">موضوع</Label>
              <Input
                id="ticket-subject"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                placeholder="مثلاً مشکل در پرداخت"
                disabled={mutation.isPending}
                required
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="ticket-body">متن</Label>
              <Textarea
                id="ticket-body"
                value={body}
                onChange={(e) => setBody(e.target.value)}
                placeholder="توضیحات کامل مشکل خود را بنویسید"
                rows={5}
                disabled={mutation.isPending}
                required
              />
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
            <Button type="submit" disabled={mutation.isPending}>
              ثبت تیکت
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export default function SupportPage() {
  const [newOpen, setNewOpen] = React.useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["tickets", { page: 1 }],
    queryFn: () =>
      api.get<Paginated<SupportTicketOut>>(
        "/support/tickets?page=1&page_size=20",
      ),
  });

  const items = data?.items ?? [];
  const isEmpty = !isLoading && items.length === 0;

  return (
    <>
      <header className="sticky top-0 z-30 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 border-b">
        <div className="flex items-center justify-between gap-3 px-4 h-14">
          <h1 className="text-sm font-semibold truncate">پشتیبانی</h1>
          <Button
            size="sm"
            onClick={() => setNewOpen(true)}
            className="shrink-0"
          >
            <Plus className="h-4 w-4 ms-1" />
            تیکت جدید
          </Button>
        </div>
      </header>

      <main className="px-4 py-4 space-y-3">
        {isLoading ? (
          <>
            <TicketSkeleton />
            <TicketSkeleton />
            <TicketSkeleton />
          </>
        ) : isEmpty ? (
          <div className="flex flex-col items-center justify-center text-center py-16">
            <p className="text-sm text-muted-foreground">
              تا الان تیکتی ثبت نشده.
            </p>
          </div>
        ) : (
          items.map((ticket) => (
            <TicketCard key={ticket.id} ticket={ticket} />
          ))
        )}
      </main>

      <NewTicketDialog open={newOpen} onOpenChange={setNewOpen} />
    </>
  );
}
