import { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useNotifications } from "../contexts/NotificationContext";
import { aiApi } from "../api";
import { NotificationResponse } from "../types";

import {
  Bell,
  CheckCircle2,
  Clock,
  Search,
  X,
  ArrowRight,
  RotateCw,
  Sparkles,
  ShieldAlert,
  ClipboardList,
  UserCheck,
  Calendar,
  BrainCircuit,
  Trash2,
  MailCheck,
  Mail,
  ExternalLink,
} from "lucide-react";

import "./Notifications.css";

export default function Notifications() {
  const navigate = useNavigate();
  const {
    notifications,
    unreadCount,
    loading,
    error,
    refreshNotifications,
    markAsRead,
    markAsUnread,
    markAllAsRead,
    deleteNotification,
  } = useNotifications();

  // Search & Filters State
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<"ALL" | "UNREAD" | "READ">("ALL");
  const [typeFilter, setTypeFilter] = useState<string>("ALL");
  const [priorityFilter, setPriorityFilter] = useState<string>("ALL");
  const [sortBy, setSortBy] = useState<"NEWEST" | "OLDEST" | "PRIORITY">("NEWEST");

  // Selected Notification Modal
  const [selectedNotif, setSelectedNotif] = useState<NotificationResponse | null>(null);

  // Toast Notification State
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // AI Assistant State
  const [aiSummary, setAiSummary] = useState(
    "AI analyzed department streams: Review pending approvals first, then address high-priority task deadlines."
  );
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => {
      setToastMessage(null);
    }, 3000);
  };

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await refreshNotifications();
    setTimeout(() => setIsRefreshing(false), 500);
    showToast("Notifications refreshed");
  };

  const handleGenerateSummary = async () => {
    setSummaryLoading(true);
    try {
      const res = await aiApi.getNotificationSummary();
      if (res && (res.summary || res.message)) {
        setAiSummary(res.summary || res.message);
      } else {
        setAiSummary(
          `AI analyzed ${notifications.length} notifications: ${unreadCount} items require immediate attention.`
        );
      }
      showToast("AI Summary generated");
    } catch (err: any) {
      console.error("AI summary error:", err);
      setAiSummary(
        `AI Summary: You currently have ${unreadCount} unread department alerts requiring priority action.`
      );
    } finally {
      setSummaryLoading(false);
    }
  };

  // Resolve target route from notification type or explicit route
  const getNotificationRoute = (notif: NotificationResponse): string => {
    if (notif.target_route) return notif.target_route;
    const typeLower = (notif.type || "").toLowerCase();
    if (typeLower.includes("task")) return "/tasks";
    if (typeLower.includes("approval")) return "/approvals";
    if (typeLower.includes("employee") || typeLower.includes("faculty") || typeLower.includes("join")) return "/employees";
    if (typeLower.includes("calendar") || typeLower.includes("event") || typeLower.includes("reminder")) return "/calendar";
    if (typeLower.includes("ai")) return "/ai";
    return "/dashboard";
  };

  const handleNotificationClick = (notif: NotificationResponse) => {
    if (!notif.is_read) {
      markAsRead(notif.id);
    }
    setSelectedNotif(notif);
  };

  const handleDirectNavigate = (e: React.MouseEvent, notif: NotificationResponse) => {
    e.stopPropagation();
    if (!notif.is_read) {
      markAsRead(notif.id);
    }
    const route = getNotificationRoute(notif);
    navigate(route);
  };

  // Helper for notification type icons
  const renderNotificationIcon = (type?: string, icon?: string) => {
    const t = (type || "").toLowerCase();
    if (t.includes("task")) return <ClipboardList size={20} />;
    if (t.includes("approval")) return <CheckCircle2 size={20} />;
    if (t.includes("employee") || t.includes("faculty")) return <UserCheck size={20} />;
    if (t.includes("calendar") || t.includes("reminder")) return <Calendar size={20} />;
    if (t.includes("ai")) return <BrainCircuit size={20} />;
    return <Bell size={20} />;
  };

  const getTypeClass = (type?: string): string => {
    const t = (type || "").toLowerCase();
    if (t.includes("task")) return "type-task";
    if (t.includes("approval")) return "type-approval";
    if (t.includes("employee") || t.includes("faculty")) return "type-employees";
    if (t.includes("calendar") || t.includes("reminder")) return "type-calendar";
    if (t.includes("ai")) return "type-ai";
    return "type-system";
  };

  // Computed summary metrics
  const totalCount = notifications.length;
  const tasksCount = notifications.filter(n => (n.type || "").toLowerCase().includes("task")).length;
  const approvalsCount = notifications.filter(n => (n.type || "").toLowerCase().includes("approval")).length;
  const systemCount = notifications.filter(n => {
    const t = (n.type || "").toLowerCase();
    return t.includes("ai") || t.includes("system") || t.includes("faculty") || t.includes("employee") || t.includes("calendar");
  }).length;

  const highPriorityCount = notifications.filter(n => (n.priority || "").toLowerCase() === "high").length;

  // Filtered and sorted notifications list
  const filteredNotifications = useMemo(() => {
    return notifications
      .filter(notif => {
        // Status filter
        if (statusFilter === "UNREAD" && notif.is_read) return false;
        if (statusFilter === "READ" && !notif.is_read) return false;

        // Type filter
        if (typeFilter !== "ALL") {
          const t = (notif.type || "").toLowerCase();
          if (!t.includes(typeFilter.toLowerCase())) return false;
        }

        // Priority filter
        if (priorityFilter !== "ALL") {
          const p = (notif.priority || "Medium").toLowerCase();
          if (p !== priorityFilter.toLowerCase()) return false;
        }

        // Search query
        if (searchQuery.trim()) {
          const q = searchQuery.toLowerCase();
          const matchTitle = (notif.title || "").toLowerCase().includes(q);
          const matchMsg = (notif.message || "").toLowerCase().includes(q);
          const matchType = (notif.type || "").toLowerCase().includes(q);
          const matchStatus = (notif.status || "").toLowerCase().includes(q);
          if (!matchTitle && !matchMsg && !matchType && !matchStatus) return false;
        }

        return true;
      })
      .sort((a, b) => {
        if (sortBy === "NEWEST") {
          return new Date(b.created_at || "").getTime() - new Date(a.created_at || "").getTime();
        }
        if (sortBy === "OLDEST") {
          return new Date(a.created_at || "").getTime() - new Date(b.created_at || "").getTime();
        }
        if (sortBy === "PRIORITY") {
          const priorityScore = (p?: string) => {
            const low = (p || "").toLowerCase();
            if (low === "high") return 3;
            if (low === "medium") return 2;
            return 1;
          };
          return priorityScore(b.priority) - priorityScore(a.priority);
        }
        return 0;
      });
  }, [notifications, statusFilter, typeFilter, priorityFilter, searchQuery, sortBy]);

  return (
    <div className="nc-page hs-page">

      {/* =====================================================
          1. TOP HEADER
      ===================================================== */}
      <header className="nc-header">
        <div className="nc-header-left">
          <div className="nc-title-row">
            <h1 className="nc-title">Notifications</h1>
            <div className={`nc-unread-pill ${unreadCount === 0 ? "all-read" : ""}`}>
              <span className="nc-unread-dot" />
              <span>{unreadCount > 0 ? `${unreadCount} unread` : "All caught up"}</span>
            </div>
          </div>
          <p className="nc-subtitle">
            Department alerts, task pipelines, approval queues, and AI-powered updates.
          </p>
        </div>

        <div className="nc-header-actions">
          <button
            onClick={handleRefresh}
            className={`nc-btn-refresh ${isRefreshing ? "spinning" : ""}`}
            title="Refresh notifications"
          >
            <RotateCw size={15} />
            <span>Refresh</span>
          </button>

          <button
            onClick={() => {
              markAllAsRead();
              showToast("All notifications marked as read");
            }}
            disabled={unreadCount === 0}
            className="nc-btn-mark-all"
          >
            <CheckCircle2 size={16} />
            <span>Mark all as read</span>
          </button>
        </div>
      </header>

      {/* =====================================================
          2. NOTIFICATION SUMMARY CARDS
      ===================================================== */}
      <section className="nc-summary-grid">
        <div
          onClick={() => {
            setStatusFilter("ALL");
            setTypeFilter("ALL");
          }}
          className={`nc-summary-card ${statusFilter === "ALL" && typeFilter === "ALL" ? "active" : ""}`}
        >
          <div className="nc-summary-icon all">
            <Bell size={18} />
          </div>
          <div className="nc-summary-text">
            <span>All Alerts</span>
            <strong>{totalCount}</strong>
          </div>
        </div>

        <div
          onClick={() => {
            setStatusFilter("UNREAD");
            setTypeFilter("ALL");
          }}
          className={`nc-summary-card ${statusFilter === "UNREAD" ? "active" : ""}`}
        >
          <div className="nc-summary-icon unread">
            <Mail size={18} />
          </div>
          <div className="nc-summary-text">
            <span>Unread</span>
            <strong>{unreadCount}</strong>
          </div>
        </div>

        <div
          onClick={() => {
            setTypeFilter("task");
            setStatusFilter("ALL");
          }}
          className={`nc-summary-card ${typeFilter === "task" ? "active" : ""}`}
        >
          <div className="nc-summary-icon tasks">
            <ClipboardList size={18} />
          </div>
          <div className="nc-summary-text">
            <span>Tasks</span>
            <strong>{tasksCount}</strong>
          </div>
        </div>

        <div
          onClick={() => {
            setTypeFilter("approval");
            setStatusFilter("ALL");
          }}
          className={`nc-summary-card ${typeFilter === "approval" ? "active" : ""}`}
        >
          <div className="nc-summary-icon approvals">
            <CheckCircle2 size={18} />
          </div>
          <div className="nc-summary-text">
            <span>Approvals</span>
            <strong>{approvalsCount}</strong>
          </div>
        </div>

        <div
          onClick={() => {
            setTypeFilter("ai");
            setStatusFilter("ALL");
          }}
          className={`nc-summary-card ${typeFilter === "ai" ? "active" : ""}`}
        >
          <div className="nc-summary-icon system">
            <BrainCircuit size={18} />
          </div>
          <div className="nc-summary-text">
            <span>AI & System</span>
            <strong>{systemCount}</strong>
          </div>
        </div>
      </section>

      {/* =====================================================
          3. AI NOTIFICATION ASSISTANT
      ===================================================== */}
      <section className="nc-ai-card">
        <div className="nc-ai-header">
          <div className="nc-ai-title-wrap">
            <div className="nc-ai-icon">
              <BrainCircuit size={19} />
            </div>
            <h3>HiéraSync AI Notification Assistant</h3>
          </div>
          <span className="nc-ai-badge">AI Active</span>
        </div>

        <p className="nc-ai-message">{aiSummary}</p>

        <div className="nc-ai-footer">
          <div className="nc-ai-insights">
            <span className="nc-ai-tag high">
              <ShieldAlert size={13} />
              <span>High Priority: {highPriorityCount}</span>
            </span>
            <span className="nc-ai-tag pending">
              <Clock size={13} />
              <span>Pending Approvals: {approvalsCount}</span>
            </span>
            <span className="nc-ai-tag deadlines">
              <ClipboardList size={13} />
              <span>Active Tasks: {tasksCount}</span>
            </span>
          </div>

          <button
            onClick={handleGenerateSummary}
            disabled={summaryLoading}
            className="nc-ai-btn"
          >
            <Sparkles size={14} />
            <span>{summaryLoading ? "Analyzing Streams..." : "Generate AI Insights"}</span>
          </button>
        </div>
      </section>

      {/* =====================================================
          4. TOOLBAR (SEARCH + FILTERS + SORTING)
      ===================================================== */}
      <section className="nc-toolbar">
        <div className="nc-toolbar-top">
          <div className="nc-search-box">
            <Search size={16} className="nc-search-icon" />
            <input
              type="text"
              placeholder="Search notifications by title, sender, department..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="nc-search-input"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery("")}
                className="nc-search-clear"
                title="Clear search"
              >
                <X size={14} />
              </button>
            )}
          </div>
        </div>

        <div className="nc-toolbar-bottom">
          <div className="nc-filter-group">
            {/* Status Segmented Control */}
            <div className="nc-segmented">
              <button
                onClick={() => setStatusFilter("ALL")}
                className={`nc-seg-btn ${statusFilter === "ALL" ? "active" : ""}`}
              >
                All ({totalCount})
              </button>
              <button
                onClick={() => setStatusFilter("UNREAD")}
                className={`nc-seg-btn ${statusFilter === "UNREAD" ? "active" : ""}`}
              >
                Unread ({unreadCount})
              </button>
              <button
                onClick={() => setStatusFilter("READ")}
                className={`nc-seg-btn ${statusFilter === "READ" ? "active" : ""}`}
              >
                Read ({totalCount - unreadCount})
              </button>
            </div>

            {/* Type Selector */}
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="nc-select"
            >
              <option value="ALL">All Categories</option>
              <option value="task">Tasks</option>
              <option value="approval">Approvals</option>
              <option value="faculty">Faculty & Staff</option>
              <option value="calendar">Calendar & Events</option>
              <option value="ai">AI Recommendations</option>
            </select>

            {/* Priority Selector */}
            <select
              value={priorityFilter}
              onChange={(e) => setPriorityFilter(e.target.value)}
              className="nc-select"
            >
              <option value="ALL">All Priorities</option>
              <option value="high">High Priority</option>
              <option value="medium">Medium Priority</option>
              <option value="low">Low Priority</option>
            </select>
          </div>

          <div className="flex items-center gap-3">
            <span className="nc-results-count">
              Showing {filteredNotifications.length} of {totalCount}
            </span>

            {/* Sort Selector */}
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as any)}
              className="nc-select"
            >
              <option value="NEWEST">Newest First</option>
              <option value="OLDEST">Oldest First</option>
              <option value="PRIORITY">Highest Priority</option>
            </select>
          </div>
        </div>
      </section>

      {/* Error Message */}
      {error && (
        <div className="nc-error-banner">
          <span>{error}</span>
          <button onClick={refreshNotifications} className="nc-error-btn">
            Retry
          </button>
        </div>
      )}

      {/* =====================================================
          5. NOTIFICATION LIST
      ===================================================== */}
      <section className="nc-list">
        {loading ? (
          <>
            <div className="nc-skeleton-card" />
            <div className="nc-skeleton-card" />
            <div className="nc-skeleton-card" />
            <div className="nc-skeleton-card" />
          </>
        ) : filteredNotifications.length === 0 ? (
          <div className="nc-empty-state">
            <div className="nc-empty-icon">
              <CheckCircle2 size={28} />
            </div>
            <h3>No notifications found</h3>
            <p>
              {searchQuery || typeFilter !== "ALL" || statusFilter !== "ALL" || priorityFilter !== "ALL"
                ? "No notifications match your current filter criteria."
                : "You're all caught up! There are no department alerts at this time."}
            </p>
            {(searchQuery || typeFilter !== "ALL" || statusFilter !== "ALL" || priorityFilter !== "ALL") && (
              <button
                onClick={() => {
                  setSearchQuery("");
                  setStatusFilter("ALL");
                  setTypeFilter("ALL");
                  setPriorityFilter("ALL");
                }}
                className="nc-btn-refresh"
              >
                Reset Filters
              </button>
            )}
          </div>
        ) : (
          filteredNotifications.map((notif) => {
            const typeClass = getTypeClass(notif.type);
            const isUnread = !notif.is_read;
            const priorityLower = (notif.priority || "Medium").toLowerCase();

            return (
              <div
                key={notif.id}
                onClick={() => handleNotificationClick(notif)}
                className={`nc-card ${isUnread ? "unread" : "read"} ${typeClass}`}
              >
                <div className="nc-card-main">
                  {/* Icon */}
                  <div className={`nc-card-icon ${typeClass}`}>
                    {renderNotificationIcon(notif.type, notif.icon)}
                  </div>

                  {/* Body */}
                  <div className="nc-card-body">
                    <div className="nc-card-headline">
                      <h2 className="nc-card-title">{notif.title}</h2>

                      <span className={`nc-type-badge ${notif.type?.toLowerCase() || "system"}`}>
                        {notif.type || "Alert"}
                      </span>

                      {notif.priority && (
                        <span className={`nc-priority-badge ${priorityLower}`}>
                          {notif.priority}
                        </span>
                      )}

                      {isUnread && (
                        <span className="w-2 h-2 rounded-full bg-[#E11D48]" title="Unread" />
                      )}
                    </div>

                    <p className="nc-card-message">{notif.message}</p>

                    <div className="nc-card-meta">
                      <span className="nc-card-meta-item">
                        <Clock size={12} />
                        <span>{notif.time || "Recent"}</span>
                      </span>

                      {notif.status && (
                        <>
                          <span>•</span>
                          <span>{notif.status}</span>
                        </>
                      )}
                    </div>
                  </div>
                </div>

                {/* Actions */}
                <div className="nc-card-actions">
                  {/* Direct Navigation Button */}
                  <button
                    onClick={(e) => handleDirectNavigate(e, notif)}
                    className="nc-navigate-btn"
                    title="Open related page"
                  >
                    <span>View</span>
                    <ArrowRight size={13} />
                  </button>

                  {/* Mark as read/unread toggle */}
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      if (notif.is_read) {
                        markAsUnread(notif.id);
                        showToast("Marked as unread");
                      } else {
                        markAsRead(notif.id);
                        showToast("Marked as read");
                      }
                    }}
                    className="nc-action-btn"
                    title={notif.is_read ? "Mark as unread" : "Mark as read"}
                  >
                    {notif.is_read ? <Mail size={15} /> : <MailCheck size={15} />}
                  </button>

                  {/* Delete / Dismiss Button */}
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      deleteNotification(notif.id);
                      showToast("Notification dismissed");
                    }}
                    className="nc-action-btn delete"
                    title="Dismiss notification"
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              </div>
            );
          })
        )}
      </section>

      {/* =====================================================
          6. NOTIFICATION DETAIL MODAL / DRAWER
      ===================================================== */}
      {selectedNotif && (
        <div className="nc-modal-backdrop" onClick={() => setSelectedNotif(null)}>
          <div className="nc-modal" onClick={(e) => e.stopPropagation()}>
            <div className="nc-modal-header">
              <div className="nc-modal-title-group">
                <div className={`nc-card-icon ${getTypeClass(selectedNotif.type)}`}>
                  {renderNotificationIcon(selectedNotif.type, selectedNotif.icon)}
                </div>
                <div>
                  <h3>{selectedNotif.title}</h3>
                  <div className="nc-modal-tags mt-1">
                    <span className={`nc-type-badge ${selectedNotif.type?.toLowerCase() || "system"}`}>
                      {selectedNotif.type || "Alert"}
                    </span>
                    {selectedNotif.priority && (
                      <span className={`nc-priority-badge ${(selectedNotif.priority || "Medium").toLowerCase()}`}>
                        {selectedNotif.priority} Priority
                      </span>
                    )}
                  </div>
                </div>
              </div>

              <button
                onClick={() => setSelectedNotif(null)}
                className="nc-modal-close"
              >
                <X size={18} />
              </button>
            </div>

            <div className="nc-modal-message">
              <p>{selectedNotif.message}</p>
            </div>

            <div className="flex items-center justify-between text-xs text-[#737373] px-1">
              <span>Received: {selectedNotif.time || "Recent"}</span>
              <span>Status: {selectedNotif.is_read ? "Read" : "Unread"}</span>
            </div>

            <div className="nc-modal-footer">
              <div className="nc-modal-footer-actions">
                <button
                  onClick={() => {
                    if (selectedNotif.is_read) {
                      markAsUnread(selectedNotif.id);
                      setSelectedNotif({ ...selectedNotif, is_read: false });
                      showToast("Marked as unread");
                    } else {
                      markAsRead(selectedNotif.id);
                      setSelectedNotif({ ...selectedNotif, is_read: true });
                      showToast("Marked as read");
                    }
                  }}
                  className="nc-btn-refresh"
                >
                  {selectedNotif.is_read ? <Mail size={14} /> : <MailCheck size={14} />}
                  <span>{selectedNotif.is_read ? "Mark Unread" : "Mark Read"}</span>
                </button>

                <button
                  onClick={() => {
                    deleteNotification(selectedNotif.id);
                    setSelectedNotif(null);
                    showToast("Notification dismissed");
                  }}
                  className="nc-action-btn delete"
                  title="Dismiss notification"
                >
                  <Trash2 size={15} />
                </button>
              </div>

              <button
                onClick={() => {
                  const route = getNotificationRoute(selectedNotif);
                  setSelectedNotif(null);
                  navigate(route);
                }}
                className="nc-modal-primary-btn"
              >
                <span>Go to Related Page</span>
                <ExternalLink size={14} />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* =====================================================
          7. ACTION FEEDBACK TOAST
      ===================================================== */}
      {toastMessage && (
        <div className="nc-toast">
          <CheckCircle2 size={16} className="nc-toast-icon" />
          <span>{toastMessage}</span>
        </div>
      )}

    </div>
  );
}