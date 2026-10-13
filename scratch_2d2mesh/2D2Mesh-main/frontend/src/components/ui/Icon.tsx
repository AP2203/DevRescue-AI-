import type { SVGProps } from "react";

const paths: Record<string, React.ReactNode> = {
  logo: (
    <>
      <path d="M12 2 3 7.5v9L12 22l9-5.5v-9L12 2Z" />
      <path d="M12 11.5V22M12 11.5 3 7.5m9 4 9-4" />
    </>
  ),
  dashboard: (
    <>
      <rect x="3" y="3" width="7.5" height="9" rx="1.5" />
      <rect x="13.5" y="3" width="7.5" height="5.5" rx="1.5" />
      <rect x="13.5" y="12" width="7.5" height="9" rx="1.5" />
      <rect x="3" y="15.5" width="7.5" height="5.5" rx="1.5" />
    </>
  ),
  generate: (
    <path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9L12 3ZM19 16l.9 2.1L22 19l-2.1.9L19 22l-.9-2.1L16 19l2.1-.9L19 16ZM5 15l.7 1.8L7.5 17.5l-1.8.7L5 20l-.7-1.8L2.5 17.5l1.8-.7L5 15Z" />
  ),
  projects: (
    <>
      <path d="M4 4h6l2 2h8a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z" />
    </>
  ),
  cube: (
    <>
      <path d="M21 7.5 12 2.25 3 7.5v9L12 21.75 21 16.5v-9Z" />
      <path d="M12 21.75V11.25M3 7.5l9 3.75 9-3.75" />
    </>
  ),
  upload: (
    <>
      <path d="M12 16V4m0 0 4 4m-4-4-4 4" />
      <path d="M4 16v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3" />
    </>
  ),
  download: (
    <>
      <path d="M12 4v12m0 0 4-4m-4 4-4-4" />
      <path d="M4 16v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3" />
    </>
  ),
  share: (
    <>
      <circle cx="18" cy="5" r="3" />
      <circle cx="6" cy="12" r="3" />
      <circle cx="18" cy="19" r="3" />
      <path d="m8.6 13.5 6.8 4M15.4 6.5l-6.8 4" />
    </>
  ),
  trash: (
    <>
      <path d="M3 6h18M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2m3 0v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" />
      <path d="M10 11v6M14 11v6" />
    </>
  ),
  settings: (
    <>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1Z" />
    </>
  ),
  user: (
    <>
      <circle cx="12" cy="8" r="4" />
      <path d="M4 21c0-4 3.6-6.5 8-6.5s8 2.5 8 6.5" />
    </>
  ),
  sun: (
    <>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2m0 16v2M4.9 4.9l1.4 1.4m11.4 11.4 1.4 1.4M2 12h2m16 0h2M4.9 19.1l1.4-1.4m11.4-11.4 1.4-1.4" />
    </>
  ),
  moon: <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79Z" />,
  search: <path d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z" />,
  grid: (
    <>
      <rect x="3" y="3" width="7" height="7" rx="1.5" />
      <rect x="14" y="3" width="7" height="7" rx="1.5" />
      <rect x="3" y="14" width="7" height="7" rx="1.5" />
      <rect x="14" y="14" width="7" height="7" rx="1.5" />
    </>
  ),
  list: (
    <>
      <path d="M8 6h13M8 12h13M8 18h13" />
      <circle cx="3.5" cy="6" r="0.5" />
      <circle cx="3.5" cy="12" r="0.5" />
      <circle cx="3.5" cy="18" r="0.5" />
    </>
  ),
  sort: (
    <>
      <path d="M7 3v13.5M7 16.5 3.5 13M7 16.5 10.5 13" />
      <path d="M17 21V7.5M17 7.5 13.5 11M17 7.5 20.5 11" />
    </>
  ),
  filter: <path d="M3 5h18l-7 8v6l-4-2v-4L3 5Z" />,
  play: <path d="M8 5.5v13l11-6.5-11-6.5Z" />,
  check: <path d="m4 12 5 5L20 6" />,
  close: <path d="M6 6l12 12M18 6 6 18" />,
  menu: <path d="M4 6h16M4 12h16M4 18h16" />,
  chevronDown: <path d="m6 9 6 6 6-6" />,
  chevronRight: <path d="m9 6 6 6-6 6" />,
  chevronLeft: <path d="m15 6-6 6 6 6" />,
  arrowRight: <path d="M5 12h14m-6-6 6 6-6 6" />,
  arrowUpRight: <path d="M7 17 17 7M8 7h9v9" />,
  image: (
    <>
      <rect x="3" y="3" width="18" height="18" rx="3" />
      <circle cx="8.5" cy="8.5" r="1.5" />
      <path d="m21 15-5-5L5 21" />
    </>
  ),
  lock: (
    <>
      <rect x="4" y="10" width="16" height="11" rx="2" />
      <path d="M8 10V7a4 4 0 0 1 8 0v3" />
    </>
  ),
  mail: (
    <>
      <rect x="2" y="4" width="20" height="16" rx="2" />
      <path d="m2 7 10 7 10-7" />
    </>
  ),
  eye: (
    <>
      <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z" />
      <circle cx="12" cy="12" r="3" />
    </>
  ),
  cpu: (
    <>
      <rect x="6" y="6" width="12" height="12" rx="2" />
      <path d="M9 2v2m6-2v2M9 20v2m6-2v2M2 9h2m-2 6h2m16-6h2m-2 6h2" />
      <rect x="9.5" y="9.5" width="5" height="5" rx="1" />
    </>
  ),
  clock: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </>
  ),
  hardDrive: (
    <>
      <path d="M21 8a2 2 0 0 0-1.5-1.97L6 2.5A2 2 0 0 0 3.5 4.5L2 16a2 2 0 0 0 .28 1.02L5.5 21A2 2 0 0 0 7.2 22h9.6a2 2 0 0 0 1.7-.98l3.22-3.98A2 2 0 0 0 22 16L21 8Z" />
      <path d="M5 9h14M4 12h16" />
    </>
  ),
  layers: (
    <>
      <path d="m12 2 9 5-9 5-9-5 9-5Z" />
      <path d="m3 12 9 5 9-5" />
      <path d="m3 17 9 5 9-5" />
    </>
  ),
  zap: <path d="M13 2 3 14h7l-1 8 11-14h-7l1-6Z" />,
  more: (
    <>
      <circle cx="12" cy="5" r="1.5" />
      <circle cx="12" cy="12" r="1.5" />
      <circle cx="12" cy="19" r="1.5" />
    </>
  ),
  fullscreen: (
    <>
      <path d="M8 3H3v5M16 3h5v5M8 21H3v-5M16 21h5v-5" />
    </>
  ),
  fullscreenExit: (
    <>
      <path d="M8 3v5H3M16 3v5h5M8 21v-5H3M16 21v-5h5" />
    </>
  ),
  wireframe: (
    <>
      <path d="M21 7.5 12 2.25 3 7.5v9L12 21.75 21 16.5v-9Z" />
      <path d="M12 2.25V11M12 21.75V11M12 11 3 7.5M12 11l9-3.5M12 11 3 16.5M12 11l9 5.5" />
    </>
  ),
  gridOff: (
    <>
      <rect x="3" y="3" width="7" height="7" rx="1.5" />
      <rect x="14" y="3" width="7" height="7" rx="1.5" />
      <rect x="3" y="14" width="7" height="7" rx="1.5" />
      <path d="M14 21h7M21 14v7" />
    </>
  ),
  light: (
    <>
      <path d="M12 3v2m0 14v2M5.2 5.2l1.4 1.4m11 11 1.4 1.4M3 12h2m14 0h2M5.2 18.8l1.4-1.4M17.6 6.6l1.4-1.4" />
      <path d="M9 18h6M10 21h4" />
      <rect x="9" y="3" width="6" height="13" rx="3" />
    </>
  ),
  camera: (
    <>
      <path d="M4 8h2l1.5-2h9L18 8h2a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1Z" />
      <circle cx="12" cy="14" r="4" />
    </>
  ),
  info: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 16v-5M12 8h.01" />
    </>
  ),
  refresh: <path d="M21 12a9 9 0 1 1-2.64-6.36M21 3v5h-5" />,
  plus: <path d="M12 5v14M5 12h14" />,
  external: (
    <>
      <path d="M14 4h6v6" />
      <path d="M20 4 10 14" />
      <path d="M19 13v6a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h6" />
    </>
  ),
  rotate: (
    <>
      <path d="M21 12a9 9 0 1 1-2.64-6.36L21 8" />
      <path d="M21 3v5h-5" />
    </>
  ),
  zoomIn: (
    <>
      <circle cx="11" cy="11" r="7" />
      <path d="m21 21-4.35-4.35M8 11h6M11 8v6" />
    </>
  ),
  zoomOut: (
    <>
      <circle cx="11" cy="11" r="7" />
      <path d="m21 21-4.35-4.35M8 11h6" />
    </>
  ),
  move: <path d="M12 2v20m-4-4 4 4 4-4M2 12h20m-4-4 4 4-4 4" />,
  sparkles: (
    <>
      <path d="M12 3l1.7 4.6L18 9.3l-4.3 1.7L12 15.6l-1.7-4.6L6 9.3l4.3-1.7L12 3Z" />
      <path d="M19 15l.9 2.1L22 18l-2.1.9L19 21l-.9-2.1L16 18l2.1-.9L19 15Z" />
    </>
  ),
  pending: <path d="M12 6v6l4 2" />,
  alert: (
    <>
      <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z" />
      <path d="M12 9v4M12 17h.01" />
    </>
  ),
  verified: (
    <>
      <path d="m3 12 3.1 3.1L12 8.2" />
      <path d="m9 15 2 2 4-4" />
      <path d="M12 2 20 5v7c0 5-3.5 8.5-8 10-4.5-1.5-8-5-8-10V5l8-3Z" />
    </>
  ),
  youtube: (
    <>
      <rect x="2" y="5" width="20" height="14" rx="4" />
      <path d="m10 9 5 3-5 3V9Z" />
    </>
  ),
  twitter: (
    <>
      <path d="M4 4h4.5L12 9.5 15.5 4H20l-6 8 6 8h-4.5L12 14.5 8.5 20H4l6-8-6-8Z" />
    </>
  ),
  github: (
    <>
      <path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3.3-.4 6.8-1.6 6.8-7.2a5.6 5.6 0 0 0-1.5-3.9 5.2 5.2 0 0 0-.1-3.9s-1.2-.4-4 1.5a13.8 13.8 0 0 0-7.2 0C6 2.9 4.8 3.3 4.8 3.3a5.2 5.2 0 0 0-.1 3.9 5.6 5.6 0 0 0-1.5 3.9c0 5.6 3.5 6.8 6.8 7.2a4.8 4.8 0 0 0-1 3.5V22" />
      <path d="M9 18c-4.5 2-4.5-2-6-2" />
    </>
  ),
  star: <path d="M12 2l2.9 6.26L21.5 9.27l-5 4.73 1.3 6.6L12 17.2 6.2 20.6l1.3-6.6-5-4.73 6.6-1.01L12 2Z" />,
  shield: (
    <>
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z" />
      <path d="m9 12 2 2 4-4" />
    </>
  ),
  wand: (
    <>
      <path d="m15 4 5 5" />
      <path d="M18.5 2.5a2.12 2.12 0 0 1 3 3L7 20l-4 1 1-4L18.5 2.5Z" />
    </>
  ),
};

export type IconName = keyof typeof paths;

export function Icon({
  name,
  className = "h-5 w-5",
  strokeWidth = 1.8,
  ...props
}: { name: IconName; strokeWidth?: number } & SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
      {...props}
    >
      {paths[name]}
    </svg>
  );
}
