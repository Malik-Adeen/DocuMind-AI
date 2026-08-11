import * as React from "react";
import { cn } from "@/lib/utils";

const Progress = React.forwardRef(({ className, value, isFailed, isComplete, ...props }, ref) => {
  const pct = Math.min(100, Math.max(0, value || 0));
  return (
    <div
      ref={ref}
      className={cn(
        "relative h-2 w-full overflow-hidden rounded-full bg-muted/60",
        className
      )}
      {...props}
    >
      <div
        className={cn(
          "h-full w-full flex-1 transition-all duration-300 rounded-full relative",
          isFailed
            ? "bg-destructive"
            : isComplete
            ? "bg-primary"
            : "bg-primary"
        )}
        style={{ transform: `translateX(-${100 - pct}%)` }}
      >
        {!isFailed && !isComplete && pct < 100 && (
          <div className="absolute inset-0 shimmer"></div>
        )}
      </div>
    </div>
  );
});
Progress.displayName = "Progress";

export { Progress };
