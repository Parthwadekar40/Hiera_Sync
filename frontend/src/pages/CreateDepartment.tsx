import { useState } from "react";
import { departmentsApi } from "../api/departments";
import { useAuth } from "../contexts/AuthContext";
import { Building2, Save } from "lucide-react";

export default function CreateDepartment() {
  const { user } = useAuth();
  const [name, setName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    
    setError("");
    setSubmitting(true);
    try {
      await departmentsApi.create({ name: name.trim() });
      window.location.reload(); // Quick way to refresh app state and hide this page
    } catch (err: any) {
      setError(err.message || "Failed to create department");
    } finally {
      setSubmitting(false);
    }
  };

  if (user?.department_id) {
    return (
      <div className="hs-page py-16 text-center">
        <h1 className="text-2xl font-bold">You already manage a department.</h1>
      </div>
    );
  }

  return (
    <div className="hs-page hs-page--narrow">
      <div className="hs-card p-8 shadow-lg">
        <div className="flex justify-center mb-6">
          <div className="w-16 h-16 bg-blue-100 rounded-2xl flex items-center justify-center text-blue-600">
            <Building2 size={32} />
          </div>
        </div>
        
        <h1 className="text-3xl font-bold text-center text-gray-800 mb-2">Create Your Department</h1>
        <p className="text-center text-gray-500 mb-8">
          Initialize your organization to invite faculty and manage workflows.
        </p>

        <form onSubmit={handleSubmit} className="space-y-6">
          {error && (
            <div className="bg-red-50 text-red-600 p-3 rounded-xl text-sm border border-red-100">
              {error}
            </div>
          )}
          
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">
              Department Name
            </label>
            <input
              type="text"
              placeholder="e.g. Artificial Intelligence & Machine Learning"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full border-2 border-gray-200 rounded-xl p-4 text-lg outline-none focus:border-blue-500 transition-colors"
              required
            />
          </div>

          <div className="bg-blue-50 p-4 rounded-xl">
            <p className="text-sm text-blue-800">
              <b>Note:</b> A unique, 8-character uppercase invitation code will be generated automatically for you. 
              You can share this code with teachers so they can request to join.
            </p>
          </div>
          
          <button
            type="submit"
            disabled={submitting || !name.trim()}
            className="w-full bg-blue-600 text-white font-bold py-4 rounded-xl hover:bg-blue-700 transition flex justify-center items-center gap-2 disabled:opacity-50"
          >
            {submitting ? 'Creating...' : 'Save & Continue'}
            <Save size={18} />
          </button>
        </form>
      </div>
    </div>
  );
}
