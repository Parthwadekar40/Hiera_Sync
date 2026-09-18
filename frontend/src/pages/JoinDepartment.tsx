import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { joinApi, JoinRequestResponse } from "../api/join";
import { departmentsApi, DepartmentResponse } from "../api/departments";
import { useAuth } from "../contexts/AuthContext";
import {
  Building2,
  Send,
  Clock,
  CheckCircle2,
  XCircle,
  ArrowRight,
  RotateCw,
  ShieldCheck,
  Sparkles,
} from "lucide-react";

import "./JoinDepartment.css";

export default function JoinDepartment() {
  const navigate = useNavigate();
  const { user, refreshUser } = useAuth();

  const [code, setCode] = useState("");
  const [status, setStatus] = useState<JoinRequestResponse | null>(null);
  const [department, setDepartment] = useState<DepartmentResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState("");

  const isUserActive = user?.status === "ACTIVE" && Boolean(user?.department_id);

  const fetchStatus = async () => {
    try {
      const [statusRes, deptRes] = await Promise.all([
        joinApi.getStatus(),
        departmentsApi.getMine().catch(() => null),
      ]);
      setStatus(statusRes);
      if (deptRes) {
        setDepartment(deptRes);
      }

      // If the backend has approved the request or user is active, sync user profile
      if (statusRes?.status === "Approved") {
        await refreshUser();
      }
    } catch (err: any) {
      console.error("Error fetching join status:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
  }, []);

  const handleManualCheck = async () => {
    setChecking(true);
    setError("");
    try {
      const [statusRes, freshUser] = await Promise.all([
        joinApi.getStatus(),
        refreshUser(),
      ]);
      setStatus(statusRes);
      if (statusRes?.status === "Approved" || freshUser?.status === "ACTIVE") {
        // Automatically navigate to dashboard when approved
        navigate("/dashboard");
        setTimeout(() => {
          if (window.location.pathname.includes("/join-department")) {
            window.location.href = "/dashboard";
          }
        }, 150);
      }
    } catch (err: any) {
      console.error("Check status error:", err);
    } finally {
      setTimeout(() => setChecking(false), 500);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!code.trim()) {
      setError("Please enter a valid invitation code.");
      return;
    }
    setError("");
    setSubmitting(true);
    try {
      const res = await joinApi.submitRequest({ code: code.trim() });
      setStatus(res);
      setCode("");
    } catch (err: any) {
      setError(err.message || "Failed to submit join request.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleOpenWorkspace = async () => {
    setSubmitting(true);
    setError("");
    try {
      // 1. Refresh user in AuthContext to guarantee ACTIVE status & assigned department_id
      await refreshUser();
      
      // 2. Perform navigation to /dashboard
      navigate("/dashboard");

      // 3. Fallback ensure navigation occurs cleanly
      setTimeout(() => {
        if (window.location.pathname.includes("/join-department")) {
          window.location.href = "/dashboard";
        }
      }, 150);
    } catch (err: any) {
      console.error("Error opening workspace:", err);
      window.location.href = "/dashboard";
    } finally {
      setTimeout(() => setSubmitting(false), 600);
    }
  };

  if (loading) {
    return (
      <div className="jd-page">
        <div className="jd-card text-center">
          <div className="w-8 h-8 border-3 border-[#6D28D9] border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-sm font-semibold text-[#737373]">Checking department authorization...</p>
        </div>
      </div>
    );
  }

  // Case 1: User is already an active member or request is approved
  if (isUserActive || status?.status === "Approved") {
    return (
      <div className="jd-page">
        <div className="jd-ambient-glow jd-glow-1" />
        <div className="jd-ambient-glow jd-glow-2" />

        <div className="jd-card">
          <div className="jd-icon-wrapper approved">
            <CheckCircle2 size={32} />
          </div>

          <h1 className="jd-title">
            {isUserActive ? "Department Membership Active" : "Join Request Approved!"}
          </h1>

          <p className="jd-subtitle">
            You are now an authorized faculty member with full access to the department workspace.
          </p>

          <div className="jd-status-box approved">
            <div className="jd-status-header">
              <span className="jd-status-tag">
                <CheckCircle2 size={18} />
                <span>Authorized Member</span>
              </span>
              <span className="px-2.5 py-1 rounded-full bg-[#D1FAE5] text-[#065F46] text-xs font-bold uppercase">
                Active
              </span>
            </div>

            <p className="jd-status-desc">
              Department: <strong>{department?.name || status?.department_name || "Computer Science & Engineering (AI & ML)"}</strong>
              <br />
              Institution: <strong>SBJIT Nagpur</strong>
            </p>

            <div className="jd-meta-details">
              <span>Department Code: <strong>{department?.code || status?.department_code || "AIML"}</strong></span>
              <span>•</span>
              <span>Access Level: <strong>Faculty Workspace</strong></span>
            </div>
          </div>

          {error && (
            <div className="jd-error-banner mb-4">
              <span>{error}</span>
            </div>
          )}

          <button
            onClick={handleOpenWorkspace}
            disabled={submitting}
            className="jd-btn-primary emerald"
          >
            {submitting ? (
              <>
                <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                <span>Opening Department Workspace...</span>
              </>
            ) : (
              <>
                <span>Open Department Workspace</span>
                <ArrowRight size={18} />
              </>
            )}
          </button>

          <div className="jd-footer-info">
            <ShieldCheck size={14} />
            <span>HiéraSync AI • SBJIT Nagpur • Secure Access</span>
          </div>
        </div>
      </div>
    );
  }

  // Case 2: Request is Pending
  if (status?.status === "Pending") {
    return (
      <div className="jd-page">
        <div className="jd-ambient-glow jd-glow-1" />
        <div className="jd-ambient-glow jd-glow-2" />

        <div className="jd-card">
          <div className="jd-icon-wrapper pending">
            <Clock size={32} />
          </div>

          <h1 className="jd-title">Request Pending Approval</h1>

          <p className="jd-subtitle">
            Your department join request has been submitted and is currently waiting for review by the Head of Department.
          </p>

          <div className="jd-status-box pending">
            <div className="jd-status-header">
              <span className="jd-status-tag">
                <Clock size={18} />
                <span>Under Review</span>
              </span>
              <span className="px-2.5 py-1 rounded-full bg-[#FEF3C7] text-[#92400E] text-xs font-bold uppercase">
                Pending
              </span>
            </div>

            <p className="jd-status-desc">
              You requested to join department code <strong>{status.department_code}</strong>
              {status.department_name && <> ({status.department_name})</>}.
            </p>

            <div className="jd-meta-details">
              <span>Submitted: {new Date(status.requested_at).toLocaleDateString()}</span>
              <span>•</span>
              <span>Reviewer: Department Administrator / HOD</span>
            </div>
          </div>

          <button
            onClick={handleManualCheck}
            disabled={checking}
            className={`jd-btn-secondary ${checking ? "spinning" : ""}`}
          >
            <RotateCw size={16} />
            <span>{checking ? "Checking Status..." : "Check Status / Refresh"}</span>
          </button>

          <div className="jd-footer-info">
            <Sparkles size={14} />
            <span>Administrator will be notified automatically upon submission</span>
          </div>
        </div>
      </div>
    );
  }

  // Case 3: Request Rejected or No Request (Show Invitation Form)
  return (
    <div className="jd-page">
      <div className="jd-ambient-glow jd-glow-1" />
      <div className="jd-ambient-glow jd-glow-2" />

      <div className="jd-card">
        <div className="jd-icon-wrapper">
          <Building2 size={32} />
        </div>

        <h1 className="jd-title">Join Department</h1>

        <p className="jd-subtitle">
          Enter the unique department invitation code provided by your Head of Department or Administrator. (Seeded demo codes: <span className="font-semibold">AIML</span> and <span className="font-semibold">IT</span> — codes for departments you create are generated as 8 random A–Z/0–9 characters.)
        </p>

        {status?.status === "Rejected" && (
          <div className="jd-status-box rejected">
            <div className="jd-status-header">
              <span className="jd-status-tag">
                <XCircle size={18} />
                <span>Request Not Approved</span>
              </span>
            </div>
            <p className="jd-status-desc">
              Your previous join request for code <strong>{status.department_code}</strong> was rejected. Please verify the code with your HOD and submit a new request below.
            </p>
          </div>
        )}

        {error && (
          <div className="jd-error-banner mb-4">
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="jd-form">
          <div>
            <label htmlFor="invitation-code" className="jd-input-label">
              Department Invitation Code
            </label>
            <input
              id="invitation-code"
              type="text"
              placeholder="e.g. 8FTEOOCV"
              value={code}
              onChange={(e) => setCode(e.target.value.toUpperCase())}
              maxLength={12}
              required
              className="jd-code-input"
            />
          </div>

          <button
            type="submit"
            disabled={submitting || !code.trim()}
            className="jd-btn-primary"
          >
            {submitting ? (
              <>
                <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                <span>Submitting Request...</span>
              </>
            ) : (
              <>
                <span>Submit Join Request</span>
                <Send size={18} />
              </>
            )}
          </button>
        </form>

        <div className="jd-footer-info">
          <ShieldCheck size={14} />
          <span>SBJIT Nagpur • Academic Governance Portal</span>
        </div>
      </div>
    </div>
  );
}
