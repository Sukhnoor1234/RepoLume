import type { ReactNode } from "react";

export function Logo() {
  return <svg className="brand-mark" viewBox="0 0 32 32" fill="none" aria-hidden="true"><path d="M8 7v18h17M8 16h12V7" stroke="currentColor" strokeWidth="2" /><rect x="4" y="3" width="8" height="8" rx="2" fill="currentColor" /><rect x="16" y="3" width="8" height="8" rx="2" fill="currentColor" /><rect x="21" y="21" width="8" height="8" rx="2" fill="currentColor" /></svg>;
}

const paths = {
  map: <><rect x="3" y="3" width="6" height="6" rx="1" /><rect x="15" y="15" width="6" height="6" rx="1" /><path d="M6 9v9h9M9 6h9v9" /></>,
  guide: <><circle cx="12" cy="12" r="9" /><path d="m16 8-2 6-6 2 2-6Z" /></>,
  book: <path d="M12 5v16M3 4h5a4 4 0 0 1 4 3 4 4 0 0 1 4-3h5v14h-5a4 4 0 0 0-4 3 4 4 0 0 0-4-3H3Z" />,
  route: <><circle cx="6" cy="5" r="2" /><circle cx="18" cy="19" r="2" /><path d="M8 5h7a4 4 0 0 1 0 8H9a3 3 0 0 0 0 6h7" /></>,
  external: <path d="M8 16 19 5M10 5h9v9M5 9v10h10" />,
  code: <path d="m8 6-6 6 6 6m8-12 6 6-6 6m-3-14-2 16" />,
  arrow: <path d="M4 12h16m-6-6 6 6-6 6" />,
  folder: <path d="M3 7V5h7l2 3h9v12H3Z" />,
} satisfies Record<string, ReactNode>;

export function Icon({ name }: { name: keyof typeof paths }) {
  return <svg className="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}
