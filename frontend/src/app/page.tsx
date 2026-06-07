import { getHealth } from "@/lib/api";

// Server component: fetches backend health on each request (dev). Errors are
// caught so the page still renders if the backend is down.
export default async function Home() {
  let status = "unreachable";
  try {
    const health = await getHealth();
    status = health.status;
  } catch {
    status = "unreachable";
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4">
      <h1 className="text-2xl font-bold">Memento</h1>
      <p className="text-muted-foreground">
        Backend health: <span className="font-mono">{status}</span>
      </p>
    </main>
  );
}
