import { cn } from "@/shared/lib/utils";

export const Divider = ({ className }: { className?: string }) => {
  return <div className={cn("w-full h-[1px] bg-border", className)} />;
};
