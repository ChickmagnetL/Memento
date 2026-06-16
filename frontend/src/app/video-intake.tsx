"use client";

import { FormEvent, useState } from "react";
import { Play, Plus, Database } from "lucide-react";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorBanner } from "@/components/ui/error-banner";
import {
  createVideo,
  listVideos,
  processVideo,
  type VideoRecord,
} from "@/lib/api";

interface VideoIntakeProps {
  initialHealth: string;
  initialVideos: VideoRecord[];
}

export function VideoIntake({ initialHealth, initialVideos }: VideoIntakeProps) {
  const [url, setUrl] = useState("");
  const [videos, setVideos] = useState<VideoRecord[]>(initialVideos);
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [processingVideoId, setProcessingVideoId] = useState<string | null>(
    null
  );

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

  async function handleProcess(videoId: string) {
    setError("");
    setProcessingVideoId(videoId);

    try {
      await processVideo(videoId);
      await refreshVideos();
    } catch {
      setError("Processing failed. Try again.");
    } finally {
      setProcessingVideoId(null);
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-6 px-8 py-8">
      <header className="space-y-1">
        <h1 className="text-xl font-semibold">Video Intake</h1>
        <p className="text-sm text-muted-foreground">
          Backend: <span className="font-mono">{initialHealth}</span>
        </p>
      </header>

      <form className="flex flex-col gap-3 sm:flex-row" onSubmit={handleSubmit}>
        <input
          className="h-10 flex-1 rounded-md border border-input bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground"
          onChange={(event) => setUrl(event.target.value)}
          placeholder="Paste a Bilibili or Douyin URL"
          value={url}
        />
        <Button disabled={isSubmitting || !url.trim()} type="submit">
          <Plus />
          {isSubmitting ? "Saving..." : "Add video"}
        </Button>
      </form>

      {error ? <ErrorBanner message={error} /> : null}

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Videos</h2>
        {videos.length === 0 ? (
          <EmptyState icon={Database} title="No videos yet" description="Paste a Bilibili or Douyin URL above." />
        ) : (
          <ul className="space-y-3">
            {videos.map((video) => (
              <li className="rounded-md border border-border p-4 transition-shadow hover:shadow-sm" key={video.id}>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="font-medium">{video.title}</p>
                  <div className="flex items-center gap-2">
                    <span className="rounded-md bg-[var(--color-bg-hover)] px-2 py-1 text-xs text-secondary-foreground">
                      {video.status}
                    </span>
                    <Button
                      className="min-w-28"
                      disabled={
                        video.status === "processing" ||
                        processingVideoId !== null
                      }
                      onClick={() => handleProcess(video.id)}
                      size="sm"
                      type="button"
                      variant="outline"
                    >
                      <Play />
                      {processingVideoId === video.id
                        ? "Processing..."
                        : "Process"}
                    </Button>
                  </div>
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
    </div>
  );
}
