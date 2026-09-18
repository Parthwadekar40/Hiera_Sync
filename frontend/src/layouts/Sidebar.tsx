import {
  FaHome,
  FaTasks,
  FaCalendarAlt,
  FaClipboardCheck,
  FaChartBar,
  FaRobot,
  FaUsers,
  FaCog,
  FaBell
} from "react-icons/fa";
import { NavLink } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { useNotifications } from "../contexts/NotificationContext";
import { Building2, Sparkles } from "lucide-react";

export default function Sidebar() {
  const { user } = useAuth();
  const { unreadCount } = useNotifications();

  let menu: any[] = [];
  
  if (user?.status === "ACTIVE") {
    const isHodOrAdmin = user.role === "ADMIN" || user.role === "HOD";
    
    const allMenu = [
      {
        name: "Dashboard",
        path: "/dashboard",
        icon: <FaHome className="w-4 h-4" />,
        badge: null,
        roles: ["ADMIN", "HOD", "FACULTY"]
      },
      {
        name: "AI Assistant",
        path: "/ai",
        icon: <FaRobot className="w-4 h-4" />,
        badge: "AI",
        roles: ["ADMIN", "HOD", "FACULTY"]
      },
      {
        name: "Employees",
        path: "/employees",
        icon: <FaUsers className="w-4 h-4" />,
        badge: null,
        roles: ["ADMIN", "HOD"]
      },
      {
        name: isHodOrAdmin ? "Tasks" : "My Tasks",
        path: "/tasks",
        icon: <FaTasks className="w-4 h-4" />,
        badge: null,
        roles: ["ADMIN", "HOD", "FACULTY"]
      },
      {
        name: isHodOrAdmin ? "Incoming Requests" : "Request Task",
        path: "/task-requests",
        icon: <FaTasks className="w-4 h-4" />,
        badge: null,
        roles: ["ADMIN", "HOD", "FACULTY"]
      },
      {
        name: "Goals",
        path: "/goals",
        icon: <FaChartBar className="w-4 h-4" />,
        badge: null,
        roles: ["ADMIN", "HOD", "FACULTY"]
      },
      {
        name: "Notifications",
        path: "/notifications",
        icon: <FaBell className="w-4 h-4" />,
        badge: unreadCount > 0 ? `${unreadCount}` : null,
        roles: ["ADMIN", "HOD", "FACULTY"]
      },
      {
        name: "Risk Center",
        path: "/risk",
        icon: <FaChartBar className="w-4 h-4" />,
        badge: "AI",
        roles: ["ADMIN", "HOD", "FACULTY"]
      },
      {
        name: "Automation",
        path: "/automation",
        icon: <FaCog className="w-4 h-4" />,
        badge: null,
        roles: ["ADMIN", "HOD", "FACULTY"]
      },
      {
        name: "Calendar",
        path: "/calendar",
        icon: <FaCalendarAlt className="w-4 h-4" />,
        badge: null,
        roles: ["ADMIN", "HOD", "FACULTY", "STUDENT", "STUDENT_REP"]
      },
      {
        name: "Approvals",
        path: "/approvals",
        icon: <FaClipboardCheck className="w-4 h-4" />,
        badge: null,
        roles: ["ADMIN", "HOD"]
      },
      {
        name: "Reports",
        path: "/reports",
        icon: <FaChartBar className="w-4 h-4" />,
        badge: null,
        roles: ["ADMIN", "HOD"]
      },
      {
        name: "Settings",
        path: "/settings",
        icon: <FaCog className="w-4 h-4" />,
        badge: null,
        roles: ["ADMIN", "HOD", "FACULTY"]
      }
    ];

    // Slide 13 lists 10 roles; the v1 menu literals only name three of them.
    // Expand each listed role to its institutional class so every role lands in the right subset.
    const ROLE_CLASS: Record<string, string[]> = {
      ADMIN: ["ADMIN", "PRINCIPAL", "HOD"],
      HOD: ["PRINCIPAL", "HOD"],
      FACULTY: ["FACULTY", "TEACHER", "TA", "LAB_ASSISTANT", "STAFF"],
      STUDENT: ["STUDENT", "STUDENT_REP"],
    };
    const audience = (listed: string[]) => new Set(listed.flatMap((r) => ROLE_CLASS[r] ?? [r]));
    menu = allMenu.filter((item: any) => audience(item.roles).has(user.role as string));
  } else {
    // Pending users can only see Join/Create Dept
    if (user?.role === "ADMIN" || user?.role === "HOD") {
      menu.push({
        name: "Create Dept",
        path: "/create-department",
        icon: <Building2 className="w-4 h-4" />,
        badge: "New"
      });
    } else {
      menu.push({
        name: "Join Dept",
        path: "/join-department",
        icon: <Building2 className="w-4 h-4" />,
        badge: "New"
      });
    }
  }

  return (
    <aside className="w-72 min-h-screen bg-[#17151F] text-[#D4D4D8] p-6 flex flex-col justify-between shadow-2xl border-r border-[#262335] shrink-0 font-sans">
      <div>
        {/* Brand Header */}
        <div className="flex items-center gap-3.5 mb-8 pb-6 border-b border-[#262335]">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-[#6D28D9] to-[#9333EA] p-0.5 shadow-lg shadow-[#6D28D9]/25">
            <div className="w-full h-full bg-[#17151F] rounded-[10px] flex items-center justify-center">
              <Sparkles className="w-5 h-5 text-[#C4B5FD]" />
            </div>
          </div>
          <div>
            <h1 className="text-lg font-bold text-white tracking-wider">
              HIÉRASYNC <span className="text-[#A78BFA] font-black">AI</span>
            </h1>
            <p className="text-[11px] text-[#A1A1AA] font-medium tracking-wide">AIML Department Portal</p>
          </div>
        </div>

        {/* Menu Navigation */}
        <nav>
          <ul className="space-y-1">
            {menu.map((item, index) => (
              <li key={index}>
                <NavLink
                  to={item.path}
                  className={({ isActive }) =>
                    `flex items-center justify-between px-3.5 py-2.5 rounded-xl font-medium text-sm transition-all duration-200 ${
                      isActive
                        ? "bg-[#6D28D9] text-white shadow-md shadow-[#6D28D9]/30 font-semibold"
                        : "text-[#A1A1AA] hover:bg-[#232030] hover:text-white"
                    }`
                  }
                >
                  <div className="flex items-center gap-3">
                    <span className="w-5 h-5 flex items-center justify-center shrink-0">{item.icon}</span>
                    <span>{item.name}</span>
                  </div>

                  {item.badge && (
                    <span className="text-xs font-semibold px-2 py-0.5 rounded-md bg-[#242033] text-[#C4B5FD] border border-[#38334E]">
                      {item.badge}
                    </span>
                  )}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
      </div>

      {/* Footer Info */}
      <div className="pt-5 border-t border-[#262335] text-xs text-[#71717A]">
        <p className="font-semibold text-[#A1A1AA]">SBJIT Nagpur • AIML</p>
        <p className="mt-0.5 text-[11px]">System v2.4 • Active Session</p>
      </div>
    </aside>
  );
}