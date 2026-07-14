"use client";

import { FormEvent, useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { Plus } from "lucide-react";

import { ErrorBanner } from "@/components/ui/error-banner";
import { SubtitleDecisionDialog } from "@/components/ui/subtitle-decision-dialog";
import {
  checkSubtitles,
  createVideo,
  deleteVideo,
  listVideos,
  processVideo,
  type VideoRecord,
} from "@/lib/api";

interface VideoIntakeProps {
  initialVideos: VideoRecord[];
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("en-US", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).replace(/\//g, "-").replace(",", "");
}

function statusBadgeClass(status: string): string {
  if (status === "completed") return "video-badge completed";
  if (status === "failed") return "video-badge failed";
  return "video-badge pending";
}

function actionLabel(status: string): string {
  if (status === "completed") return "Re-process";
  return "Process";
}

async function refreshBilibiliCookieIfPossible() {
  if (typeof window === "undefined" || !window.electron?.refreshBilibiliCookie) return;
  try {
    await window.electron.refreshBilibiliCookie();
  } catch {
    // ignore
  }
}

function mapSoftSubtitleError(
  errorMessage: string
): { reason: string; message?: string } | null {
  const lower = errorMessage.toLowerCase();
  if (errorMessage.includes("No Chinese soft subtitles")) {
    return { reason: "non_chinese_subtitles", message: errorMessage };
  }
  if (errorMessage.includes("no usable soft subtitles")) {
    return { reason: "no_subtitles", message: errorMessage };
  }
  if (errorMessage.includes("temporarily unavailable")) {
    return { reason: "subtitle_unstable", message: errorMessage };
  }
  if (lower.includes("login expired")) {
    return { reason: "auth_expired", message: errorMessage };
  }
  if (lower.includes("login is required")) {
    return { reason: "not_logged_in", message: errorMessage };
  }
  return null;
}

export function VideoIntake({ initialVideos }: VideoIntakeProps) {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [videos, setVideos] = useState<VideoRecord[]>(initialVideos);
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [processingVideoId, setProcessingVideoId] = useState<string | null>(null);
  const [checkingVideoId, setCheckingVideoId] = useState<string | null>(null);
  const [pendingSubtitleDecision, setPendingSubtitleDecision] = useState<{
    videoId: string;
    title: string;
    reason: string;
    message?: string;
    availableLanguages?: string[];
  } | null>(null);

  // Carousel state
  const [activeCardIndex, setActiveCardIndex] = useState(0);
  const [isExpanded, setIsExpanded] = useState(false);
  const pageShellRef = useRef<HTMLDivElement>(null);
  const heroUrlRef = useRef<HTMLDivElement>(null);
  const cardsStageRef = useRef<HTMLDivElement>(null);

  const isBusy =
    processingVideoId !== null ||
    checkingVideoId !== null ||
    pendingSubtitleDecision !== null;

  async function refreshVideos() {
    const items = await listVideos();
    setVideos(items);
    if (activeCardIndex >= items.length) {
      setActiveCardIndex(Math.max(0, items.length - 1));
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedUrl = url.trim();
    if (!trimmedUrl) return;
    setError("");
    setIsSubmitting(true);
    try {
      await createVideo({ url: trimmedUrl });
      setUrl("");
      await refreshVideos();
      // Focus the newly added video (newest is at index 0)
      setActiveCardIndex(0);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Operation failed");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function runProcess(
    videoId: string,
    fallback?: "asr",
    options?: { allowNonChinese?: boolean }
  ) {
    setProcessingVideoId(videoId);
    try {
      const processed = await processVideo(videoId, fallback, options);
      await refreshVideos();
      if (processed.status === "failed" && processed.error_message) {
        const mapped = mapSoftSubtitleError(processed.error_message);
        if (mapped) {
          const title =
            videos.find((item) => item.id === videoId)?.title ?? "Video";
          setPendingSubtitleDecision({
            videoId,
            title,
            reason: mapped.reason,
            message: mapped.message,
          });
        } else {
          setError(processed.error_message);
        }
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Operation failed");
    } finally {
      setProcessingVideoId(null);
    }
  }

  async function handleDelete(videoId: string) {
    setError("");
    try {
      await deleteVideo(videoId);
      await refreshVideos();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Operation failed");
    }
  }

  async function handleProcess(video: VideoRecord) {
    setError("");
    // Only non-bilibili completed can bypass pre-check; bilibili always checks
    if (video.status === "completed" && video.platform !== "bilibili") {
      await runProcess(video.id);
      return;
    }
    setCheckingVideoId(video.id);
    let hasSubtitles = true;
    let reason = "no_subtitles";
    let message: string | undefined;
    let availableLanguages: string[] | undefined;
    try {
      if (video.platform === "bilibili") {
        await refreshBilibiliCookieIfPossible();
      }
      let result = await checkSubtitles(video.id);
      hasSubtitles = result.has_subtitles;
      reason = result.reason ?? "no_subtitles";
      message = result.message;
      availableLanguages = result.available_languages;

      // One recheck after auth_expired for bilibili
      if (video.platform === "bilibili" && !hasSubtitles && reason === "auth_expired") {
        await refreshBilibiliCookieIfPossible();
        result = await checkSubtitles(video.id);
        hasSubtitles = result.has_subtitles;
        reason = result.reason ?? "no_subtitles";
        message = result.message;
        availableLanguages = result.available_languages;
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Operation failed");
      setCheckingVideoId(null);
      return;
    }
    setCheckingVideoId(null);
    if (hasSubtitles) {
      await runProcess(video.id);
    } else {
      setPendingSubtitleDecision({
        videoId: video.id,
        title: video.title,
        reason,
        message,
        availableLanguages,
      });
    }
  }

  useLayoutEffect(() => {
    const shell = pageShellRef.current;
    const heroUrl = heroUrlRef.current;
    if (!shell || !heroUrl) return;

    const updateHeroHeight = () => {
      const height = heroUrl.offsetHeight;
      shell.style.setProperty("--hero-url-height", `${height}px`);
      shell.style.setProperty("--hero-url-half-height", `${height / 2}px`);
    };

    updateHeroHeight();
    const resizeObserver = new ResizeObserver(updateHeroHeight);
    resizeObserver.observe(heroUrl);
    return () => resizeObserver.disconnect();
  }, []);

  // Measure card heights and set --list-y (expanded position) + --stage-height.
  // Cumulative height so cards of differing sizes (e.g. failed w/ error msg) don't overlap.
  useLayoutEffect(() => {
    const stage = cardsStageRef.current;
    if (!stage) return;
    const cards = Array.from(stage.querySelectorAll<HTMLElement>(".video-card"));
    if (cards.length === 0) return;
    const gap = 12;
    let cumulative = 0;
    cards.forEach((card) => {
      card.style.setProperty("--list-y", `${cumulative}px`);
      cumulative += card.offsetHeight + gap;
    });
    // stage height = last card's list-y + its own height
    const last = cards[cards.length - 1];
    const totalHeight = parseFloat(last.style.getPropertyValue("--list-y")) + last.offsetHeight;
    stage.style.setProperty("--stage-height", `${totalHeight}px`);
  }, [isExpanded, videos]);

  // Wheel event for carousel scrolling.
  // Trackpads emit many small continuous events per swipe; accumulate deltaY
  // and switch one card per threshold, with a cooldown to avoid overshooting.
  useEffect(() => {
    const stage = cardsStageRef.current;
    if (!stage) return;
    let acc = 0;
    let lastSwitch = 0;
    const threshold = 40;
    const cooldown = 180;
    function onWheel(e: WheelEvent) {
      if (isExpanded) return;
      e.preventDefault();
      const now = Date.now();
      if (now - lastSwitch < cooldown) return;
      acc += e.deltaY;
      if (Math.abs(acc) < threshold) return;
      const dir = acc > 0 ? 1 : -1;
      setActiveCardIndex((prev) =>
        Math.max(0, Math.min(videos.length - 1, prev + dir))
      );
      acc = 0;
      lastSwitch = now;
    }
    stage.addEventListener("wheel", onWheel, { passive: false });
    return () => stage.removeEventListener("wheel", onWheel);
  }, [isExpanded, videos.length]);

  const toggleExpand = useCallback(() => {
    setIsExpanded((prev) => !prev);
  }, []);

  return (
    <div ref={pageShellRef} className={`page-shell${isExpanded ? " is-expanded" : ""}`}>
      <div ref={heroUrlRef} className="page-hero-url">
        {/* SVG filter for handwriting roughness */}
        <svg width="0" height="0" aria-hidden="true" focusable="false" className="absolute">
        <filter id="handwriting-rough">
          <feTurbulence type="fractalNoise" baseFrequency="0.045" numOctaves="2" seed="11" result="noise" />
          <feDisplacementMap in="SourceGraphic" in2="noise" scale="1.8" xChannelSelector="R" yChannelSelector="G" />
        </filter>
      </svg>

      {/* Hero: Memento handwriting */}
      <section className="flex flex-col items-center gap-2.5 mb-2">
        <Image
          alt="Memento"
          className="brand-word"
          draggable={false}
          height={180}
          priority
          src="/memento-wordmark.svg"
          width={920}
        />
      </section>

      {/* URL input card */}
      <form
        className="grid grid-cols-[1fr_auto] gap-2.5 rounded-lg border border-border bg-[hsl(240_6%_10%)] p-3 shadow-sm"
        onSubmit={handleSubmit}
      >
        <input
          className="h-10 rounded-md border border-border bg-[hsl(240_10%_4%)] px-3 text-sm text-foreground placeholder:text-muted-foreground"
          onChange={(e) => setUrl(e.target.value)}
          placeholder="Paste a Bilibili or Douyin URL"
          value={url}
        />
        <button
          className="flex h-10 items-center justify-center gap-2 rounded-md bg-primary px-4 text-sm font-semibold text-white whitespace-nowrap disabled:opacity-50"
          disabled={isSubmitting || !url.trim()}
          type="submit"
        >
          <Plus className="h-4 w-4" />
          {isSubmitting ? "Saving..." : "Add video"}
        </button>
      </form>

      {error ? <ErrorBanner message={error} /> : null}

      {pendingSubtitleDecision ? (
        <SubtitleDecisionDialog
          videoTitle={pendingSubtitleDecision.title}
          reason={pendingSubtitleDecision.reason}
          message={pendingSubtitleDecision.message}
          availableLanguages={pendingSubtitleDecision.availableLanguages}
          onCancel={() => setPendingSubtitleDecision(null)}
          onUseAsr={() => {
            const { videoId } = pendingSubtitleDecision;
            setPendingSubtitleDecision(null);
            void runProcess(videoId, "asr");
          }}
          onUseOfficial={() => {
            const { videoId } = pendingSubtitleDecision;
            setPendingSubtitleDecision(null);
            void runProcess(videoId, undefined, { allowNonChinese: true });
          }}
          onGoToLogin={() => {
            setPendingSubtitleDecision(null);
            router.push("/login");
          }}
          onRetry={() => {
            const { videoId } = pendingSubtitleDecision;
            setPendingSubtitleDecision(null);
            const video = videos.find((item) => item.id === videoId);
            if (video) {
              void handleProcess(video);
            }
          }}
        />
      ) : null}
      </div>

      {/* Imported videos section */}
      {videos.length > 0 ? (
        <section className={`history-shell${isExpanded ? " is-expanded" : ""}`}>
          <div className="history-header">
            <div>
              <h2>Imported videos</h2>
              <p>
                {isExpanded
                  ? "All imported records, ordered by import time."
                  : "Scroll or click a card to focus."}
              </p>
            </div>
            <button
              className="expand-toggle-btn"
              type="button"
              aria-label="Toggle list view"
              onClick={toggleExpand}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <rect x="5" y="4" width="14" height="3" rx="1" />
                <rect x="5" y="10.5" width="14" height="3" rx="1" />
                <rect x="5" y="17" width="14" height="3" rx="1" />
              </svg>
            </button>
          </div>

          <div className="cards-stage" ref={cardsStageRef}>
            {videos.map((video, index) => {
              const offset = index - activeCardIndex;
              const isActive = offset === 0;

              return (
                <article
                  key={video.id}
                  className={`video-card${isActive ? " is-active" : ""}`}
                  style={{
                    "--offset": offset,
                    "--list-y": "0px",
                  } as React.CSSProperties}
                  onClick={() => {
                    if (isExpanded) return;
                    setActiveCardIndex(index);
                  }}
                >
                  {/* Title + badge */}
                  <div className="video-card-top">
                    <div className="video-card-title">{video.title}</div>
                    <span className={statusBadgeClass(video.status)}>
                      {video.status}
                    </span>
                  </div>

                  {/* Info grid: Platform / Author / Imported */}
                  <div className="video-info-grid">
                    <div>
                      <span className="video-info-label">Platform</span>
                      <span className="video-info-value">
                        {video.platform === "bilibili" ? "Bilibili" : "Douyin"}
                      </span>
                    </div>
                    <div>
                      <span className="video-info-label">Author</span>
                      <span className="video-info-value">
                        {video.author || "Unknown author"}
                      </span>
                    </div>
                    <div>
                      <span className="video-info-label">Imported</span>
                      <span className="video-info-value">
                        {formatDate(video.created_at)}
                      </span>
                    </div>
                  </div>

                  {/* URL row + actions */}
                  <div className="video-url-row">
                    <a
                      className="video-url-link"
                      href={video.url}
                      target="_blank"
                      rel="noreferrer"
                      onClick={(e) => e.stopPropagation()}
                    >
                      {video.url}
                    </a>
                    <div className="video-actions">
                      <button
                        className="video-action-btn primary"
                        type="button"
                        disabled={isBusy}
                        onClick={(e) => {
                          e.stopPropagation();
                          handleProcess(video);
                        }}
                      >
                        {checkingVideoId === video.id
                          ? "Checking..."
                          : processingVideoId === video.id || video.status === "processing"
                            ? "Processing..."
                            : actionLabel(video.status)}
                      </button>
                      <button
                        className="video-action-btn danger"
                        type="button"
                        disabled={processingVideoId !== null}
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDelete(video.id);
                        }}
                      >
                        Delete
                      </button>
                    </div>
                  </div>

                  {/* Error message for failed videos */}
                  {video.status === "failed" && video.error_message ? (
                    <p className="mt-2 text-xs text-[hsl(0_40%_72%)]">{video.error_message}</p>
                  ) : null}
                </article>
              );
            })}
          </div>
        </section>
      ) : (
        <div className="flex flex-col items-center gap-2 py-16 text-center">
          <p className="text-sm text-muted-foreground">
            No videos yet. Paste a Bilibili or Douyin URL above to get started.
          </p>
        </div>
      )}
    </div>
  );
}
