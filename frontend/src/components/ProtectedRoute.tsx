import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

export const ProtectedRoute = ({ allowedRoles }: { allowedRoles?: string[] }) => {
  const { isAuthenticated, loading, user } = useAuth();
  const location = useLocation();

  if (loading || (!user && isAuthenticated)) {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-slate-900">
        <div className="text-white text-lg flex items-center gap-3">
          <div className="w-6 h-6 border-2 border-t-indigo-500 border-r-transparent border-b-indigo-500 border-l-transparent rounded-full animate-spin"></div>
          Authenticating Hiera Sync...
        </div>
      </div>
    );
  }

  if (!isAuthenticated || !user) {
    return <Navigate to="/login" replace />;
  }

  if (user.status === "PENDING") {
    // A pending account may only see the pages that can get it activated:
    // /join-department (submit a code) and /create-department - without the latter,
    // a fresh database can never be started, because approving a request needs an
    // active HOD and there is none yet.
    const bootstrapPages = ['/join-department', '/create-department'];
    if (!bootstrapPages.includes(location.pathname)) {
       return <Navigate to="/join-department" replace />;
    }
  } else if (user.status !== "ACTIVE") {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-slate-100">
        <div className="text-rose-600 bg-white p-8 rounded-xl shadow-xl text-center">
          <h2 className="text-2xl font-bold mb-2">Access Restricted</h2>
          <p>Your account is inactive. Please contact your department admin.</p>
        </div>
      </div>
    );
  }

  if (allowedRoles && !allowedRoles.includes(user.role)) {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-slate-100">
        <div className="text-rose-600 bg-white p-8 rounded-xl shadow-xl text-center">
          <h2 className="text-2xl font-bold mb-2">Unauthorized</h2>
          <p>You do not have the required role to view this page.</p>
        </div>
      </div>
    );
  }

  return <Outlet />;
};
