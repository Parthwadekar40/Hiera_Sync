import { useState, useEffect } from "react";
import { goalsApi } from "../api";
import { DepartmentGoalResponse } from "../types";
import { useAuth } from "../contexts/AuthContext";

export default function Goals() {
  const { user } = useAuth();
  const [goals, setGoals] = useState<DepartmentGoalResponse[]>([]);
  const [loading, setLoading] = useState(true);

  const isHod = user?.role === "HOD" || user?.role === "ADMIN";

  useEffect(() => {
    fetchGoals();
  }, []);

  const fetchGoals = async () => {
    try {
      const data = await goalsApi.getAll();
      setGoals(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateGoal = async () => {
    const title = prompt("Enter goal title:");
    if (!title) return;
    const desc = prompt("Enter description:");
    if (!desc) return;
    const target = prompt("Target deadline (YYYY-MM-DD):");
    if (!target) return;

    try {
      await goalsApi.create({
        title,
        description: desc,
        start_date: new Date().toISOString().split('T')[0],
        target_date: target,
      });
      fetchGoals();
    } catch (e) {
      alert("Failed to create goal");
    }
  };

  if (loading) return <div>Loading goals...</div>;

  return (
    <div className="hs-page">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Department Goals & Milestones</h1>
        {isHod && (
          <button onClick={handleCreateGoal} className="bg-indigo-600 text-white px-4 py-2 rounded-md hover:bg-indigo-700">
            + New Goal
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {goals.map(goal => (
          <div key={goal.id} className="bg-white rounded-lg shadow p-6 border-l-4 border-indigo-500">
            <h3 className="text-lg font-bold text-gray-900">{goal.title}</h3>
            <p className="text-gray-600 text-sm mt-2">{goal.description}</p>
            <div className="mt-4 flex justify-between text-sm text-gray-500">
              <span>Status: <strong className="text-indigo-600">{goal.status}</strong></span>
              <span>Target: {goal.target_date}</span>
            </div>
            {goal.milestones.length > 0 && (
              <div className="mt-4 pt-4 border-t border-gray-100">
                <h4 className="text-sm font-semibold mb-2">Milestones</h4>
                <ul className="space-y-2">
                  {goal.milestones.map(m => (
                    <li key={m.id} className="flex items-center text-sm">
                      <span className={`w-2 h-2 rounded-full mr-2 ${m.status === 'COMPLETED' ? 'bg-green-500' : 'bg-gray-300'}`}></span>
                      {m.title}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ))}
        {goals.length === 0 && (
          <div className="col-span-2 text-center text-gray-500 py-10 bg-white rounded-lg shadow">
            No active department goals.
          </div>
        )}
      </div>
    </div>
  );
}
