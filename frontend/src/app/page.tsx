import { listVideos, type VideoRecord } from "@/lib/api";
import { VideoIntake } from "./video-intake";

export default async function Home() {
  let videos: VideoRecord[] = [];

  try {
    videos = await listVideos();
  } catch {
    videos = [];
  }

  return <VideoIntake initialVideos={videos} />;
}
