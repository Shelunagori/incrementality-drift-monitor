import { litLamp, STATUS_STYLES } from "@/lib/status";
import type { Status } from "@/lib/types";

const LAMPS: Status[] = ["RED", "YELLOW", "GREEN"];

/** Three-lamp traffic light; only the lamp for `status` is lit. */
export function TrafficLight({ status }: { status: Status }) {
  const lit = litLamp(status);
  return (
    <div
      className="flex flex-col gap-1 rounded-full bg-slate-800 p-1.5"
      role="img"
      aria-label={`Status ${status}`}
    >
      {LAMPS.map((s, i) => (
        <span
          key={s}
          data-testid={`lamp-${s}`}
          data-lit={i === lit}
          className={`h-4 w-4 rounded-full ${i === lit ? STATUS_STYLES[s].dot : "bg-slate-600"}`}
        />
      ))}
    </div>
  );
}
