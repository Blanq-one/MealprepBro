import type { MetadataRoute } from "next";

export const dynamic = "force-static";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Mealbro",
    short_name: "Mealbro",
    description: "Cook a meal now or prep for the days ahead, from what you have.",
    id: "/",
    start_url: "/cook/",
    scope: "/",
    display: "standalone",
    orientation: "portrait",
    background_color: "#fff8f1",
    theme_color: "#fff8f1",
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icons/maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
