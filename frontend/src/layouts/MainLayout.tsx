import { useEffect } from "react";
import { useLocation, Outlet } from "react-router-dom";
import Sidebar from "./Sidebar";
import Navbar from "./Navbar";

/**
 * App shell.
 *
 * The <main> region deliberately carries no horizontal padding: every page
 * uses the shared `.hs-page` shell (see src/index.css) so gutters, content
 * width and bento alignment stay pixel-identical across the whole app.
 */
export default function MainLayout() {
  const { pathname } = useLocation();

  // Every page starts at the top instead of inheriting the previous page's
  // scroll offset (which made bento rows look clipped or half-shifted).
  useEffect(() => {
    document.scrollingElement?.scrollTo({ top: 0, behavior: "auto" });
  }, [pathname]);

  return (
    <div className="flex min-h-screen bg-canvas font-sans text-ink antialiased">
      <a
        href="#hs-workspace"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-brand-plum focus:px-4 focus:py-2 focus:text-sm focus:font-semibold focus:text-white"
      >
        Skip to content
      </a>

      <Sidebar />

      <div className="flex min-w-0 flex-1 flex-col bg-canvas">
        <Navbar />
        <main id="hs-workspace" className="flex-1 overflow-x-hidden">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
