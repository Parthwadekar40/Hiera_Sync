import { useState, useEffect } from "react";
import { settingsApi } from "../api";
import { useAuth } from "../contexts/AuthContext";
import FileUpload from "../components/FileUpload";

export default function Settings() {
  const { user } = useAuth();
  const [aiRecommendation, setAiRecommendation] = useState(true);
  const [taskAnalysis, setTaskAnalysis] = useState(true);
  const [deadlineAlert, setDeadlineAlert] = useState(true);
  
  const [department, setDepartment] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [settings, dept] = await Promise.all([
          settingsApi.getUserSettings().catch(() => null),
          settingsApi.getDepartmentProfile().catch(() => null)
        ]);

        if (settings) {
          setAiRecommendation(settings.ai_recommendation ?? true);
          setTaskAnalysis(settings.task_analysis ?? true);
          setDeadlineAlert(settings.deadline_alert ?? true);
        }
        if (dept) setDepartment(dept);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const handleSaveSettings = async () => {
    setSaving(true);
    try {
      await settingsApi.updateUserSettings({
        ai_recommendation: aiRecommendation,
        task_analysis: taskAnalysis,
        deadline_alert: deadlineAlert
      });
      alert("Settings saved successfully!");
    } catch (err: any) {
      alert("Failed to save settings: " + err.message);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div className="hs-page py-16 text-center">Loading settings...</div>;
  }

  return (
    <div className="hs-page">
      <h1 className="text-4xl font-bold text-gray-800">System Settings</h1>
      <p className="text-gray-500 mt-2 mb-8">Manage HieraSync AIML Department preferences</p>

      {/* Profile Section */}
      <div className="bg-white rounded-3xl shadow p-6 mb-8 flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold text-blue-700 mb-5">👤 User Profile</h2>
          <div className="flex items-center gap-5">
            <div className="w-20 h-20 rounded-full bg-blue-600 text-white flex items-center justify-center text-4xl font-bold">
              {user?.name?.charAt(0) || "U"}
            </div>
            <div>
              <h3 className="text-xl font-bold">{user?.name || "User"}</h3>
              <p className="text-gray-500">{user?.role || "Faculty"}</p>
              <p className="text-gray-500">AIML Department | SBJIT Nagpur</p>
            </div>
          </div>
        </div>
        
        <div className="w-96">
          <h3 className="font-bold text-gray-700 mb-2">Upload Profile Picture</h3>
          <FileUpload />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Department Profile */}
        <div className="bg-white rounded-3xl shadow p-6">
          <h2 className="text-2xl font-bold text-blue-700 mb-5">🏢 Department Profile</h2>
          <div className="space-y-4 text-gray-700">
            <p><b>Department:</b><br />{department?.department || "Artificial Intelligence & Machine Learning"}</p>
            <p><b>Institute:</b><br />{department?.institute || "SBJIT Nagpur"}</p>
            <p><b>Platform:</b><br />{department?.platform || "HieraSync AI"}</p>
            <p><b>Purpose:</b><br />{department?.purpose || "Organizational Workflow Management"}</p>
          </div>
        </div>

        {/* AI Settings */}
        <div className="bg-white rounded-3xl shadow p-6 relative">
          <h2 className="text-2xl font-bold text-blue-700 mb-5">🤖 AI Assistant Settings</h2>
          <div className="space-y-6">
            <div className="flex justify-between items-center">
              <span>AI Recommendations</span>
              <input type="checkbox" checked={aiRecommendation} onChange={() => setAiRecommendation(!aiRecommendation)} className="w-5 h-5" />
            </div>
            <div className="flex justify-between items-center">
              <span>Task Priority Analysis</span>
              <input type="checkbox" checked={taskAnalysis} onChange={() => setTaskAnalysis(!taskAnalysis)} className="w-5 h-5" />
            </div>
            <div className="flex justify-between items-center">
              <span>Deadline Alerts</span>
              <input type="checkbox" checked={deadlineAlert} onChange={() => setDeadlineAlert(!deadlineAlert)} className="w-5 h-5" />
            </div>
          </div>
          
          <div className="mt-8 flex justify-end">
            <button 
              onClick={handleSaveSettings} 
              disabled={saving}
              className="bg-blue-600 text-white px-6 py-2 rounded-xl hover:bg-blue-700 disabled:opacity-50"
            >
              {saving ? "Saving..." : "Save Settings"}
            </button>
          </div>
        </div>

        {/* Notification Settings */}
        <div className="bg-white rounded-3xl shadow p-6">
          <h2 className="text-2xl font-bold text-blue-700 mb-5">🔔 Notification Preferences</h2>
          <div className="space-y-3">
            <div className="bg-blue-50 p-4 rounded-xl">✅ Task Assignment Alerts</div>
            <div className="bg-green-50 p-4 rounded-xl">✅ Approval Updates</div>
            <div className="bg-purple-50 p-4 rounded-xl">✅ Upcoming Deadline Reminder</div>
          </div>
        </div>

        {/* System Information */}
        <div className="bg-gradient-to-r from-blue-100 to-cyan-100 border rounded-3xl shadow p-6">
          <h2 className="text-2xl font-bold text-blue-700">⚡ HieraSync System</h2>
          <p className="mt-4 text-gray-700">AI Powered Organizational Workflow Management Platform</p>
          <p className="mt-3 text-gray-600">Version: {department?.version || "1.0"}</p>
          <p className="mt-3 text-gray-600">Status: {department?.status || "Active"}</p>
        </div>
      </div>
    </div>
  );
}