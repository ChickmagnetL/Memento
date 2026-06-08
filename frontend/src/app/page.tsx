import { getHealth, listVideos, type VideoRecord } from "@/lib/api";
import { VideoIntake } from "./video-intake";

export default async function Home() {
  let health = "unreachable";
  let videos: VideoRecord[] = [];

  try {
    const data = await getHealth();
    health = data.status;
    videos = await listVideos();
  } catch {
    health = "unreachable";
    videos = [];
  }

  return <VideoIntake initialHealth={health} initialVideos={videos} />;
}
