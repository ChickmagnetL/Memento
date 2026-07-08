"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Database,
  HelpCircle,
  Home,
  LogIn,
  MessageSquare,
  PanelLeft,
  PanelLeftClose,
  Settings,
} from "lucide-react";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/", label: "Home", icon: Home },
  { href: "/knowledge", label: "Knowledge Base", icon: Database },
  { href: "/chat", label: "Chat", icon: MessageSquare },
  { href: "/login", label: "Login", icon: LogIn },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem("sidebar-collapsed");
    // Persisted UI preference; must be read after mount to avoid SSR hydration mismatch.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (stored === "true") setCollapsed(true);
  }, []);

  function toggle() {
    setCollapsed((prev) => {
      const next = !prev;
      localStorage.setItem("sidebar-collapsed", String(next));
      return next;
    });
  }

  const width = collapsed
    ? "var(--sidebar-collapsed-width)"
    : "var(--sidebar-width)";

  return (
    <aside
      className="flex flex-col border-r border-border bg-[var(--color-bg-sidebar)] transition-[width]"
      style={{ width }}
    >
      {/* Header: only visible when collapsed, toggle centered below traffic lights */}
      {collapsed && (
        <div className="flex items-center justify-center border-b border-border px-2 pt-9 pb-2">
          <button
            onClick={toggle}
            className="rounded-md p-1.5 text-muted-foreground hover:bg-[var(--color-bg-hover)] hover:text-[var(--color-text)] transition-colors"
            aria-label="Expand sidebar"
          >
            <PanelLeft className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Toggle button when expanded: top-right corner */}
      {!collapsed && (
        <div className="flex justify-end px-2 pt-2">
          <button
            onClick={toggle}
            className="rounded-md p-1.5 text-muted-foreground hover:bg-[var(--color-bg-hover)] hover:text-[var(--color-text)] transition-colors"
            aria-label="Collapse sidebar"
          >
            <PanelLeftClose className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Nav items */}
      <nav className="flex-1 py-2">
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "mx-2 mb-0.5 flex items-center gap-3 rounded-md py-2 text-sm transition-colors",
                collapsed ? "justify-center px-0" : "px-3",
                active
                  ? "bg-[var(--color-bg-hover)] text-[var(--color-text)]"
                  : "text-[var(--color-text-muted)] hover:bg-[var(--color-bg-hover)] hover:text-[var(--color-text)]"
              )}
            >
              <Icon
                className="h-4 w-4 shrink-0"
                strokeWidth={active ? 2 : 1.5}
              />
              {!collapsed && <span>{label}</span>}
            </Link>
          );
        })}
        <div className="mx-2 my-2 border-t border-border" />
        {(() => {
          const helpHref = "/help";
          const helpActive = pathname === helpHref;
          return (
            <Link
              href={helpHref}
              className={cn(
                "mx-2 mb-0.5 flex items-center gap-3 rounded-md py-2 text-sm transition-colors",
                collapsed ? "justify-center px-0" : "px-3",
                helpActive
                  ? "bg-[var(--color-bg-hover)] text-[var(--color-text)]"
                  : "text-[var(--color-text-muted)] hover:bg-[var(--color-bg-hover)] hover:text-[var(--color-text)]"
              )}
            >
              <HelpCircle
                className="h-4 w-4 shrink-0"
                strokeWidth={helpActive ? 2 : 1.5}
              />
              {!collapsed && <span>Help</span>}
            </Link>
          );
        })()}
      </nav>
    </aside>
  );
}
