"use client";
import * as M from "@radix-ui/react-dropdown-menu";
import { cn } from "@/lib/utils";

export const DropdownMenu = M.Root;
export const DropdownMenuTrigger = M.Trigger;
export function DropdownMenuContent({ className, align = "end", ...p }: M.DropdownMenuContentProps) {
  return (
    <M.Portal>
      <M.Content align={align} sideOffset={6} className={cn("z-50 min-w-[12rem] rounded-md border bg-popover p-1 text-popover-foreground shadow-lg", className)} {...p} />
    </M.Portal>
  );
}
export function DropdownMenuItem({ className, ...p }: M.DropdownMenuItemProps) {
  return <M.Item className={cn("flex cursor-pointer select-none items-center gap-2 rounded-sm px-2 py-1.5 text-sm outline-none focus:bg-accent focus:text-accent-foreground [&_svg]:size-4", className)} {...p} />;
}
export const DropdownMenuSeparator = () => <M.Separator className="my-1 h-px bg-border" />;
export const DropdownMenuLabel = ({ children }: { children: React.ReactNode }) => <M.Label className="px-2 py-1.5 text-xs font-medium text-muted-foreground">{children}</M.Label>;
