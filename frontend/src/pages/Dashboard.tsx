import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { reportsApi, aiApi } from "../api";
import {
  DashboardStatsResponse,
  ActivityLogResponse,
  AIDashboardSummaryResponse,
} from "../types";
import { useAuth } from "../contexts/AuthContext";

import {
  Users,
  CheckSquare,
  ClipboardCheck,
  Sparkles,
  TrendingUp,
  Plus,
  ArrowUpRight,
  Activity,
  Clock3,
  UserCheck,
  ShieldCheck,
  Building2,
  ChevronRight,
  BrainCircuit,
  Zap,
  CheckCircle2,
  CalendarDays,
  FileCheck2,
  CircleDot,
  BarChart3,
} from "lucide-react";

import "./Dashboard.css";

export default function Dashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [stats, setStats] =
    useState<DashboardStatsResponse | null>(null);

  const [activities, setActivities] =
    useState<ActivityLogResponse[]>([]);

  const [aiInsights, setAiInsights] =
    useState<AIDashboardSummaryResponse | null>(null);

  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [statsData, actData, aiData] =
          await Promise.allSettled([
            reportsApi.getDashboardStats(),
            reportsApi.getRecentActivities(),
            aiApi.getDashboardSummary(),
          ]);

        if (statsData.status === "fulfilled") {
          setStats(statsData.value);
        }

        if (actData.status === "fulfilled") {
          setActivities(actData.value || []);
        }

        if (aiData.status === "fulfilled") {
          setAiInsights(aiData.value);
        }
      } catch (error) {
        console.error("Dashboard data error:", error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="dashboard-loading">
        <div className="dashboard-loader" />
        <span>Loading department dashboard...</span>
      </div>
    );
  }

  const displayActivities =
    activities.length > 0
      ? activities
      : [
          {
            id: "act-1",
            message:
              "New task assigned: NPTEL registration review",
            category: "task",
            timestamp: "10 mins ago",
          },
          {
            id: "act-2",
            message:
              "Faculty approval request is waiting for review",
            category: "approval",
            timestamp: "1 hour ago",
          },
          {
            id: "act-3",
            message:
              "Department calendar was updated successfully",
            category: "calendar",
            timestamp: "3 hours ago",
          },
          {
            id: "act-4",
            message:
              "Academic resource moderation completed",
            category: "resource",
            timestamp: "5 hours ago",
          },
        ];

  const facultyCount = stats?.employees_count ?? 4;
  const pendingTasks = stats?.pending_tasks_count ?? 2;
  const pendingApprovals = stats?.approvals_count ?? 9;
  const automationScore = stats?.ai_productivity || "92%";

  const firstInsight =
    aiInsights?.insights?.[0] ||
    "2 Tasks may miss deadline. AI recommends reviewing project approvals first.";

  return (
    <div className="admin-dashboard hs-page">

      {/* =====================================================
          HERO (BRIGHT, GLOSSY, SOPHISTICATED NEUTRAL/PLUM)
      ===================================================== */}

      <section className="dashboard-hero">

        <div className="hero-glow hero-glow-one" />
        <div className="hero-glow hero-glow-two" />

        <div className="hero-content">

          <div className="hero-eyebrow">
            <Sparkles size={14} />
            <span>
              AIML Department • SBJIT Nagpur
            </span>
          </div>

          <h1>
            Welcome back,{" "}
            <strong>
              {user?.name || "Admin User"}
            </strong>
          </h1>

          <p>
            Manage department operations, monitor tasks,
            review approvals, and keep your academic
            workflow moving smoothly.
          </p>

          <div className="hero-actions">

            <button
              className="primary-action"
              onClick={() => navigate("/tasks")}
            >
              <Plus size={16} />
              Create New Task
            </button>

            <button
              className="secondary-action"
              onClick={() => navigate("/approvals")}
            >
              <FileCheck2 size={16} />
              Review Approvals
              <ArrowUpRight size={14} />
            </button>

            <button
              className="secondary-action calendar-action"
              onClick={() => navigate("/calendar")}
            >
              <CalendarDays size={16} />
              Calendar
            </button>

          </div>
        </div>

        <div className="hero-status">

          <div className="hero-status-icon">
            <ShieldCheck size={22} />
          </div>

          <div className="hero-status-text">
            <span>DEPARTMENT STATUS</span>
            <strong>Operational</strong>
            <small>
              All core workflows are active
            </small>
          </div>

          <div className="status-dot" />
        </div>

      </section>


      {/* =====================================================
          KPI CARDS (CLICKABLE, REFINED MULTI-ACCENTS)
      ===================================================== */}

      <section className="kpi-grid">

        {/* Card 1: Faculty/Staff -> Employees */}
        <div
          className="kpi-card kpi-plum"
          onClick={() => navigate("/employees")}
          role="button"
          tabIndex={0}
          title="View Faculty Directory"
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              navigate("/employees");
            }
          }}
        >

          <div className="kpi-top">
            <div>
              <span>Total Faculty / Staff</span>
              <strong>{facultyCount}</strong>
            </div>

            <div className="kpi-icon">
              <Users size={20} />
            </div>
          </div>

          <div className="kpi-bottom">
            <span className="kpi-positive">
              <CircleDot size={10} />
              Active department
            </span>

            <span className="kpi-label">
              Faculty →
            </span>
          </div>

        </div>


        {/* Card 2: Pending Tasks -> Tasks */}
        <div
          className="kpi-card kpi-amber"
          onClick={() => navigate("/tasks")}
          role="button"
          tabIndex={0}
          title="View Pending Tasks"
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              navigate("/tasks");
            }
          }}
        >

          <div className="kpi-top">
            <div>
              <span>Pending Tasks</span>
              <strong>{pendingTasks}</strong>
            </div>

            <div className="kpi-icon">
              <CheckSquare size={20} />
            </div>
          </div>

          <div className="kpi-bottom">
            <span className="kpi-warning">
              <CircleDot size={10} />
              Requires action
            </span>

            <span className="kpi-label">
              Tasks →
            </span>
          </div>

        </div>


        {/* Card 3: Pending Approvals -> Approvals */}
        <div
          className="kpi-card kpi-rose"
          onClick={() => navigate("/approvals")}
          role="button"
          tabIndex={0}
          title="View Pending Approvals"
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              navigate("/approvals");
            }
          }}
        >

          <div className="kpi-top">
            <div>
              <span>Pending Approvals</span>
              <strong>{pendingApprovals}</strong>
            </div>

            <div className="kpi-icon">
              <ClipboardCheck size={20} />
            </div>
          </div>

          <div className="kpi-bottom">
            <span className="kpi-danger">
              <CircleDot size={10} />
              In review pipeline
            </span>

            <span className="kpi-label">
              Reviews →
            </span>
          </div>

        </div>


        {/* Card 4: AI Automation Score -> Reports */}
        <div
          className="kpi-card kpi-emerald"
          onClick={() => navigate("/reports")}
          role="button"
          tabIndex={0}
          title="View Performance Reports"
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              navigate("/reports");
            }
          }}
        >

          <div className="kpi-top">
            <div>
              <span>AI Automation Score</span>
              <strong>{automationScore}</strong>
            </div>

            <div className="kpi-icon">
              <TrendingUp size={20} />
            </div>
          </div>

          <div className="kpi-bottom">
            <span className="kpi-positive">
              <TrendingUp size={12} />
              +14% efficiency
            </span>

            <span className="kpi-label">
              Analytics →
            </span>
          </div>

        </div>

      </section>


      {/* =====================================================
          MAIN CONTENT (ACTIVITY & REVIEWS)
      ===================================================== */}

      <section className="dashboard-main-grid">

        {/* =================================================
            RECENT DEPARTMENT ACTIVITY
        ================================================= */}

        <div className="dashboard-panel activity-panel">

          <div className="panel-header">

            <div className="panel-title">

              <div className="panel-icon plum">
                <Activity size={18} />
              </div>

              <div>
                <h2>
                  Recent Department Activity
                </h2>

                <p>
                  Latest operational updates
                </p>
              </div>

            </div>

            <button
              className="text-link"
              onClick={() =>
                navigate("/notifications")
              }
            >
              View All
              <ArrowUpRight size={14} />
            </button>

          </div>


          <div className="activity-list">

            {displayActivities
              .slice(0, 4)
              .map((activity, index) => (

                <div
                  className="activity-row"
                  key={activity.id || index}
                  onClick={() => navigate("/notifications")}
                  role="button"
                  tabIndex={0}
                >

                  <div className="activity-number">
                    {index + 1}
                  </div>

                  <div className="activity-content">

                    <strong>
                      {activity.message}
                    </strong>

                    <div className="activity-meta">

                      <span
                        className={`activity-tag ${
                          activity.category || "general"
                        }`}
                      >
                        {activity.category ||
                          "General"}
                      </span>

                      <span>
                        <Clock3 size={11} />
                        {activity.timestamp ||
                          "Just now"}
                      </span>

                    </div>

                  </div>

                  <ChevronRight
                    size={16}
                    className="activity-arrow"
                  />

                </div>

              ))}

          </div>


          <button
            className="panel-bottom-button"
            onClick={() =>
              navigate("/notifications")
            }
          >
            Open full activity log
            <ChevronRight size={15} />
          </button>

        </div>


        {/* =================================================
            PENDING REVIEW
        ================================================= */}

        <div className="dashboard-panel review-panel">

          <div className="panel-header">

            <div className="panel-title">

              <div className="panel-icon amber">
                <ClipboardCheck size={18} />
              </div>

              <div>
                <h2>
                  Pending Review
                </h2>

                <p>
                  Items that need your attention
                </p>
              </div>

            </div>

            <button
              className="text-link"
              onClick={() =>
                navigate("/approvals")
              }
            >
              View Queue
              <ArrowUpRight size={14} />
            </button>

          </div>


          <div className="review-stack">

            <div
              className="review-item"
              onClick={() => navigate("/approvals")}
              role="button"
              tabIndex={0}
            >

              <div className="review-item-icon rose">
                <ClipboardCheck size={18} />
              </div>

              <div>
                <span>
                  Approval Requests
                </span>

                <strong>
                  {pendingApprovals}
                </strong>
              </div>

              <span className="review-badge danger">
                NEEDS REVIEW
              </span>

            </div>


            <div
              className="review-item"
              onClick={() => navigate("/tasks")}
              role="button"
              tabIndex={0}
            >

              <div className="review-item-icon amber">
                <CheckSquare size={18} />
              </div>

              <div>
                <span>
                  Task Queue
                </span>

                <strong>
                  {pendingTasks}
                </strong>
              </div>

              <span className="review-badge amber">
                ACTION
              </span>

            </div>


            <div className="review-status">

              <div className="review-status-icon">
                <CheckCircle2 size={17} />
              </div>

              <div>
                <strong>
                  Department workflow is operational
                </strong>

                <span>
                  Continue monitoring tasks and
                  approval requests.
                </span>
              </div>

            </div>

          </div>

        </div>

      </section>


      {/* =====================================================
          LOWER SECTION (DEPARTMENT, AI INSIGHT, ADMIN PROFILE)
      ===================================================== */}

      <section className="lower-grid">

        {/* DEPARTMENT OVERVIEW */}

        <div className="dashboard-panel department-panel">

          <div className="panel-header">

            <div className="panel-title">

              <div className="panel-icon plum">
                <Building2 size={18} />
              </div>

              <div>
                <h2>
                  Department Overview
                </h2>

                <p>
                  CSE (AI & ML)
                </p>
              </div>

            </div>

            <span className="verified-pill">
              <ShieldCheck size={13} />
              Verified
            </span>

          </div>


          <div className="department-details">

            <div
              className="department-stat"
              onClick={() => navigate("/employees")}
              role="button"
              tabIndex={0}
            >

              <div>
                <span>
                  Faculty / Staff
                </span>

                <strong>
                  {facultyCount}
                </strong>
              </div>

              <div className="mini-icon">
                <Users size={16} />
              </div>

            </div>


            <div
              className="department-stat"
              onClick={() => navigate("/tasks")}
              role="button"
              tabIndex={0}
            >

              <div>
                <span>
                  Pending Tasks
                </span>

                <strong>
                  {pendingTasks}
                </strong>
              </div>

              <div className="mini-icon amber-bg">
                <CheckSquare size={16} />
              </div>

            </div>


            <div
              className="department-stat"
              onClick={() => navigate("/approvals")}
              role="button"
              tabIndex={0}
            >

              <div>
                <span>
                  Approval Queue
                </span>

                <strong>
                  {pendingApprovals}
                </strong>
              </div>

              <div className="mini-icon rose-bg">
                <ClipboardCheck size={16} />
              </div>

            </div>

          </div>


          <button
            className="wide-outline-button"
            onClick={() =>
              navigate("/employees")
            }
          >
            Open Faculty Directory
            <ArrowUpRight size={14} />
          </button>

        </div>


        {/* AI INSIGHT / SMART ASSISTANT */}

        <div className="dashboard-panel ai-panel">

          <div className="ai-panel-top">

            <div className="ai-symbol">
              <BrainCircuit size={20} />
            </div>

            <div>

              <span>
                SMART ASSISTANT
              </span>

              <h2>
                Department Insight
              </h2>

            </div>

            <span className="ai-active">
              ACTIVE
            </span>

          </div>


          <div className="ai-message">

            <div className="ai-message-icon">
              <Zap size={15} />
            </div>

            <p>
              {firstInsight}
            </p>

          </div>


          <div className="workflow-progress">

            <div className="progress-heading">

              <span>
                Workflow efficiency
              </span>

              <strong>
                88%
              </strong>

            </div>

            <div className="progress-track">
              <div
                className="progress-value"
                style={{ width: "88%" }}
              />
            </div>

          </div>


          <div className="ai-actions">

            <button
              onClick={() =>
                navigate("/reports")
              }
            >
              <BarChart3 size={14} />
              View Department Reports
              <ArrowUpRight size={13} />
            </button>

            <button
              onClick={() =>
                navigate("/calendar")
              }
            >
              <CalendarDays size={14} />
              Open Academic Calendar
              <ArrowUpRight size={13} />
            </button>

          </div>

        </div>


        {/* ADMIN USER PROFILE */}

        <div className="dashboard-panel profile-panel">

          <div className="profile-top">

            <div className="profile-avatar">

              {user?.name
                ? user.name
                    .substring(0, 2)
                    .toUpperCase()
                : "AD"}

            </div>

            <div className="profile-online">
              <span />
              Online
            </div>

          </div>


          <h2>
            {user?.name || "Admin User"}
          </h2>

          <p className="profile-email">
            {user?.email ||
              "admin@campuspulse.com"}
          </p>


          <div className="profile-tags">

            <span className="admin-tag">
              {user?.role || "ADMIN"}
            </span>

            <span className="dept-tag">
              AIML DEPARTMENT
            </span>

          </div>


          <div className="profile-divider" />


          <div className="profile-info">

            <div>
              <span>
                <ShieldCheck size={13} />
                Account Status
              </span>

              <strong className="verified-text">
                Verified
              </strong>
            </div>

            <div>
              <span>
                <UserCheck size={13} />
                Access Level
              </span>

              <strong>
                Administrator
              </strong>
            </div>

          </div>


          <button
            className="profile-button"
            onClick={() =>
              navigate("/employees")
            }
          >
            Faculty Directory
            <ArrowUpRight size={14} />
          </button>

        </div>

      </section>


      {/* =====================================================
          FOOTER SYSTEM STATUS
      ===================================================== */}

      <div className="dashboard-footer">

        <div className="footer-status">

          <span className="footer-dot" />

          <div>
            <strong>
              Department systems operational
            </strong>

            <span>
              {facultyCount} faculty/staff •{" "}
              {pendingTasks} pending tasks •{" "}
              {pendingApprovals} pending approvals
            </span>
          </div>

        </div>


        <div className="footer-actions">

          <button
            onClick={() =>
              navigate("/calendar")
            }
          >
            <CalendarDays size={14} />
            Calendar
          </button>

          <button
            className="footer-primary"
            onClick={() =>
              navigate("/reports")
            }
          >
            Reports
            <ArrowUpRight size={13} />
          </button>

        </div>

      </div>

    </div>
  );
}