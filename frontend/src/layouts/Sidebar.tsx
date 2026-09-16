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
        name: "Calendar",
        path: "/calendar",
        icon: <FaCalendarAlt className="w-4 h-4" />,
        badge: null,
        roles: ["ADMIN", "HOD", "FACULTY"]
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

    menu = allMenu.filter(item => item.roles.includes(user.role));
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
    <aside className="sticky top-0 flex h-screen w-72 shrink-0 flex-col justify-between overflow-y-auto border-r border-[#262335] bg-[#17151F] p-5 font-label text-[#D4D4D8] shadow-2xl">
      <div>
        {/* Brand Header */}
        <div className="mb-7 flex items-center gap-3 border-b border-[#262335] pb-5">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-gradient-to-tr from-brand-plum to-[#9333EA] p-0.5 shadow-lg shadow-brand-plum/25">
            <div className="flex h-full w-full items-center justify-center rounded-[7px] bg-[#17151F]">
              <Sparkles className="h-5 w-5 text-[#C4B5FD]" />
            </div>
          </div>
          <div className="min-w-0">
            <h1 className="truncate font-display text-[17px] font-semibold tracking-wide text-white">
              HiéraSync <span className="text-[#A78BFA]">AI</span>
            </h1>
            <p className="hs-kicker mt-0.5 truncate text-[#8B87A3]">AIML Department Portal</p>
          </div>
        </div>

        {/* Menu Navigation */}
        <nav aria-label="Primary">
          <ul className="space-y-1">
            {menu.map((item) => (
              <li key={item.path}>
                <NavLink
                  to={item.path}
                  className={({ isActive }) =>
                    `flex items-center justify-between rounded-md px-3 py-2 text-sm font-medium transition-colors duration-150 ${
                      isActive
                        ? "bg-brand-plum font-semibold text-white shadow-md shadow-brand-plum/30"
                        : "text-[#A1A1AA] hover:bg-[#232030] hover:text-white"
                    }`
                  }
                >
                  <span className="flex min-w-0 items-center gap-3">
                    <span className="flex h-5 w-5 shrink-0 items-center justify-center">{item.icon}</span>
                    <span className="truncate">{item.name}</span>
                  </span>

                  {item.badge && (
                    <span className="ml-2 shrink-0 rounded-sm border border-[#38334E] bg-[#242033] px-1.5 py-px text-[11px] font-semibold text-[#C4B5FD]">
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
      <div className="mt-6 border-t border-[#262335] pt-4 text-xs text-[#71717A]">
        <p className="font-semibold text-[#A1A1AA]">SBJIT Nagpur • AIML</p>
        <p className="mt-0.5 text-[11px]">System v2.4 • Active Session</p>
      </div>
    </aside>
  );
}
