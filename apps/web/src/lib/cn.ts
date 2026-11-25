import { clsx, type ClassValue } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

// Teach tailwind-merge the custom tokens in globals.css (@theme), so that e.g.
// `text-caption` (a size) and `text-muted` (a colour) are not treated as a clash.
const twMerge = extendTailwindMerge({
  extend: {
    theme: {
      text: ["caption", "label", "body", "heading", "title", "kpi"],
      radius: ["card", "tile"],
      shadow: ["card", "pop"],
    },
  },
});

/** Join class names; later Tailwind classes win over earlier ones. */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
