import { useState, useEffect } from "react";
import { tasksApi, aiApi } from "../../api";
import { TaskResponse, AIPriorityItem } from "../../types";
import { useAuth } from "../../contexts/AuthContext";
import { CheckCircle, Clock, AlertCircle, PlayCircle, Loader2, Calendar as CalendarIcon, AlignJustify, GitCommit, ChevronRight } from "lucide-react";
import TaskDetailsModal from "./TaskDetailsModal";
import { TaskCalendarView, TaskTimelineView } from "./TaskViews";

export default function TeacherDashboard() {
  const { user } = useAuth();
  const [tasks, setTasks] = useState<TaskResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [updating, setUpdating] = useState<string | null>(null);
  const [aiPriorities, setAiPriorities] = useState<AIPriorityItem[]>([]);
  
  const [currentView, setCurrentView] = useState<"LIST" | "CALENDAR" | "TIMELINE">("LIST");
  const [selectedTask, setSelectedTask] = useState<TaskResponse | null>(null);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      const data = await tasksApi.getAll();
      setTasks(data);
      
      try {
         const aiData = await aiApi.getDashboardSummary();
         if(aiData?.teacher_priorities) {
            setAiPriorities(aiData.teacher_priorities);
         }
      } catch (e) {}
    } catch (err: any) {
      setError(err.message || "Failed to load tasks");
    } finally {
      setLoading(false);
    }
  };

  const updateProgress = async (task: TaskResponse, newProgress: string) => {
    try {
      setUpdating(task.id);
      let newStatus = task.status;
      if (newProgress === "100%") {
        newStatus = task.require_approval ? "Awaiting Approval" : "Completed";
      } else if (newProgress !== "0%" && task.status === "Pending") {
        newStatus = "In Progress";
      }

      await tasksApi.update(task.id, { progress: newProgress, status: newStatus });
      await fetchData();
    } catch (err: any) {
      alert("Failed to update task: " + err.message);
    } finally {
      setUpdating(null);
    }
  };

  if (loading) return <div className="p-8 text-center text-slate-500">Loading your tasks...</div>;

  const pendingCount = tasks.filter(t => t.status === "Pending").length;
  const inProgressCount = tasks.filter(t => t.status === "In Progress").length;
  const completedCount = tasks.filter(t => t.status === "Completed" || t.status === "Awaiting Approval").length;
  const overdueCount = tasks.filter(t => t.risk_level === "HIGH" && t.status !== "Completed" && t.status !== "Awaiting Approval").length;

  return (
    <div className="hs-page font-sans">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-slate-800">Welcome, {user?.name.split(' ')[0]} 👋</h1>
        <p className="text-slate-500 mt-1">Here are your assigned tasks and priorities.</p>
      </div>

      {error && <div className="bg-red-50 text-red-600 p-4 rounded-xl mb-6">{error}</div>}

      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
        <div className="bg-white p-5 rounded-2xl shadow-sm border border-slate-100">
          <div className="text-sm font-semibold text-slate-400 mb-1">My Tasks</div>
          <div className="text-3xl font-bold text-indigo-600">{tasks.length}</div>
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

      <div className="flex flex-col lg:flex-row gap-6">
         {/* Left Side: Tasks */}
         <div className="flex-1">
            <div className="bg-white rounded-2xl shadow-sm border border-slate-100 overflow-hidden mb-6">
              <div className="px-6 py-4 border-b border-slate-100 bg-slate-50/50 flex justify-between items-center">
                <h2 className="text-lg font-bold text-slate-700">Assigned Tasks</h2>
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
              </div>
              
              {tasks.length === 0 ? (
                 <div className="p-8 text-center text-slate-500">You don't have any tasks assigned yet.</div>
              ) : (
                <>
                  {currentView === "LIST" && (
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-sm text-slate-600">
                        <thead className="bg-slate-50 text-slate-500 text-xs uppercase font-semibold">
                          <tr>
                            <th className="px-6 py-4">Task</th>
                            <th className="px-6 py-4">Priority</th>
                            <th className="px-6 py-4">Deadline</th>
                            <th className="px-6 py-4">Status</th>
                            <th className="px-6 py-4 w-48">Progress</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                          {tasks.map(task => {
                            const hasSubtasks = task.subtasks && task.subtasks.length > 0;
                            return (
                            <tr key={task.id} className="hover:bg-slate-50/50 transition cursor-pointer" onClick={() => setSelectedTask(task)}>
                              <td className="px-6 py-4">
                                <div className="font-bold text-slate-800 flex items-center gap-2">
                                   {task.title}
                                   {task.risk_level === 'HIGH' && <span title="High Risk"><AlertCircle className="w-3.5 h-3.5 text-red-500" /></span>}
                                </div>
                                {task.category && <div className="text-xs text-slate-400 mt-0.5">{task.category}</div>}
                              </td>
                              <td className="px-6 py-4">
                                <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${
                                  task.priority === 'High' ? 'bg-red-50 text-red-700 border-red-200' : 
                                  task.priority === 'Medium' ? 'bg-amber-50 text-amber-700 border-amber-200' : 
                                  'bg-blue-50 text-blue-700 border-blue-200'
                                }`}>
                                  {task.priority || "Medium"}
                                </span>
                              </td>
                              <td className="px-6 py-4">
                                <div className={`font-medium ${task.risk_level === 'HIGH' ? 'text-red-500' : 'text-slate-600'}`}>
                                  {task.deadline || 'No deadline'}
                                </div>
                              </td>
                              <td className="px-6 py-4">
                                <span className={`inline-flex items-center px-2.5 py-1 rounded-md text-xs font-semibold ${
                                  task.status === 'Completed' ? 'bg-emerald-100 text-emerald-700' :
                                  task.status === 'In Progress' ? 'bg-blue-100 text-blue-700' :
                                  task.status === 'Awaiting Approval' ? 'bg-purple-100 text-purple-700' :
                                  'bg-slate-100 text-slate-700'
                                }`}>
                                  {task.status || "Pending"}
                                </span>
                              </td>
                              <td className="px-6 py-4" onClick={e => e.stopPropagation()}>
                                <div className="flex items-center gap-3">
                                  {hasSubtasks ? (
                                    <div className="w-full text-xs font-bold text-indigo-600 bg-indigo-50 py-1.5 px-3 rounded-lg text-center cursor-pointer" onClick={() => setSelectedTask(task)}>
                                       {task.progress} (See Checklist)
                                    </div>
                                  ) : (
                                    <>
                                       <select 
                                         className="bg-slate-50 border border-slate-200 text-slate-700 rounded-lg text-xs p-1.5 font-medium w-full focus:ring-2 focus:ring-indigo-500 outline-none disabled:opacity-50"
                                         value={task.progress || "0%"}
                                         onChange={(e) => updateProgress(task, e.target.value)}
                                         disabled={updating === task.id || task.status === "Completed" || task.status === "Awaiting Approval"}
                                       >
                                         <option value="0%">0% - Not Started</option>
                                         <option value="25%">25% - Quarter</option>
                                         <option value="50%">50% - Halfway</option>
                                         <option value="75%">75% - Almost</option>
                                         <option value="100%">100% - Done</option>
                                       </select>
                                       {updating === task.id && <Loader2 className="w-4 h-4 animate-spin text-indigo-500 shrink-0" />}
                                    </>
                                  )}
                                </div>
                              </td>
                            </tr>
                          )})}
                        </tbody>
                      </table>
                    </div>
                  )}

                  {currentView === "CALENDAR" && <TaskCalendarView tasks={tasks} onTaskClick={setSelectedTask} />}
                  {currentView === "TIMELINE" && <TaskTimelineView tasks={tasks} onTaskClick={setSelectedTask} />}
                </>
              )}
            </div>
         </div>

         {/* Right Side: AI Today's Priority */}
         <div className="w-full lg:w-80 shrink-0">
            <div className="bg-indigo-50 border border-indigo-100 rounded-2xl p-5 shadow-sm">
              <h3 className="text-sm font-bold text-indigo-900 mb-3 flex items-center gap-2">🤖 Today's Priority</h3>
              <ul className="space-y-4">
                {aiPriorities.length === 0 && (
                  <li className="text-xs text-indigo-700">No urgent priorities today!</li>
                )}
                {aiPriorities.map((item, idx) => (
                  <li key={idx} className="bg-white rounded-xl shadow-sm border border-indigo-100 overflow-hidden">
                    <div className="p-3 border-b border-gray-100 bg-gray-50/50 flex justify-between items-start">
                      <div>
                        <div className="font-bold text-gray-800 text-sm flex items-center gap-1.5">
                           <span className="text-xs font-black text-indigo-400">{item.rank}.</span>
                           {item.title}
                        </div>
                        <div className="text-[10px] uppercase font-bold tracking-wider mt-1 flex gap-2">
                           <span className={item.priority === 'HIGH' ? 'text-red-500' : 'text-amber-500'}>
                             {item.priority} Priority
                           </span>
                           {(item.risk_score || 0) > 60 && (
                             <span className="text-red-600 font-bold flex items-center gap-0.5">
                                <AlertCircle className="w-3 h-3" /> Risk {item.risk_score}%
                             </span>
                           )}
                        </div>
                      </div>
                    </div>
                    <div className="p-3 bg-white">
                      <div className="text-xs font-semibold text-gray-500 mb-1">Why?</div>
                      <ul className="text-xs text-gray-600 space-y-1 mb-3">
                        {(item.why || []).map((reason: string, i: number) => (
                          <li key={i} className="flex items-start gap-1">
                            <span className="text-indigo-400 mt-0.5">•</span>
                            {reason}
                          </li>
                        ))}
                      </ul>
                      <button 
                        onClick={() => {
                          const matched = tasks.find(t => t.id === item.task_id);
                          if (matched) setSelectedTask(matched);
                        }}
                        className="text-xs font-semibold text-indigo-600 hover:text-indigo-700 flex items-center gap-1"
                      >
                        Open Task <ChevronRight className="w-3 h-3" />
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
           </div>
         </div>
      </div>

      {selectedTask && (
        <TaskDetailsModal 
          task={selectedTask} 
          role="FACULTY" 
          onClose={() => {
            setSelectedTask(null);
            fetchData();
          }} 
          onUpdate={fetchData} 
        />
      )}
    </div>
  );
}
