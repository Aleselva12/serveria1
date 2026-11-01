import { useEffect, useRef, type ReactNode } from "react";
import { MoreVertical } from "lucide-react";

/** Native disclosure keeps actions keyboard-accessible without a second menu state. */
export default function FileMenu({
  label,
  children,
  disabled = false,
}: {
  label: string;
  children: ReactNode;
  disabled?: boolean;
}) {
  const ref = useRef<HTMLDetailsElement>(null);
  useEffect(() => {
    const outside = (event: PointerEvent) => {
      if (event.target instanceof Node && !ref.current?.contains(event.target))
        ref.current?.removeAttribute("open");
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape" && ref.current?.open) {
        ref.current.open = false;
        ref.current.querySelector("summary")?.focus();
      }
    };
    document.addEventListener("pointerdown", outside);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("pointerdown", outside);
      document.removeEventListener("keydown", escape);
    };
  }, []);
  return (
    <details className="drive-menu" ref={ref}>
      <summary
        aria-label={label}
        aria-disabled={disabled}
        title={label}
        onClick={(event) => {
          if (disabled) event.preventDefault();
        }}
      >
        <MoreVertical size={19} />
      </summary>
      <div
        className="drive-menu-popover"
        onClick={(event) => {
          if ((event.target as HTMLElement).closest("button:not(:disabled)"))
            ref.current?.removeAttribute("open");
        }}
      >
        {children}
      </div>
    </details>
  );
}
