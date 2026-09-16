import { useState, useEffect } from "react";
import { tasksApi, employeesApi, aiApi } from "../../api";
import { TaskResponse, EmployeeResponse, TaskCreate, HODActionItem, FacultyPerformance } from "../../types";
import { CheckCircle, Clock, AlertCircle, PlayCircle, Plus, Search, Calendar as CalendarIcon, AlignJustify, GitCommit, ChevronRight, Activity, Users, FileText } from "lucide-react";
import TaskDetailsModal from "./TaskDetailsModal";
import { TaskCalendarView, TaskTimelineView } from "./TaskViews";
import { analyticsApi } from "../../api/analytics";

export default function HODDashboard() {
  const [tasks, setTasks] = useState<TaskResponse[]>([]);
  const [facultyList, setFacultyList] = useState<EmployeeResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [hodActions, setHodActions] = useState<HODActionItem[]>([]);
  const [facultyPerformance, setFacultyPerformance] = useState<FacultyPerformance[]>([]);
  const [showForm, setShowForm] = useState(false);
  
  const [taskForm, setTaskForm] = useState<TaskCreate>({
    title: "", description: "", category: "General", assigned: "", assigned_id: "",
    start_date: "", deadline: "", deadline_time: "", priority: "High",
    estimated_effort: "", reminder: "1 day before", require_approval: false,
    status: "Pending", progress: "0%", subtasks: []
  });

  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [currentView, setCurrentView] = useState<"LIST" | "CALENDAR" | "TIMELINE">("LIST");
  const [selectedTask, setSelectedTask] = useState<TaskResponse | null>(null);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      const [tasksData, facultyData] = await Promise.all([
        tasksApi.getAll(),
        employeesApi.getAll()
      ]);
      setTasks(tasksData);
      setFacultyList(facultyData);
      
      try {
         const [aiData, perfData] = await Promise.all([
            aiApi.getDashboardSummary(),
            analyticsApi.getFacultyPerformance()
         ]);
         
         if(aiData?.hod_actions) {
            setHodActions(aiData.hod_actions);
         }
         
         if(perfData) {
            setFacultyPerformance(perfData);
         }
      } catch (e) {}
    } catch (err: any) {
      setError(err.message || "Failed to load dashboard data");
    } finally {
      setLoading(false);
    }
  };

  const handleCreateTask = async () => {
    if(!taskForm.title || !taskForm.assigned_id || !taskForm.deadline) {
      alert("Please fill required fields: Title, Assigned Faculty, and Deadline Date");
      return;
    }
    const selectedFac = facultyList.find(f => f.id === taskForm.assigned_id);
    const payload: TaskCreate = { ...taskForm, assigned: selectedFac ? selectedFac.name : "" };
    try {
      await tasksApi.create(payload);
      setShowForm(false);
      setTaskForm({
        title: "", description: "", category: "General", assigned: "", assigned_id: "",
        start_date: "", deadline: "", deadline_time: "", priority: "High",
        estimated_effort: "", reminder: "1 day before", require_approval: false,
        status: "Pending", progress: "0%", subtasks: []
      });
      await fetchData();
    } catch(err: any) {
      alert("Error creating task: " + err.message);
    }
  };
  
  const handleApproval = async (task: TaskResponse, approved: boolean) => {
    const newStatus = approved ? "Completed" : "In Progress";
    const newProgress = approved ? "100%" : "75%";
    try {
      await tasksApi.update(task.id, { status: newStatus, progress: newProgress });
      await fetchData();
    } catch (e: any) {
      alert("Failed to update approval: " + e.message);
    }
  };

  if (loading) return <div className="hs-page text-center text-slate-500">Loading HOD Dashboard...</div>;

  const totalTasks = tasks.length;
  const pendingCount = tasks.filter(t => t.status === "Pending").length;
  const inProgressCount = tasks.filter(t => t.status === "In Progress").length;
  const completedCount = tasks.filter(t => t.status === "Completed").length;
  const overdueCount = tasks.filter(t => t.risk_level === "HIGH" && t.status !== "Completed" && t.status !== "Awaiting Approval").length;

  const filteredTasks = tasks.filter(t => {
    if(statusFilter && t.status !== statusFilter) return false;
    if(searchTerm && !t.title.toLowerCase().includes(searchTerm.toLowerCase()) && !t.assigned?.toLowerCase().includes(searchTerm.toLowerCase())) return false;
    return true;
  });

  return (
    <div className="hs-page font-sans">
      <div className="flex justify-between items-start mb-8">
        <div>
          <h1 className="text-3xl font-bold text-slate-800">Department Task Management</h1>
          <p className="text-slate-500 mt-1">Manage department activities, deadlines and approvals</p>
        </div>
        <button onClick={() => setShowForm(!showForm)} className="bg-indigo-600 text-white px-5 py-2.5 rounded-lg font-medium shadow-sm hover:bg-indigo-700 flex items-center gap-2">
          <Plus className="w-5 h-5"/> {showForm ? "Cancel Creation" : "Add New Task"}
        </button>
      </div>

      {error && <div className="bg-red-50 text-red-600 p-4 rounded-xl mb-6">{error}</div>}

      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
        <div className="bg-white p-5 rounded-2xl shadow-sm border border-slate-100">
          <div className="text-sm font-semibold text-slate-400 mb-1">Total Tasks</div>
          <div className="text-3xl font-bold text-indigo-600">{totalTasks}</div>
        </div>
        <div className="bg-white p-5 rounded-2xl shadow-sm border border-slate-100">
          <div className="text-sm font-semibold text-slate-400 mb-1 flex items-center gap-2"><Clock className="w-4 h-4"/> Pending</div>
          <div className="text-3xl font-bold text-slate-700">{pendingCount}</div>
        </div>
        <div className="bg-white p-5 rounded-2xl shadow-sm border border-slate-100">
          <div className="text-sm font-semibold text-slate-400 mb-1 flex items-center gap-2"><PlayCircle className="w-4 h-4"/> In Progress</div>
          <div className="text-3xl font-bold text-blue-600">{inProgressCount}</div>
        </div>
        <div className="bg-white p-5 rounded-2xl shadow-sm border border-slate-100">
          <div className="text-sm font-semibold text-slate-400 mb-1 flex items-center gap-2"><CheckCircle className="w-4 h-4"/> Completed</div>
          <div className="text-3xl font-bold text-emerald-500">{completedCount}</div>
        </div>
        <div className="bg-white p-5 rounded-2xl shadow-sm border border-red-100">
          <div className="text-sm font-semibold text-red-400 mb-1 flex items-center gap-2"><AlertCircle className="w-4 h-4"/> High Risk</div>
          <div className="text-3xl font-bold text-red-500">{overdueCount}</div>
        </div>
      </div>

      {showForm && (
        <div className="bg-white rounded-2xl shadow-md border border-indigo-100 p-6 mb-8">
          <h2 className="text-xl font-bold text-indigo-900 mb-4 border-b pb-2">Create New Task</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Task Name *</label>
              <input type="text" className="w-full border p-2.5 rounded-lg bg-slate-50 focus:bg-white" value={taskForm.title} onChange={e => setTaskForm({...taskForm, title: e.target.value})} />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Assign To *</label>
              <select className="w-full border p-2.5 rounded-lg bg-slate-50 focus:bg-white" value={taskForm.assigned_id} onChange={e => setTaskForm({...taskForm, assigned_id: e.target.value})}>
                <option value="">-- Select Faculty --</option>
                {facultyList.map(f => <option key={f.id} value={f.id}>{f.name}</option>)}
              </select>
            </div>
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-slate-700 mb-1">Description</label>
              <textarea className="w-full border p-2.5 rounded-lg bg-slate-50 focus:bg-white" rows={2} value={taskForm.description} onChange={e => setTaskForm({...taskForm, description: e.target.value})}></textarea>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Start Date</label>
              <input type="date" className="w-full border p-2.5 rounded-lg bg-slate-50 focus:bg-white" value={taskForm.start_date} onChange={e => setTaskForm({...taskForm, start_date: e.target.value})} />
            </div>
            <div className="flex gap-2">
               <div className="flex-1">
                 <label className="block text-sm font-medium text-slate-700 mb-1">Deadline Date *</label>
                 <input type="date" className="w-full border p-2.5 rounded-lg bg-slate-50 focus:bg-white" value={taskForm.deadline} onChange={e => setTaskForm({...taskForm, deadline: e.target.value})} />
               </div>
               <div className="flex-1">
                 <label className="block text-sm font-medium text-slate-700 mb-1">Deadline Time</label>
                 <input type="time" className="w-full border p-2.5 rounded-lg bg-slate-50 focus:bg-white" value={taskForm.deadline_time} onChange={e => setTaskForm({...taskForm, deadline_time: e.target.value})} />
               </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Priority & Estimated Effort</label>
              <div className="flex gap-2">
                 <select className="flex-1 border p-2.5 rounded-lg bg-slate-50" value={taskForm.priority} onChange={e => setTaskForm({...taskForm, priority: e.target.value})}>
                    <option>High</option><option>Medium</option><option>Low</option>
                 </select>
                 <input type="text" placeholder="e.g. 4 hours" className="flex-1 border p-2.5 rounded-lg bg-slate-50" value={taskForm.estimated_effort} onChange={e => setTaskForm({...taskForm, estimated_effort: e.target.value})} />
              </div>
            </div>
            <div className="flex items-end pb-2">
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" className="w-5 h-5 rounded text-indigo-600 focus:ring-indigo-500" checked={taskForm.require_approval} onChange={e => setTaskForm({...taskForm, require_approval: e.target.checked})} />
                <span className="text-sm font-medium text-slate-700">Require HOD Approval to Complete</span>
              </label>
            </div>
          </div>
          <div className="mt-6 flex justify-end gap-3">
             <button onClick={() => setShowForm(false)} className="px-5 py-2 text-slate-600 hover:bg-slate-100 rounded-lg font-medium">Cancel</button>
             <button onClick={handleCreateTask} className="px-6 py-2 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700">Create Task</button>
          </div>
        </div>
      )}

      {/* Main Content Area */}
      <div className="flex flex-col lg:flex-row gap-6">
        
        {/* Left Side: Task List */}
        <div className="flex-1">
          <div className="bg-white rounded-2xl shadow-sm border border-slate-100 overflow-hidden mb-6">
            <div className="px-6 py-4 border-b border-slate-100 bg-slate-50/50 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
              <div className="flex items-center gap-2 bg-slate-200/50 p-1 rounded-lg">
                 <button onClick={() => setCurrentView("LIST")} className={`p-1.5 rounded-md flex items-center gap-1.5 text-xs font-bold transition ${currentView === 'LIST' ? 'bg-white shadow-sm text-indigo-700' : 'text-slate-500 hover:text-slate-700'}`}>
                    <AlignJustify className="w-4 h-4"/> List
                 </button>
                 <button onClick={() => setCurrentView("CALENDAR")} className={`p-1.5 rounded-md flex items-center gap-1.5 text-xs font-bold transition ${currentView === 'CALENDAR' ? 'bg-white shadow-sm text-indigo-700' : 'text-slate-500 hover:text-slate-700'}`}>
                    <CalendarIcon className="w-4 h-4"/> Calendar
                 </button>
                 <button onClick={() => setCurrentView("TIMELINE")} className={`p-1.5 rounded-md flex items-center gap-1.5 text-xs font-bold transition ${currentView === 'TIMELINE' ? 'bg-white shadow-sm text-indigo-700' : 'text-slate-500 hover:text-slate-700'}`}>
                    <GitCommit className="w-4 h-4"/> Timeline
                 </button>
              </div>

              <div className="flex gap-2 w-full md:w-auto">
                 <div className="relative flex-1 md:w-48">
                   <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
                   <input type="text" placeholder="Search tasks..." className="pl-9 pr-3 py-1.5 border rounded-lg text-sm bg-white w-full" value={searchTerm} onChange={e => setSearchTerm(e.target.value)} />
                 </div>
                 <select className="border rounded-lg text-sm px-3 py-1.5 bg-white text-slate-600" value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
                   <option value="">All Status</option>
                   <option value="Pending">Pending</option>
                   <option value="In Progress">In Progress</option>
                   <option value="Awaiting Approval">Awaiting Approval</option>
                   <option value="Completed">Completed</option>
                 </select>
              </div>
            </div>
            
            {currentView === "LIST" && (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm text-slate-600">
                <thead className="bg-slate-50 text-slate-500 text-xs uppercase font-semibold border-b border-slate-200">
                  <tr>
                    <th className="px-5 py-3">Task</th>
                    <th className="px-5 py-3">Assigned To</th>
                    <th className="px-5 py-3">Priority</th>
                    <th className="px-5 py-3">Deadline</th>
                    <th className="px-5 py-3">Risk</th>
                    <th className="px-5 py-3">Progress</th>
                    <th className="px-5 py-3">Status</th>
                    <th className="px-5 py-3">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {filteredTasks.map(task => (
                    <tr key={task.id} className="hover:bg-slate-50/50 cursor-pointer" onClick={() => setSelectedTask(task)}>
                      <td className="px-5 py-3 font-medium text-slate-800">{task.title}</td>
                      <td className="px-5 py-3">{task.assigned}</td>
                      <td className="px-5 py-3">
                        <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                          task.priority === 'High' ? 'bg-red-100 text-red-700' : task.priority === 'Medium' ? 'bg-amber-100 text-amber-700' : 'bg-blue-100 text-blue-700'
                        }`}>{task.priority || "Medium"}</span>
                      </td>
                      <td className="px-5 py-3 text-xs">{task.deadline}</td>
                      <td className="px-5 py-3">
                        {task.risk_level === 'HIGH' && <span className="text-xs font-bold text-red-600">HIGH ({(task.risk_score||0)}%)</span>}
                        {task.risk_level === 'MEDIUM' && <span className="text-xs font-bold text-orange-500">MED ({(task.risk_score||0)}%)</span>}
                        {task.risk_level === 'LOW' && <span className="text-xs font-bold text-green-600">LOW</span>}
                      </td>
                      <td className="px-5 py-3 text-xs font-semibold">{task.progress}</td>
                      <td className="px-5 py-3">
                         <span className={`inline-flex items-center px-2 py-1 rounded-md text-[10px] font-bold uppercase tracking-wider ${
                          task.status === 'Completed' ? 'bg-emerald-100 text-emerald-700' : task.status === 'Awaiting Approval' ? 'bg-purple-100 text-purple-700' : task.status === 'In Progress' ? 'bg-blue-100 text-blue-700' : 'bg-slate-100 text-slate-700'
                        }`}>{task.status || "Pending"}</span>
                      </td>
                      <td className="px-5 py-3" onClick={(e) => e.stopPropagation()}>
                        {task.status === "Awaiting Approval" && (
                           <div className="flex gap-1">
                             <button onClick={() => handleApproval(task, true)} className="px-2 py-1 bg-green-100 text-green-700 rounded text-xs font-medium hover:bg-green-200">Approve</button>
                             <button onClick={() => handleApproval(task, false)} className="px-2 py-1 bg-red-100 text-red-700 rounded text-xs font-medium hover:bg-red-200">Reject</button>
                           </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            )}

            {currentView === "CALENDAR" && <TaskCalendarView tasks={filteredTasks} onTaskClick={setSelectedTask} />}
            {currentView === "TIMELINE" && <TaskTimelineView tasks={filteredTasks} onTaskClick={setSelectedTask} />}

          </div>
        </div>

         {/* Right Side: Faculty Workload & AI */}
         <div className="w-full lg:w-80 flex flex-col gap-6 shrink-0">
            {/* Action Center */}
            <div className="bg-indigo-50 border border-indigo-100 rounded-2xl p-5 shadow-sm">
               <h3 className="text-sm font-bold text-indigo-900 mb-3 flex items-center gap-2">⚡ HOD Action Center</h3>
               <ul className="space-y-3">
                 {hodActions.length === 0 && (
                   <li className="text-xs text-indigo-700">No actions required.</li>
                 )}
                 {hodActions.map((action, idx) => (
                   <li key={idx} className="bg-white rounded-xl shadow-sm border border-indigo-100 overflow-hidden flex flex-col">
                     <div className="p-3 border-b border-gray-100 bg-gray-50/50">
                        <div className="text-[10px] uppercase font-bold tracking-wider mb-1 flex items-center gap-1.5">
                          {action.type === 'CRITICAL' && <span className="text-red-600"><AlertCircle className="w-3 h-3 inline"/> CRITICAL</span>}
                          {action.type === 'HIGH RISK' && <span className="text-orange-500"><Activity className="w-3 h-3 inline"/> HIGH RISK</span>}
                          {action.type === 'APPROVAL' && <span className="text-purple-600"><FileText className="w-3 h-3 inline"/> APPROVAL</span>}
                          {action.type === 'WORKLOAD' && <span className="text-blue-600"><Users className="w-3 h-3 inline"/> WORKLOAD</span>}
                        </div>
                        <div className="font-bold text-gray-800 text-sm leading-tight">{action.title}</div>
                     </div>
                     <div className="p-3 bg-white">
                        <p className="text-xs text-gray-600 leading-relaxed mb-3">{action.description}</p>
                        <button 
                          onClick={() => {
                            if (action.target_id && (action.type === 'CRITICAL' || action.type === 'HIGH RISK' || action.type === 'APPROVAL')) {
                               const matched = tasks.find(t => t.id === action.target_id);
                               if (matched) setSelectedTask(matched);
                            }
                          }}
                          className="text-xs font-semibold text-indigo-600 hover:text-indigo-700 flex items-center gap-1"
                        >
                          Take Action <ChevronRight className="w-3 h-3" />
                        </button>
                     </div>
                   </li>
                 ))}
               </ul>
            </div>

            {/* Faculty Performance & Score */}
            <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm">
              <h3 className="text-sm font-bold text-slate-800 mb-4 border-b pb-2 flex items-center gap-2"><Activity className="w-4 h-4 text-emerald-500" /> Faculty Performance</h3>
              <div className="space-y-6">
                {facultyPerformance.length === 0 && (
                  <div className="text-xs text-slate-500 text-center py-4">Loading performance data...</div>
                )}
                {facultyPerformance.map(perf => (
                  <div key={perf.faculty_id} className="block group">
                    <div className="flex justify-between items-start mb-2">
                      <div>
                        <span className="text-sm font-bold text-slate-700 block">{perf.faculty_name}</span>
                        <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">{perf.pending} Active • {perf.overdue} Overdue</span>
                      </div>
                      <div className="text-right">
                        <span className={`text-sm font-black ${perf.productivity_score >= 80 ? 'text-emerald-500' : perf.productivity_score >= 60 ? 'text-amber-500' : 'text-red-500'}`}>
                          {perf.productivity_score}
                        </span>
                        <div className="text-[10px] text-slate-400 font-bold">SCORE</div>
                      </div>
                    </div>
                    
                    {/* Tiny stats bar */}
                    <div className="flex gap-1 h-1.5 w-full rounded-full overflow-hidden mb-2">
                       <div className="bg-emerald-400" style={{width: `${perf.on_time_rate}%`}}></div>
                       <div className="bg-slate-200 flex-1"></div>
                    </div>
                    
                    {/* Expandable Explanation */}
                    <div className="hidden group-hover:block mt-3 bg-slate-50 p-3 rounded-lg border border-slate-100 transition-all">
                       <p className="text-xs text-slate-600 whitespace-pre-wrap font-medium leading-relaxed">{perf.productivity_explanation}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
         </div>
      </div>

      {selectedTask && (
        <TaskDetailsModal 
          task={selectedTask} 
          role="HOD" 
          onClose={() => setSelectedTask(null)} 
          onUpdate={() => {
            fetchData();
            // Also need to refresh the task object itself if it was updated
            // To be safe, we close the modal and they can reopen if needed, or we just refresh lists.
          }} 
          facultyList={facultyList}
        />
      )}
    </div>
  );
}
