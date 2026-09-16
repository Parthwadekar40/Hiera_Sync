import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { useNotifications } from "../contexts/NotificationContext";
import { searchApi } from "../api";
import { FaSearch, FaBell, FaUserCircle, FaSignOutAlt } from "react-icons/fa";
import { GraduationCap } from "lucide-react";

export default function Navbar() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const { unreadCount } = useNotifications();

  const [search, setSearch] = useState("");
  const [results, setResults] = useState<any[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  const searchWrapRef = useRef<HTMLDivElement | null>(null);
  const menuWrapRef = useRef<HTMLDivElement | null>(null);

  const handleLogout = () => {
    setMenuOpen(false);
    logout();
    navigate("/login");
  };

  // Close overlays on Escape / outside click - the profile menu used to be
  // hover-only, which made it unusable with a keyboard or on touch devices.
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setMenuOpen(false);
        setSearch("");
      }
    };

    const onPointerDown = (event: MouseEvent) => {
      const target = event.target as Node;
      if (menuWrapRef.current && !menuWrapRef.current.contains(target)) {
        setMenuOpen(false);
      }
      if (searchWrapRef.current && !searchWrapRef.current.contains(target)) {
        setResults([]);
      }
    };

    document.addEventListener("keydown", onKeyDown);
    document.addEventListener("mousedown", onPointerDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("mousedown", onPointerDown);
    };
  }, []);

  useEffect(() => {
    if (!search.trim()) {
      setResults([]);
      return;
    }

    const debounce = setTimeout(async () => {
      setIsSearching(true);
      try {
        const data = await searchApi.globalSearch(search);
        setResults(data.results || []);
      } catch (err) {
        console.error("Search error", err);
        setResults([]);
      } finally {
        setIsSearching(false);
      }
    }, 500);

    return () => clearTimeout(debounce);
  }, [search]);

  const goTo = (type?: string) => {
    setSearch("");
    if (type === "faculty") navigate("/employees");
    else if (type === "task") navigate("/tasks");
    else if (type === "event") navigate("/calendar");
    else if (type === "notification") navigate("/notifications");
    else navigate("/dashboard");
  };

  return (
    <header className="hs-shell-pad sticky top-0 z-30 flex h-20 items-center justify-between gap-4 border-b border-[#E5E5E5] bg-white/95 font-sans backdrop-blur">
      <div className="relative min-w-0 flex-1 sm:flex-none" ref={searchWrapRef}>
        <div className="flex w-full items-center rounded-md border border-[#E5E5E5] bg-canvas px-3.5 py-2 transition-all duration-200 focus-within:border-brand-plum focus-within:bg-white focus-within:ring-4 focus-within:ring-brand-plum/10 sm:w-80 lg:w-96">
          <FaSearch className="shrink-0 text-[#A1A1AA]" />
          <input
            type="text"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search tasks, faculty, notifications..."
            aria-label="Search department records"
            className="ml-3 w-full min-w-0 bg-transparent text-sm font-medium text-ink outline-none placeholder:text-[#A1A1AA]"
          />
        </div>

        {search.trim() !== "" && (
          <div className="absolute left-0 top-[calc(100%+8px)] z-50 max-h-96 w-full overflow-y-auto rounded-lg border border-[#E5E5E5] bg-white shadow-xl sm:w-96">
            {isSearching ? (
              <div className="p-4 text-center text-sm font-medium text-[#71717A]">
                Searching department records...
              </div>
            ) : results.length > 0 ? (
              results.map((item, index) => (
                <button
                  key={item.id || index}
                  type="button"
                  onClick={() => goTo(item.type)}
                  className="flex w-full flex-col items-start px-4 py-2.5 text-left transition hover:bg-[#F5F3FF]"
                >
                  <span className="text-sm font-semibold text-ink">{item.title}</span>
                  <span className="mt-0.5 text-xs font-medium capitalize text-brand-plum">
                    {item.type}
                  </span>
                </button>
              ))
            ) : (
              <div className="p-4 text-center text-sm font-medium text-[#71717A]">
                No results found
              </div>
            )}
          </div>
        )}
      </div>

      <div className="flex shrink-0 items-center gap-3 sm:gap-5">
        <div className="hidden items-center gap-2.5 rounded-pill border border-[#EDE9FE] bg-[#F5F3FF] px-3 py-1.5 md:flex">
          <GraduationCap className="h-4 w-4 text-brand-plum" />
          <div className="text-left">
            <h3 className="text-xs font-semibold leading-tight text-[#2E1065]">
              AIML Department · SBJIT
            </h3>
            <p className="hs-kicker text-[10px] text-[#7C6AAE]">Nagpur Campus</p>
          </div>
        </div>

        <button
          onClick={() => navigate("/notifications")}
          className="relative rounded-md border border-[#E5E5E5] bg-canvas p-2.5 text-ink-soft shadow-xs transition hover:bg-[#F5F3FF] hover:text-brand-plum"
          title="Notifications"
          aria-label={`Notifications${unreadCount > 0 ? `, ${unreadCount} unread` : ""}`}
        >
          <FaBell className="text-base" />
          {unreadCount > 0 && (
            <span className="absolute -right-1 -top-1 flex h-4 min-w-[16px] items-center justify-center rounded-pill bg-[#E11D48] px-1 text-[10px] font-bold text-white">
              {unreadCount}
            </span>
          )}
        </button>

        <div className="relative" ref={menuWrapRef}>
          <button
            type="button"
            onClick={() => setMenuOpen((open) => !open)}
            aria-expanded={menuOpen}
            aria-haspopup="menu"
            className="flex items-center gap-3 rounded-md border border-[#E5E5E5] bg-canvas px-3 py-1.5 transition hover:bg-[#EFEFEF]"
          >
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-pill bg-gradient-to-tr from-brand-plum to-[#9333EA] text-xs font-bold text-white shadow-xs">
              {user?.name ? (
                user.name.substring(0, 2).toUpperCase()
              ) : (
                <FaUserCircle className="text-xl" />
              )}
            </span>

            <span className="hidden text-left sm:block">
              <span className="block text-sm font-semibold leading-tight text-ink">
                {user?.name || "Admin User"}
              </span>
              <span className="block text-xs font-medium leading-tight text-ink-muted">
                {user?.role || "ADMIN"}
              </span>
            </span>
          </button>

          {menuOpen && (
            <div
              role="menu"
              className="absolute right-0 top-[calc(100%+8px)] z-50 w-56 rounded-lg border border-[#E5E5E5] bg-white p-1.5 shadow-xl"
            >
              <div className="mb-1 border-b border-[#F4F4F5] px-3 py-2">
                <p className="hs-kicker">Signed in as</p>
                <p className="mt-1 truncate text-xs font-bold text-ink">
                  {user?.email || "admin@hierasync.edu"}
                </p>
              </div>
              <button
                role="menuitem"
                onClick={handleLogout}
                className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-xs font-bold text-rose-600 transition hover:bg-rose-50"
              >
                <FaSignOutAlt className="text-sm" />
                <span>Sign Out</span>
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
