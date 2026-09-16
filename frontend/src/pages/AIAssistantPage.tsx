import { useState, useRef, useEffect } from "react";
import {
  FaRobot,
  FaPaperPlane,
  FaTrashAlt,
  FaLightbulb,
  FaCheckCircle,
  FaServer,
  FaBolt,
  FaChartLine,
  FaShieldAlt,
  FaArrowRight
} from "react-icons/fa";
import { Sparkles } from "lucide-react";
import { aiApi } from "../api";
import { AIChatResponse } from "../types";
import { useAuth } from "../contexts/AuthContext";

export default function AIAssistantPage() {
  const { user } = useAuth();
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<AIChatResponse[]>([
    {
      user: "System Initialized",
      ai: `Hello ${user?.name || "Faculty"}! I am HiéraSync AI, your academic workflow intelligence assistant for the AIML Department at SBJIT Nagpur. How can I assist you today?`
    }
  ]);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  const handleSend = async (messageText?: string) => {
    const textToSend = (messageText || input).trim();
    if (!textToSend || loading) return;

    if (!messageText) setInput("");

    // Optimistic UI update
    setMessages(prev => [...prev, { user: textToSend, ai: "..." }]);
    setLoading(true);

    try {
      const response = await aiApi.chat({ message: textToSend });
      setMessages(prev => {
        const newMsgs = [...prev];
        newMsgs[newMsgs.length - 1] = response;
        return newMsgs;
      });
    } catch (error: any) {
      const errorMsg = error?.message || "Encountered an issue processing your request. Please try again.";
      setMessages(prev => {
        const newMsgs = [...prev];
        newMsgs[newMsgs.length - 1] = {
          user: textToSend,
          ai: `⚠️ ${errorMsg}`
        };
        return newMsgs;
      });
    } finally {
      setLoading(false);
    }
  };

  const handleClear = () => {
    setMessages([
      {
        user: "System Initialized",
        ai: `Conversation cleared. Ready for new queries regarding AIML department tasks, approvals, or schedules!`
      }
    ]);
  };

  const quickPrompts = [
    { label: "Summarize department tasks", query: "Summarize active department tasks and high priority items." },
    { label: "Show pending approvals", query: "What approvals are currently pending review?" },
    { label: "Check calendar insights", query: "Provide calendar insights for upcoming events and deadlines." },
    { label: "Generate department report", query: "Generate an AI summary report for department performance." }
  ];

  return (
    <div className="hs-page space-y-6 font-sans">

      {/* HEADER BANNER */}
      <div className="bg-gradient-to-r from-[#1E1B4B] via-[#312E81] to-[#4338CA] rounded-2xl p-6 text-white shadow-xl flex flex-col md:flex-row justify-between items-start md:items-center gap-4 relative overflow-hidden">
        <div className="absolute top-0 right-0 w-96 h-96 bg-purple-500/10 rounded-full filter blur-3xl pointer-events-none" />

        <div className="z-10 flex items-center gap-4">
          <div className="w-14 h-14 rounded-2xl bg-white/10 backdrop-blur-md border border-white/20 flex items-center justify-center text-white text-2xl shadow-inner shrink-0">
            <FaRobot />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold tracking-tight">HiéraSync AI Assistant</h1>
              <span className="bg-emerald-500/20 text-emerald-300 text-xs font-semibold px-2.5 py-0.5 rounded-full border border-emerald-500/30 flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                Gemini 2.5 Flash
              </span>
            </div>
            <p className="text-indigo-200 text-sm mt-1">
              Autonomous Academic Workflow & Department Intelligence • SBJIT Nagpur AIML
            </p>
          </div>
        </div>

        <div className="z-10 flex items-center gap-3">
          <button
            onClick={handleClear}
            className="flex items-center gap-2 bg-white/10 hover:bg-white/20 text-white text-xs font-semibold px-4 py-2 rounded-xl transition border border-white/15 backdrop-blur-sm"
          >
            <FaTrashAlt />
            <span>Clear Chat</span>
          </button>
        </div>
      </div>

      {/* MAIN LAYOUT GRID */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">

        {/* LEFT/CENTER CHAT AREA (3 COLS) */}
        <div className="lg:col-span-3 flex flex-col bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden h-[680px]">

          {/* QUICK PROMPT CHIPS BANNER */}
          <div className="p-4 bg-slate-50 border-b border-gray-100 flex items-center gap-2 overflow-x-auto">
            <span className="text-xs font-bold text-gray-500 flex items-center gap-1 shrink-0 uppercase tracking-wider">
              <FaLightbulb className="text-amber-500" /> Suggestions:
            </span>
            <div className="flex items-center gap-2">
              {quickPrompts.map((chip, index) => (
                <button
                  key={index}
                  onClick={() => handleSend(chip.query)}
                  disabled={loading}
                  className="whitespace-nowrap text-xs font-medium bg-white hover:bg-indigo-50 hover:text-indigo-600 hover:border-indigo-200 text-gray-700 px-3.5 py-1.5 rounded-full border border-gray-200 transition shadow-2xs flex items-center gap-1.5 disabled:opacity-50"
                >
                  <span>{chip.label}</span>
                  <FaArrowRight className="text-[10px] text-gray-400" />
                </button>
              ))}
            </div>
          </div>

          {/* MESSAGES STREAM */}
          <div className="flex-1 p-6 overflow-y-auto space-y-5 bg-[#FAFBFD]">
            {messages.map((msg, index) => (
              <div key={index} className="space-y-3">
                {/* User Message */}
                {msg.user && (
                  <div className="flex justify-end">
                    <div className="bg-[#4338CA] text-white rounded-2xl rounded-tr-xs px-5 py-3 max-w-[80%] shadow-sm text-sm font-medium leading-relaxed">
                      {msg.user}
                    </div>
                  </div>
                )}

                {/* AI Message */}
                <div className="flex justify-start items-start gap-3">
                  <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-indigo-600 to-purple-600 text-white flex items-center justify-center text-xs shadow-xs shrink-0 mt-0.5">
                    <Sparkles className="w-4 h-4" />
                  </div>
                  <div className="bg-white border border-gray-200/80 text-gray-800 rounded-2xl rounded-tl-xs p-4 max-w-[85%] shadow-xs text-sm leading-relaxed whitespace-pre-wrap">
                    {msg.ai === "..." ? (
                      <div className="flex items-center gap-2 text-indigo-600 py-1 font-medium">
                        <span className="w-2 h-2 rounded-full bg-indigo-600 animate-bounce" />
                        <span className="w-2 h-2 rounded-full bg-indigo-600 animate-bounce [animation-delay:0.2s]" />
                        <span className="w-2 h-2 rounded-full bg-indigo-600 animate-bounce [animation-delay:0.4s]" />
                        <span className="text-xs text-gray-400 ml-2">Analyzing department context...</span>
                      </div>
                    ) : (
                      msg.ai
                    )}
                  </div>
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>

          {/* INPUT BAR */}
          <div className="p-4 bg-white border-t border-gray-100 flex items-center gap-3">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSend()}
              placeholder="Ask HiéraSync AI about department tasks, approvals, schedule..."
              disabled={loading}
              className="flex-1 bg-gray-50 hover:bg-gray-100/70 focus:bg-white border border-gray-200 focus:border-indigo-500 rounded-xl px-4 py-3 text-sm outline-none transition focus:ring-4 focus:ring-indigo-500/10 text-gray-800 placeholder-gray-400 font-medium"
            />
            <button
              onClick={() => handleSend()}
              disabled={loading || !input.trim()}
              className="bg-[#4338CA] hover:bg-[#3730A3] disabled:opacity-50 text-white p-3.5 rounded-xl shadow-md shadow-indigo-500/20 transition flex items-center justify-center shrink-0 cursor-pointer"
            >
              <FaPaperPlane className="text-sm" />
            </button>
          </div>
        </div>

        {/* RIGHT SIDEBAR: SYSTEM TELEMETRY & CONTEXT (1 COL) */}
        <div className="space-y-6">

          {/* MODEL STATUS CARD */}
          <div className="bg-white rounded-2xl border border-gray-200 p-5 shadow-xs space-y-4">
            <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider flex items-center gap-2">
              <FaServer className="text-indigo-600" /> System Telemetry
            </h3>

            <div className="space-y-3.5">
              <div className="flex items-center justify-between text-xs">
                <span className="text-gray-500 flex items-center gap-2">
                  <FaBolt className="text-amber-500" /> AI Engine
                </span>
                <span className="font-semibold text-gray-800">Gemini 2.5 Flash</span>
              </div>

              <div className="flex items-center justify-between text-xs">
                <span className="text-gray-500 flex items-center gap-2">
                  <FaCheckCircle className="text-emerald-500" /> Firestore Data Sync
                </span>
                <span className="font-semibold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-md">Connected</span>
              </div>

              <div className="flex items-center justify-between text-xs">
                <span className="text-gray-500 flex items-center gap-2">
                  <FaChartLine className="text-blue-500" /> System Latency
                </span>
                <span className="font-semibold text-gray-800">~120 ms</span>
              </div>

              <div className="flex items-center justify-between text-xs">
                <span className="text-gray-500 flex items-center gap-2">
                  <FaShieldAlt className="text-purple-500" /> Security Protocol
                </span>
                <span className="font-semibold text-gray-800">JWT Authenticated</span>
              </div>
            </div>
          </div>

          {/* ACTIVE USER CONTEXT CARD */}
          <div className="bg-gradient-to-br from-indigo-50 to-purple-50 rounded-2xl border border-indigo-100 p-5 shadow-xs space-y-3">
            <h3 className="text-xs font-bold text-indigo-900 uppercase tracking-wider flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-indigo-600" /> User Context
            </h3>

            <div className="text-xs space-y-2 text-indigo-950">
              <p><strong>Name:</strong> {user?.name || "Faculty Member"}</p>
              <p><strong>Role:</strong> <span className="bg-indigo-200/60 text-indigo-900 px-2 py-0.5 rounded-md font-semibold">{user?.role || "FACULTY"}</span></p>
              <p><strong>Department:</strong> AIML • SBJIT Nagpur</p>
              <p><strong>Status:</strong> {user?.status || "ACTIVE"}</p>
            </div>
          </div>

          {/* AI CAPABILITIES & TIPS */}
          <div className="bg-white rounded-2xl border border-gray-200 p-5 shadow-xs space-y-3 text-xs text-gray-600 leading-relaxed">
            <h4 className="font-bold text-gray-800 text-sm">💡 Intelligent Assistance</h4>
            <p>HiéraSync AI can summarize your assigned tasks, analyze pending department approvals, check calendar events, and draft institutional reports in real-time.</p>
          </div>

        </div>

      </div>

    </div>
  );
}
