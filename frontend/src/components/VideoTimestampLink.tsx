/**
 * VideoTimestampLink component for memento:// protocol URLs.
 *
 * Parses memento://play URLs and triggers video player via Electron IPC.
 * Falls back to no-op in non-Electron environments.
 */

interface VideoTimestampLinkProps {
  href: string;
  children: React.ReactNode;
}

export function VideoTimestampLink({ href, children }: VideoTimestampLinkProps) {
  const handleClick = (event: React.MouseEvent<HTMLAnchorElement>) => {
    event.preventDefault();

    if (!window.electron) {
      console.warn("VideoTimestampLink: window.electron not available");
      return;
    }

    try {
      const url = new URL(href);
      const platform = url.searchParams.get("platform");
      const videoId = url.searchParams.get("video_id");
      const timestamp = url.searchParams.get("t");

      if (!platform || !videoId || !timestamp) {
        console.error("VideoTimestampLink: missing required params", { platform, videoId, timestamp });
        return;
      }

      const timestampNum = parseInt(timestamp, 10);
      if (isNaN(timestampNum)) {
        console.error("VideoTimestampLink: invalid timestamp", timestamp);
        return;
      }

      window.electron.openVideoPlayer({
        platform,
        videoId,
        timestamp: timestampNum,
      });
    } catch (error) {
      console.error("VideoTimestampLink: failed to parse URL", error);
    }
  };

  return (
    <a
      href={href}
      onClick={handleClick}
      className="text-primary underline-offset-4 hover:underline cursor-pointer"
    >
      {children}
    </a>
  );
}
