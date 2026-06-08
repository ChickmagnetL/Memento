"use client";

import { FormEvent, useState } from "react";
import { Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { createVideo, listVideos, type VideoRecord } from "@/lib/api";

interface VideoIntakeProps {
  initialHealth: string;
  initialVideos: VideoRecord[];
}

export function VideoIntake({ initialHealth, initialVideos }: VideoIntakeProps) {
  const [url, setUrl] = useState("");
  const [videos, setVideos] = useState<VideoRecord[]>(initialVideos);
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function refreshVideos() {
    const items = await listVideos();
    setVideos(items);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const trimmedUrl = url.trim();
    if (!trimmedUrl) {
      return;
    }

    setError("");
    setIsSubmitting(true);

    try {
      await createVideo({ url: trimmedUrl });
      setUrl("");
      await refreshVideos();
    } catch {
      setError("Only Bilibili and Douyin URLs are supported.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-3xl flex-col gap-6 px-6 py-10">
      <header className="space-y-1">
        <h1 className="text-2xl font-bold">Memento</h1>
        <p className="text-sm text-muted-foreground">
          Backend health: <span className="font-mono">{initialHealth}</span>
        </p>
      </header>

      <form className="flex flex-col gap-3 sm:flex-row" onSubmit={handleSubmit}>
        <input
          className="h-10 flex-1 rounded-md border border-input bg-background px-3 text-sm"
          onChange={(event) => setUrl(event.target.value)}
          placeholder="Paste a Bilibili or Douyin URL"
          value={url}
        />
        <Button disabled={isSubmitting || !url.trim()} type="submit">
          <Plus />
          {isSubmitting ? "Saving..." : "Add video"}
        </Button>
      </form>

      {error ? <p className="text-sm text-destructive">{error}</p> : null}

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Videos</h2>
        {videos.length === 0 ? (
          <p className="text-sm text-muted-foreground">No videos yet.</p>
        ) : (
          <ul className="space-y-3">
            {videos.map((video) => (
              <li className="rounded-md border p-4" key={video.id}>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="font-medium">{video.title}</p>
                  <span className="rounded-md bg-secondary px-2 py-1 text-xs">
                    {video.status}
                  </span>
                </div>
                <p className="mt-2 break-all text-sm text-muted-foreground">
                  {video.url}
                </p>
                <p className="mt-2 text-xs text-muted-foreground">
                  {video.platform} · {video.created_at}
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
