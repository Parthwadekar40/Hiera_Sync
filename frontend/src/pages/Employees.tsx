import { useState, useEffect } from "react";
import { employeesApi } from "../api";
import { joinApi, JoinRequestResponse } from "../api/join";
import { departmentsApi, DepartmentResponse } from "../api/departments";
import { EmployeeResponse } from "../types";
import { useAuth } from "../contexts/AuthContext";
import { CheckCircle, XCircle, RefreshCw, Copy, Users } from "lucide-react";

export default function Employees() {
  const { user } = useAuth();
  const [search, setSearch] = useState("");
  const [selectedFaculty, setSelectedFaculty] = useState<EmployeeResponse | null>(null);
  
  const [facultyList, setFacultyList] = useState<EmployeeResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [department, setDepartment] = useState<DepartmentResponse | null>(null);
  const [pendingRequests, setPendingRequests] = useState<JoinRequestResponse[]>([]);
  const [approvedRequests, setApprovedRequests] = useState<JoinRequestResponse[]>([]);
  const [rejectedRequests, setRejectedRequests] = useState<JoinRequestResponse[]>([]);
  
  const isAdmin = user?.role === "ADMIN" || user?.role === "HOD";

  const fetchData = async () => {
    try {
      setLoading(true);
      const data = await employeesApi.getAll();
      setFacultyList(data);

      if (isAdmin) {
        const [dept, pending, approved, rejected] = await Promise.all([
          departmentsApi.getMine(),
          joinApi.getPending(),
          joinApi.getApproved(),
          joinApi.getRejected()
        ]);
        setDepartment(dept);
        setPendingRequests(pending);
        setApprovedRequests(approved);
        setRejectedRequests(rejected);
      }
    } catch (err: any) {
      setError(err.message || "Failed to load data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleRegenerateCode = async () => {
    try {
      const res = await departmentsApi.regenerateCode();
      setDepartment(res);
      alert("Code regenerated successfully!");
    } catch (err: any) {
      alert("Failed to regenerate code: " + err.message);
    }
  };

  const handleApprove = async (id: string) => {
    try {
      await joinApi.approve(id);
      fetchData();
    } catch (err: any) {
      alert("Failed to approve: " + err.message);
    }
  };

  const handleReject = async (id: string) => {
    try {
      await joinApi.reject(id);
      fetchData();
    } catch (err: any) {
      alert("Failed to reject: " + err.message);
    }
  };

  const filteredFaculty = facultyList.filter((faculty) =>
    faculty.name.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="hs-page space-y-8">
      <div>
        <h1 className="text-4xl font-bold text-gray-800">
          Faculty Management
        </h1>
        <p className="text-gray-500 mt-2">
          {department ? department.name : "Department Faculty"}
        </p>
      </div>

      {isAdmin && department && (
        <div className="bg-white p-6 rounded-3xl shadow-sm border border-blue-100 flex flex-col md:flex-row items-center justify-between gap-4">
          <div>
            <h2 className="text-xl font-bold text-blue-800 flex items-center gap-2">
              <Users size={24} /> Department Invitation Code
            </h2>
            <p className="text-sm text-gray-500 mt-1">Share this code with teachers so they can join.</p>
          </div>
          <div className="flex items-center gap-4">
            <div className="bg-blue-50 text-blue-700 font-mono font-bold px-6 py-3 rounded-xl text-2xl tracking-widest border border-blue-200">
              {department.code}
            </div>
            <button
              onClick={() => { navigator.clipboard.writeText(department.code); alert("Copied!"); }}
              className="p-3 bg-gray-100 text-gray-600 rounded-xl hover:bg-gray-200"
              title="Copy Code"
            >
              <Copy size={20} />
            </button>
            <button
              onClick={handleRegenerateCode}
              className="p-3 bg-red-50 text-red-600 rounded-xl hover:bg-red-100"
              title="Regenerate Code"
            >
              <RefreshCw size={20} />
            </button>
          </div>
        </div>
      )}

      {isAdmin && (
        <div className="grid md:grid-cols-3 gap-6">
          <div className="bg-white rounded-3xl p-6 shadow border-t-4 border-yellow-400">
            <h3 className="text-lg font-bold mb-4">Pending Requests ({pendingRequests.length})</h3>
            <div className="space-y-4 max-h-80 overflow-y-auto">
              {pendingRequests.length === 0 && <p className="text-sm text-gray-500">No pending requests.</p>}
              {pendingRequests.map(req => (
                <div key={req.id} className="p-4 bg-gray-50 rounded-xl border">
                  <p className="font-bold">{req.faculty_name}</p>
                  <p className="text-xs text-gray-500">{req.faculty_email}</p>
                  <p className="text-xs mt-1">Requested: {new Date(req.requested_at).toLocaleDateString()}</p>
                  <div className="flex gap-2 mt-3">
                    <button onClick={() => handleApprove(req.id)} className="flex-1 bg-green-600 text-white py-1.5 rounded-lg text-sm font-semibold flex items-center justify-center gap-1">
                      <CheckCircle size={16} /> Approve
                    </button>
                    <button onClick={() => handleReject(req.id)} className="flex-1 bg-red-100 text-red-700 py-1.5 rounded-lg text-sm font-semibold flex items-center justify-center gap-1">
                      <XCircle size={16} /> Reject
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-white rounded-3xl p-6 shadow border-t-4 border-green-500">
            <h3 className="text-lg font-bold mb-4">Approved ({approvedRequests.length})</h3>
            <div className="space-y-3 max-h-80 overflow-y-auto">
              {approvedRequests.length === 0 && <p className="text-sm text-gray-500">No approved requests.</p>}
              {approvedRequests.map(req => (
                <div key={req.id} className="p-3 bg-green-50 rounded-xl border border-green-100 flex justify-between items-center">
                  <div>
                    <p className="font-bold text-sm">{req.faculty_name}</p>
                    <p className="text-xs text-gray-500">{req.faculty_email}</p>
                  </div>
                  <CheckCircle className="text-green-500" size={20} />
                </div>
              ))}
            </div>
          </div>

          <div className="bg-white rounded-3xl p-6 shadow border-t-4 border-red-500">
            <h3 className="text-lg font-bold mb-4">Rejected ({rejectedRequests.length})</h3>
            <div className="space-y-3 max-h-80 overflow-y-auto">
              {rejectedRequests.length === 0 && <p className="text-sm text-gray-500">No rejected requests.</p>}
              {rejectedRequests.map(req => (
                <div key={req.id} className="p-3 bg-red-50 rounded-xl border border-red-100 flex justify-between items-center">
                  <div>
                    <p className="font-bold text-sm">{req.faculty_name}</p>
                    <p className="text-xs text-gray-500">{req.faculty_email}</p>
                  </div>
                  <XCircle className="text-red-500" size={20} />
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      <div className="bg-white p-4 rounded-2xl shadow mb-8">
        <input
          className="w-full p-3 rounded-xl border outline-none focus:ring-2 focus:ring-blue-400"
          placeholder="🔍 Search Faculty Directory..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {loading && <div className="col-span-3 text-center text-lg text-gray-500 py-10">Loading...</div>}
        {error && <div className="col-span-3 text-center text-lg text-red-500 py-10">{error}</div>}

        {!loading && !error && filteredFaculty.length === 0 && (
          <div className="col-span-3 text-center text-lg text-gray-500 py-10">No employees found.</div>
        )}

        {!loading && !error && filteredFaculty.map((faculty, index) => (
          <div
            key={index}
            className="bg-white rounded-3xl shadow-md p-6 hover:shadow-xl hover:-translate-y-2 transition"
          >
            <div className="flex items-center gap-4">
              <div className="w-16 h-16 rounded-full bg-gradient-to-r from-blue-600 to-cyan-400 text-white flex items-center justify-center text-3xl font-bold uppercase">
                {faculty.name.charAt(0)}
              </div>
              <div>
                <h2 className="font-bold text-blue-700">{faculty.name}</h2>
                <span className="text-xs bg-blue-100 text-blue-600 px-3 py-1 rounded-full font-semibold uppercase">
                  {faculty.role}
                </span>
              </div>
            </div>

            <p className="mt-5">
              <b>Designation</b><br />
              {faculty.designation}
            </p>
            <p className="mt-4 text-gray-600">
              <b>Expertise</b><br />
              {faculty.area_of_interest || "Not Available"}
            </p>

            <button
              onClick={() => setSelectedFaculty(faculty)}
              className="mt-5 w-full bg-blue-600 text-white py-3 rounded-xl hover:bg-blue-700"
            >
              View Profile
            </button>
          </div>
        ))}
      </div>

      {selectedFaculty && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div 
            className="bg-white w-[500px] rounded-3xl p-8 shadow-xl"
            role="dialog"
            aria-modal="true"
            aria-labelledby="modal-title"
          >
            <div className="flex justify-between">
              <h2 id="modal-title" className="text-2xl font-bold text-blue-700">
                Faculty Profile
              </h2>
              <button
                onClick={() => setSelectedFaculty(null)}
                className="text-red-500 text-2xl hover:bg-red-50 rounded-full w-8 h-8 flex items-center justify-center"
                aria-label="Close profile modal"
              >
                ×
              </button>
            </div>
            
            <div className="mt-6 space-y-4">
              <h3 className="text-xl font-bold">{selectedFaculty.name}</h3>
              <p><b>Role:</b> {selectedFaculty.role}</p>
              <p><b>Designation:</b> {selectedFaculty.designation}</p>
              <p><b>Area of Interest:</b> {selectedFaculty.area_of_interest || "Not Available"}</p>
              <p><b>Joining Date:</b> {selectedFaculty.joining_date || "Not Available"}</p>
              <p><b>Association:</b> {selectedFaculty.association || "Not Available"}</p>
              <p><b>Email:</b> {selectedFaculty.email}</p>
            </div>

            <button
              onClick={() => setSelectedFaculty(null)}
              className="mt-6 w-full bg-blue-600 text-white py-3 rounded-xl"
            >
              Close Profile
            </button>
          </div>
        </div>
      )}
    </div>
  );
}