import Image from "next/image";
import { cn } from "@/lib/cn";

/** The IREP "ip" mark on a white tile: it sits on the navy sidebar, login panel and classroom bar,
 *  where the deep blue of the mark would otherwise disappear. Size with w-/h- classes. */
export function BrandMark({ className, rounded = "rounded-tile" }: { className?: string; rounded?: string }) {
  return (
    <span className={cn("relative inline-flex shrink-0 items-center justify-center bg-white shadow-card overflow-hidden", rounded, className)}>
      <Image src="/icons/logo-mark.png" alt="IREP" fill sizes="64px" className="object-contain p-[12%]" priority />
    </span>
  );
}
