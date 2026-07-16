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
import { useLanguage } from "@/lib/i18n";

interface VideoIntakeProps {
  initialVideos: VideoRecord[];
}

function formatDate(iso: string, language: "en" | "zh-CN"): string {
  const d = new Date(iso);
  return d.toLocaleString(language === "zh-CN" ? "zh-CN" : "en-US", {
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
): { reason: string } | null {
  const lower = errorMessage.toLowerCase();
  if (errorMessage.includes("No Chinese soft subtitles")) {
    return { reason: "non_chinese_subtitles" };
  }
  if (errorMessage.includes("No Chinese subtitles were found")) {
    return { reason: "non_chinese_subtitles" };
  }
  if (errorMessage.includes("no usable soft subtitles")) {
    return { reason: "no_subtitles" };
  }
  if (errorMessage.includes("no usable creator or automatic subtitles")) {
    return { reason: "no_subtitles" };
  }
  if (errorMessage.includes("temporarily unavailable")) {
    return { reason: "subtitle_unstable" };
  }
  if (lower.includes("login expired")) {
    return { reason: "auth_expired" };
  }
  if (lower.includes("login is required")) {
    return { reason: "not_logged_in" };
  }
  return null;
}

export function VideoIntake({ initialVideos }: VideoIntakeProps) {
  const router = useRouter();
  const { language, t } = useLanguage();
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
    platform?: VideoRecord["platform"];
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

  function localizedVideoError(message: string, fallback: string): string {
    const lower = message.toLowerCase();
    if (
      lower.includes("unsupported platform") ||
      lower.includes("unsupported video") ||
      lower.includes("cannot resolve aweme_id")
    ) {
      return t("This video link is not supported. Check the link and try again.");
    }
    if (
      lower.includes("already processing") ||
      lower.includes("could not be claimed for processing")
    ) {
      return t("This video is already being processed.");
    }
    if (lower.includes("subtitle")) {
      return t("Couldn't fetch subtitles. Check your network or login status and try again.");
    }
    if (lower.includes("asr")) {
      return t("ASR processing failed: {detail}", { detail: message.trim() });
    }
    if (
      lower.includes("audio") ||
      lower.includes("yt-dlp") ||
      lower.includes("ffmpeg") ||
      lower.includes("douyin fetcher")
    ) {
      return t("Couldn't download or prepare the video audio. Check your network and try again.");
    }
    return fallback;
  }

  function showLocalizedError(error: unknown, fallback: string) {
    const message = error instanceof Error ? error.message : String(error ?? "");
    console.error("[video-intake]", message);
    setError(localizedVideoError(message, fallback));
  }

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
      showLocalizedError(
        e,
        t("Couldn't import the video. Check the link and network, then try again.")
      );
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
          const video = videos.find((item) => item.id === videoId);
          setPendingSubtitleDecision({
            videoId,
            title: video?.title ?? t("Video"),
            platform: video?.platform,
            reason: mapped.reason,
          });
        } else {
          showLocalizedError(
            processed.error_message,
            t("Video processing failed. Check your network and model settings, then try again.")
          );
        }
      }
    } catch (e) {
      showLocalizedError(
        e,
        t("Video processing failed. Check your network and model settings, then try again.")
      );
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
      setError(e instanceof Error ? e.message : t("Operation failed"));
    }
  }

  async function handleProcess(video: VideoRecord) {
    setError("");
    // Douyin has no subtitle path; Bilibili and YouTube always pre-check.
    if (video.status === "completed" && video.platform === "douyin") {
      await runProcess(video.id);
      return;
    }
    setCheckingVideoId(video.id);
    let hasSubtitles = true;
    let reason = "no_subtitles";
    let availableLanguages: string[] | undefined;
    try {
      if (video.platform === "bilibili") {
        await refreshBilibiliCookieIfPossible();
      }
      let result = await checkSubtitles(video.id);
      hasSubtitles = result.has_subtitles;
      reason = result.reason ?? "no_subtitles";
      availableLanguages = result.available_languages;

      // One recheck after auth_expired for bilibili
      if (video.platform === "bilibili" && !hasSubtitles && reason === "auth_expired") {
        await refreshBilibiliCookieIfPossible();
        result = await checkSubtitles(video.id);
        hasSubtitles = result.has_subtitles;
        reason = result.reason ?? "no_subtitles";
        availableLanguages = result.available_languages;
      }
    } catch (e) {
      showLocalizedError(
        e,
        t("Couldn't fetch subtitles. Check your network or login status and try again.")
      );
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
        platform: video.platform,
        reason,
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
          placeholder={t("Paste a Bilibili, Douyin, or YouTube URL")}
          value={url}
        />
        <button
          className="flex h-10 items-center justify-center gap-2 rounded-md bg-primary px-4 text-sm font-semibold text-white whitespace-nowrap disabled:opacity-50"
          disabled={isSubmitting || !url.trim()}
          type="submit"
        >
          <Plus className="h-4 w-4" />
          {isSubmitting ? t("Saving...") : t("Add video")}
        </button>
      </form>

      {error ? <ErrorBanner message={error} /> : null}

      {pendingSubtitleDecision ? (
        <SubtitleDecisionDialog
          videoTitle={pendingSubtitleDecision.title}
          reason={pendingSubtitleDecision.reason}
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
          onGoToLogin={
            pendingSubtitleDecision.platform === "bilibili"
              ? () => {
                  setPendingSubtitleDecision(null);
                  router.push("/login");
                }
              : undefined
          }
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
              <h2>{t("Imported videos")}</h2>
              <p>
                {isExpanded
                  ? t("All imported records, ordered by import time.")
                  : t("Scroll or click a card to focus.")}
              </p>
            </div>
            <button
              className="expand-toggle-btn"
              type="button"
              aria-label={t("Toggle list view")}
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
                      {video.status === "completed"
                        ? t("Completed")
                        : video.status === "failed"
                          ? t("Failed")
                          : video.status === "processing"
                            ? t("Processing")
                            : t("Pending")}
                    </span>
                  </div>

                  {/* Info grid: Platform / Author / Imported */}
                  <div className="video-info-grid">
                    <div>
                      <span className="video-info-label">{t("Platform")}</span>
                      <span className="video-info-value">
                        {video.platform === "bilibili"
                          ? "Bilibili"
                          : video.platform === "youtube"
                            ? "YouTube"
                            : "Douyin"}
                      </span>
                    </div>
                    <div>
                      <span className="video-info-label">{t("Author")}</span>
                      <span className="video-info-value">
                        {video.author || t("Unknown author")}
                      </span>
                    </div>
                    <div>
                      <span className="video-info-label">{t("Imported")}</span>
                      <span className="video-info-value">
                        {formatDate(video.created_at, language)}
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
                          ? t("Checking...")
                          : processingVideoId === video.id || video.status === "processing"
                            ? t("Processing...")
                            : video.status === "completed"
                              ? t("Re-process")
                              : t("Process")}
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
                        {t("Delete")}
                      </button>
                    </div>
                  </div>

                  {/* Error message for failed videos */}
                  {video.status === "failed" && video.error_message ? (
                    <p className="mt-2 text-xs text-[hsl(0_40%_72%)]">
                      {localizedVideoError(
                        video.error_message,
                        t("Video processing failed. Check your network and model settings, then try again.")
                      )}
                    </p>
                  ) : null}
                </article>
              );
            })}
          </div>
        </section>
      ) : (
        <div className="flex flex-col items-center gap-2 py-16 text-center">
          <p className="text-sm text-muted-foreground">
            {t("No videos yet. Paste a Bilibili or Douyin URL above to get started.")}
          </p>
        </div>
      )}
    </div>
  );
}
