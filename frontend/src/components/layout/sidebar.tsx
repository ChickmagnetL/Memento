"use client";

import { type MouseEvent, useEffect, useState } from "react";
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

  function openGitHub(event: MouseEvent<HTMLAnchorElement>) {
    if (!window.electron?.openGitHub) return;
    event.preventDefault();
    void window.electron.openGitHub();
  }

  const width = collapsed
    ? "var(--sidebar-collapsed-width)"
    : "var(--sidebar-width)";

  return (
    <aside
      className="shrink-0 flex flex-col border-r border-border bg-[var(--color-bg-sidebar)] transition-[width]"
      style={{ width }}
    >
      {/* Header: only visible when collapsed, toggle centered below traffic lights */}
      {collapsed && (
        <div className="desktop-sidebar-titlebar flex items-center justify-center border-b border-border px-2 pt-9 pb-2">
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
        <div className="desktop-sidebar-titlebar flex justify-end px-2 pt-2">
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
      <div className="p-2">
        <a
          href="https://github.com/ChickmagnetL/Memento"
          target="_blank"
          rel="noreferrer"
          onClick={openGitHub}
          className={cn(
            "flex h-8 w-8 items-center justify-center rounded-md text-[var(--color-text-muted)] transition-colors hover:bg-[var(--color-bg-hover)] hover:text-[var(--color-text)]",
            !collapsed && "ml-1.5"
          )}
          aria-label="Open Memento on GitHub"
          title="GitHub"
        >
          <svg
            className="h-5 w-5 fill-current"
            viewBox="0 0 16 16"
            aria-hidden="true"
          >
            <path d="M8 0C3.58 0 0 3.64 0 8.13c0 3.59 2.29 6.64 5.47 7.71.4.08.55-.18.55-.39 0-.19-.01-.83-.01-1.51-2.01.44-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.53-.01-.54.63-.01 1.08.59 1.23.83.72 1.23 1.87.88 2.33.67.07-.53.28-.88.51-1.08-1.78-.21-3.64-.91-3.64-4.02 0-.89.31-1.62.82-2.19-.08-.21-.36-1.04.08-2.16 0 0 .67-.22 2.2.84A7.46 7.46 0 0 1 8 3.95c.68 0 1.36.09 2 .27 1.53-1.06 2.2-.84 2.2-.84.44 1.12.16 1.95.08 2.16.51.57.82 1.29.82 2.19 0 3.12-1.87 3.81-3.65 4.02.29.25.54.74.54 1.5 0 1.08-.01 1.95-.01 2.22 0 .22.15.47.55.39A8.12 8.12 0 0 0 16 8.13C16 3.64 12.42 0 8 0Z" />
          </svg>
        </a>
      </div>
    </aside>
  );
}
