import { useState, useEffect } from "react";
import { requestsApi } from "../api";
import { TaskRequestResponse } from "../types";
import { useAuth } from "../contexts/AuthContext";

export default function TaskRequests() {
  const { user } = useAuth();
  const [requests, setRequests] = useState<TaskRequestResponse[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchRequests();
  }, []);

  const fetchRequests = async () => {
    try {
      const data = await requestsApi.getAll();
      setRequests(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateRequest = async () => {
    const title = prompt("Enter task title:");
    if (!title) return;
    const desc = prompt("Enter description:");
    if (!desc) return;
    const deadline = prompt("Suggested deadline (YYYY-MM-DD):");
    if (!deadline) return;

    try {
      await requestsApi.create({
        title,
        description: desc,
        suggested_deadline: deadline
      });
      fetchRequests();
    } catch (e) {
      alert("Failed to create request");
    }
  };

  const handleApprove = async (reqId: string) => {
    try {
      await requestsApi.update(reqId, { status: "APPROVED" });
      fetchRequests();
    } catch (e) {
      alert("Failed to approve");
    }
  };

  const handleReject = async (reqId: string) => {
    const reason = prompt("Enter rejection reason:");
    try {
      await requestsApi.update(reqId, { status: "REJECTED", rejection_reason: reason });
      fetchRequests();
    } catch (e) {
      alert("Failed to reject");
    }
  };

  const isHod = user?.role === "HOD" || user?.role === "ADMIN";

  if (loading) return <div>Loading requests...</div>;

  return (
    <div className="hs-page">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">{isHod ? "Incoming Task Requests" : "My Task Requests"}</h1>
        {!isHod && (
          <button onClick={handleCreateRequest} className="bg-indigo-600 text-white px-4 py-2 rounded-md hover:bg-indigo-700">
            + Request Task
          </button>
        )}
      </div>

      <div className="bg-white rounded-lg shadow overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Title</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Requester</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Deadline</th>
              {isHod && <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>}
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {requests.map(req => (
              <tr key={req.id}>
                <td className="px-6 py-4 whitespace-nowrap">{req.title}</td>
                <td className="px-6 py-4 whitespace-nowrap">{req.requester_name}</td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span className={`px-2 py-1 text-xs rounded-full ${req.status === 'APPROVED' ? 'bg-green-100 text-green-800' : req.status === 'REJECTED' ? 'bg-red-100 text-red-800' : 'bg-yellow-100 text-yellow-800'}`}>
                    {req.status}
                  </span>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">{req.suggested_deadline}</td>
                {isHod && (
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                    {req.status === "PENDING" && (
                      <>
                        <button onClick={() => handleApprove(req.id)} className="text-indigo-600 hover:text-indigo-900 mr-4">Approve</button>
                        <button onClick={() => handleReject(req.id)} className="text-red-600 hover:text-red-900">Reject</button>
                      </>
                    )}
                  </td>
                )}
              </tr>
            ))}
            {requests.length === 0 && (
              <tr><td colSpan={isHod ? 5 : 4} className="px-6 py-4 text-center text-gray-500">No task requests found.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
