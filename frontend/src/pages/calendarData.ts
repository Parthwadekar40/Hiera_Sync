import type {
  ActivityPriority,
  ActivityStatus,
  ActivityType,
  EventResponse,
} from "../types";
import { dayKey, toISODate } from "../utils/calendar";

export const ACTIVITY_TYPES: ActivityType[] = [
  "Academic",
  "Meeting",
  "Workshop",
  "Department Activity",
  "Research",
];

export const STATUS_FLOW: ActivityStatus[] = [
  "Planned",
  "Assigned",
  "Review",
  "Completed",
];

export const PRIORITIES: ActivityPriority[] = ["Low", "Medium", "High"];

export const typeIcons: Record<ActivityType, string> = {
  Academic: "📚",
  Meeting: "👥",
  Workshop: "🎓",
  "Department Activity": "🏫",
  Research: "🔬",
};

export const typeClass: Record<ActivityType, string> = {
  Academic: "academic",
  Meeting: "meeting",
  Workshop: "workshop",
  "Department Activity": "department",
  Research: "research",
};

export const asActivityType = (value?: string | null): ActivityType =>
  (ACTIVITY_TYPES as string[]).includes(String(value))
    ? (value as ActivityType)
    : "Academic";

export const asStatus = (value?: string | null): ActivityStatus =>
  (STATUS_FLOW as string[]).includes(String(value))
    ? (value as ActivityStatus)
    : "Planned";

/**
 * One shape for every event, whatever the API sent.
 * Dates are normalised to ISO and unknown enums fall back to safe defaults,
 * so a legacy record ("05 August 2026", missing status) still renders.
 */
export const normalizeEvent = (event: any): EventResponse => ({
  ...event,
  id: String(event?.id ?? ""),
  date: toISODate(event?.date) || dayKey(new Date()),
  type: asActivityType(event?.type),
  status: asStatus(event?.status),
  priority: (["Low", "Medium", "High"].includes(event?.priority)
    ? event.priority
    : "Medium") as ActivityPriority,
  all_day: event?.all_day !== false,
  person: event?.person ?? "",
  location: event?.location ?? "",
  description: event?.description ?? "",
  start_time: event?.start_time ?? "",
  end_time: event?.end_time ?? "",
});

const shiftDay = (days: number) => {
  const date = new Date();
  date.setDate(date.getDate() + days);
  return dayKey(date);
};

/**
 * Offline preview data — used only when the API is unreachable so the screen
 * can still be demonstrated. The page labels it explicitly as a preview.
 */
export const buildPreviewEvents = (): EventResponse[] => {
  const seeds: Array<Partial<EventResponse> & { date: string; title: string }> = [
    {
      date: shiftDay(-4),
      title: "Course File Verification — TYAIML",
      type: "Department Activity",
      person: "Mrs. Neha Gurnani",
      status: "Completed",
      location: "HOD Room",
      description: "Audit of continuous assessment records and tutorial sheets.",
    },
    {
      date: shiftDay(-1),
      title: "Minor Project Internal Review",
      type: "Academic",
      person: "Dr. Animesh Tayal",
      status: "Review",
      priority: "High",
      start_time: "10:00",
      end_time: "13:00",
      location: "Seminar Hall",
      description: "Phase-1 evaluation of minor project titles with an external reviewer.",
    },
    {
      date: shiftDay(1),
      title: "AI/ML Research Paper Discussion",
      type: "Research",
      person: "Dr. Bhushan Mahendra Manjre",
      status: "Assigned",
      priority: "Medium",
      start_time: "15:30",
      end_time: "17:00",
      location: "Research Lab",
      description: "Review of two conference submissions before camera-ready.",
    },
    {
      date: shiftDay(2),
      title: "Faculty Coordination Meeting",
      type: "Meeting",
      person: "Ms. Sweta Arun Bokade",
      status: "Planned",
      priority: "Medium",
      start_time: "11:00",
      end_time: "12:00",
      location: "Conference Room",
      description: "Timetable adjustments, invigilation duty and lab allocation.",
    },
    {
      date: shiftDay(4),
      title: "Hands-on Workshop: LLM Fine-tuning",
      type: "Workshop",
      person: "Dr. Animesh Tayal",
      status: "Planned",
      priority: "High",
      start_time: "09:30",
      end_time: "16:30",
      location: "AI Lab",
      description: "Two-session workshop covering LoRA fine-tuning and evaluation.",
    },
    {
      date: shiftDay(4),
      title: "Mid-Semester Assessment — SYAIML",
      type: "Academic",
      person: "Dr. Animesh Tayal",
      status: "Assigned",
      priority: "High",
      start_time: "14:00",
      end_time: "17:00",
      location: "Exam Block B",
      description: "Question paper moderation and evaluation plan.",
    },
    {
      date: shiftDay(6),
      title: "Industry Visit — Nagpur AI Park",
      type: "Department Activity",
      person: "Mrs. Neha Gurnani",
      status: "Planned",
      priority: "Low",
      start_time: "08:00",
      end_time: "18:00",
      location: "On site",
      description: "Student exposure visit with consent forms and faculty escort roster.",
    },
    {
      date: shiftDay(9),
      title: "Final Year Project Review — Phase 2",
      type: "Academic",
      person: "Dr. Bhushan Mahendra Manjre",
      status: "Planned",
      priority: "High",
      start_time: "10:00",
      end_time: "15:00",
      location: "Seminar Hall",
      description: "Prototype demonstration and synopsis progress presentation.",
    },
    {
      date: shiftDay(13),
      title: "NPTEL & Research Fellowship Briefing",
      type: "Meeting",
      person: "Ms. Sweta Arun Bokade",
      status: "Planned",
      priority: "Low",
      location: "CSE Seminar Room",
      description: "Eligibility, certification tracks and stipend documentation.",
    },
    {
      date: shiftDay(17),
      title: "Smart India Hackathon Internal Shortlist",
      type: "Workshop",
      person: "Ms. Preeti Deshmukh",
      status: "Planned",
      priority: "Medium",
      start_time: "13:00",
      end_time: "17:30",
      location: "AI Lab",
      description: "Team pitches and problem-statement mapping for SIH 2026.",
    },
  ];

  return seeds.map((seed, index) =>
    normalizeEvent({
      id: `preview_${index + 1}`,
      creator_id: "system",
      created_at: new Date().toISOString(),
      all_day: !seed.start_time,
      ...seed,
    })
  );
};

const STORAGE_KEY = "hiera:calendar:preview-events";

export const readPreviewEvents = (): EventResponse[] | null => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.map(normalizeEvent) : null;
  } catch {
    return null;
  }
};

export const writePreviewEvents = (events: EventResponse[]) => {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(events));
  } catch {
    /* storage unavailable (private mode) — the preview stays in memory */
  }
};
