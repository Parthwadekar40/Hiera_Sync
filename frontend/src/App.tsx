import {
  BrowserRouter,
  Routes,
  Route,
  Link,
} from "react-router-dom";

import { lazy, Suspense } from "react";

import MainLayout from "./layouts/MainLayout";
import { AuthProvider } from "./contexts/AuthContext";
import { NotificationProvider } from "./contexts/NotificationContext";
import { ProtectedRoute } from "./components/ProtectedRoute";
import Chatbot from "./components/Chatbot";

import {
  ArrowRight,
  GraduationCap,
} from "lucide-react";

import "./App.css";


/* =====================================================
   EXISTING PAGES — PRESERVED EXACTLY
===================================================== */

const Notifications = lazy(
  () => import("./pages/Notifications")
);

const Dashboard = lazy(
  () => import("./pages/Dashboard")
);

const Employees = lazy(
  () => import("./pages/Employees")
);

const Tasks = lazy(
  () => import("./pages/Tasks")
);

const CalendarPage = lazy(
  () => import("./pages/CalendarPage")
);

const Goals = lazy(() => import('./pages/Goals'));
const TaskRequests = lazy(() => import('./pages/TaskRequests'));
const Approvals = lazy(
  () => import("./pages/Approvals")
);

const Reports = lazy(
  () => import("./pages/Reports")
);

const Settings = lazy(
  () => import("./pages/Settings")
);

const Login = lazy(
  () => import("./pages/Auth/Login")
);

const Register = lazy(
  () => import("./pages/Auth/Register")
);

const JoinDepartment = lazy(
  () => import("./pages/JoinDepartment")
);

const CreateDepartment = lazy(
  () => import("./pages/CreateDepartment")
);

const AIAssistantPage = lazy(
  () => import("./pages/AIAssistantPage")
);

const RiskCenter = lazy(
  () => import("./pages/RiskCenter")
);

const AutomationCenter = lazy(
  () => import("./pages/AutomationCenter")
);

const ApprovalDesk = lazy(
  () => import("./pages/ApprovalDesk")
);

const Analytics = lazy(
  () => import("./pages/Analytics")
);



/* =====================================================
   LANDING PAGE — PREMIUM REDESIGN
===================================================== */

function LandingPage() {
  return (
    <div className="hs-landing">

      {/* AMBIENT BACKGROUND GLOWS */}
      <div className="hs-ambient-glow hs-glow-1" />
      <div className="hs-ambient-glow hs-glow-2" />
      <div className="hs-ambient-glow hs-glow-3" />

      {/* HEADER */}
      <header className="hs-header">
        <div className="hs-header-inner">

          <Link to="/" className="hs-logo-area">
            <div className="hs-logo">
              <GraduationCap size={25} />
            </div>

            <div>
              <div className="hs-brand">
                HiéraSync <span className="hs-brand-ai">AI</span>
              </div>
              <div className="hs-brand-college">
                SBJIT NAGPUR
              </div>
            </div>
          </Link>

          <Link to="/login" className="hs-signin">
            <span>Sign In</span>
            <ArrowRight size={16} />
          </Link>

        </div>
      </header>


      {/* MAIN HERO SECTION */}
      <main className="hs-main">

        {/* LEFT CONTENT */}
        <section className="hs-content">

          <div className="hs-college-pill">
            <span className="hs-college-badge">INSTITUTION</span>
            <div className="hs-college-text">
              <span>SB JAIN INSTITUTE OF TECHNOLOGY, MANAGEMENT & RESEARCH</span>
              <strong>NAGPUR</strong>
            </div>
          </div>

          <h1 className="hs-title">
            HiéraSync <span className="hs-title-ai">AI</span>
          </h1>

          <h2 className="hs-department">
            CSE (AI & ML) Department
          </h2>

          <p className="hs-description">
            Smart academic workflow management for a connected and efficient department.
          </p>

          <div className="hs-cta-group">
            <Link to="/login" className="hs-enter">
              <span>Enter HieraSync</span>
              <ArrowRight size={20} />
            </Link>

            <div className="hs-trust-badge">
              <span className="hs-trust-dot" />
              <span>Academic Workspace v2.4</span>
            </div>
          </div>

        </section>


        {/* RIGHT COMPOSITION (LAYERED CAMPUS VISUAL) */}
        <section className="hs-photo-section">
          <div className="hs-composition-wrapper">

            {/* Background layered accent card for depth */}
            <div className="hs-composition-card-back" />

            {/* Main Campus Image Container */}
            <div className="hs-photo">
              <img
                src="/sbjit-campus.jpg"
                alt="SB Jain Institute of Technology, Management & Research, Nagpur"
              />
              <div className="hs-photo-overlay" />

              {/* Integrated Glass Badge */}
              <div className="hs-photo-bottom">
                <div className="hs-photo-badge-icon">
                  <GraduationCap size={16} />
                </div>
                <div>
                  <strong>SBJIT Nagpur</strong>
                  <span>CSE (AI & ML) Campus Portal</span>
                </div>
              </div>
            </div>

          </div>
        </section>

      </main>


      {/* FOOTER */}
      <footer className="hs-footer">
        <div className="hs-footer-inner">
          <div className="hs-footer-left">
            <strong>HiéraSync AI</strong>
            <span>•</span>
            <span>Academic Workflow Management</span>
          </div>

          <div className="hs-footer-center">
            <span>CSE (AI & ML)</span>
            <span>•</span>
            <span>SBJIT Nagpur</span>
          </div>

          <div className="hs-footer-right">
            <span>© 2026 HiéraSync AI</span>
          </div>
        </div>
      </footer>

    </div>
  );
}


/* =====================================================
   APP ROUTER — PRESERVED EXACTLY
===================================================== */

function App() {
  return (
    <AuthProvider>
      <NotificationProvider>
        <BrowserRouter>
          <Suspense
            fallback={
              <div className="app-loading">
                <div className="loading-spinner"></div>
                <p>Loading HieraSync...</p>
              </div>
            }
          >
            <Routes>
              {/* LANDING PAGE */}
              <Route
                path="/"
                element={<LandingPage />}
              />

              {/* LOGIN */}
              <Route
                path="/login"
                element={<Login />}
              />

              {/* REGISTER */}
              <Route
                path="/register"
                element={<Register />}
              />

              {/* ALL INTERNAL PAGES */}
              <Route element={<ProtectedRoute />}>
                <Route element={<MainLayout />}>
                  <Route
                    path="/dashboard"
                    element={<Dashboard />}
                  />

                  <Route
                    path="/ai"
                    element={<AIAssistantPage />}
                  />


                  <Route
                    path="/employees"
                    element={<Employees />}
                  />

                  <Route
                    path="/tasks"
                    element={<Tasks />}
                  />

                  <Route
                    path="/calendar"
                    element={<CalendarPage />}
                  />

                  <Route path="/goals" element={<Goals />} />
                  <Route path="/task-requests" element={<TaskRequests />} />
                  <Route
                    path="/approvals"
                    element={<Approvals />}
                  />

                  <Route
                    path="/reports"
                    element={<Reports />}
                  />

                  <Route
                    path="/settings"
                    element={<Settings />}
                  />

                  <Route
                    path="/notifications"
                    element={<Notifications />}
                  />

                  <Route
                    path="/risk"
                    element={<RiskCenter />}
                  />

                  <Route
                    path="/automation"
                    element={<AutomationCenter />}
                  />

                  <Route
                    path="/approvals/desk"
                    element={<ApprovalDesk />}
                  />

                  <Route
                    path="/analytics"
                    element={<Analytics />}
                  />

                  <Route
                    path="/join-department"
                    element={<JoinDepartment />}
                  />

                  <Route
                    path="/create-department"
                    element={<CreateDepartment />}
                  />
                </Route>
              </Route>
            </Routes>

            <Chatbot />
          </Suspense>
        </BrowserRouter>
      </NotificationProvider>
    </AuthProvider>
  );
}

export default App;