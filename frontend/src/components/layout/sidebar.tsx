"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Video,
  Database,
  MessageSquare,
  Settings,
  HelpCircle,
  PanelLeftClose,
  PanelLeft,
} from "lucide-react";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/", label: "Video Intake", icon: Video },
  { href: "/knowledge", label: "Knowledge Base", icon: Database },
  { href: "/chat", label: "Chat", icon: MessageSquare },
  { href: "/settings", label: "Settings", icon: Settings },
];

interface SidebarProps {
  health: string;
}

export function Sidebar({ health }: SidebarProps) {
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

  const isConnected = health === "ok";
  const width = collapsed
    ? "var(--sidebar-collapsed-width)"
    : "var(--sidebar-width)";

  return (
    <aside
      className="flex flex-col border-r border-border bg-[var(--color-bg-sidebar)] transition-[width]"
      style={{ width }}
    >
      {/* Header */}
      <div className="flex h-12 items-center gap-2 px-3 border-b border-border" style={{ WebkitAppRegion: "drag" } as React.CSSProperties}>
        {!collapsed && (
          <span className="flex-1 text-sm font-semibold tracking-tight">
            Memento
          </span>
        )}
        <button
          onClick={toggle}
          className="rounded-md p-1.5 text-muted-foreground hover:bg-[var(--color-bg-hover)] hover:text-[var(--color-text)] transition-colors"
          style={{ WebkitAppRegion: "no-drag" } as React.CSSProperties}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? (
            <PanelLeft className="h-4 w-4" />
          ) : (
            <PanelLeftClose className="h-4 w-4" />
          )}
        </button>
      </div>

      {/* Nav items */}
      <nav className="flex-1 py-2">
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 mx-2 mb-0.5 rounded-md px-3 py-2 text-sm transition-colors",
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
                "flex items-center gap-3 mx-2 mb-0.5 rounded-md px-3 py-2 text-sm transition-colors",
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

      {/* Health indicator */}
      <div className="border-t border-border px-3 py-3">
        <div className="flex items-center gap-2">
          <span
            className={cn(
              "h-2 w-2 rounded-full shrink-0",
              isConnected ? "bg-[var(--color-success)]" : "bg-[var(--color-destructive)]"
            )}
          />
          {!collapsed && (
            <span className="text-xs text-[var(--color-text-muted)]">
              {isConnected ? "Connected" : "Offline"}
            </span>
          )}
        </div>
      </div>
    </aside>
  );
}
