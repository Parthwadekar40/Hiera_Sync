import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import FullCalendar from "@fullcalendar/react";
import dayGridPlugin from "@fullcalendar/daygrid";
import timeGridPlugin from "@fullcalendar/timegrid";
import interactionPlugin from "@fullcalendar/interaction";

import { aiApi, employeesApi, eventsApi, notificationsApi } from "../api";
import { useAuth } from "../contexts/AuthContext";
import type {
  ActivityPriority,
  ActivityStatus,
  ActivityType,
  EmployeeResponse,
  EventResponse,
  EventUpdate,
} from "../types";
import {
  buildCSV,
  buildICS,
  dayKey,
  daysFromToday,
  downloadFile,
  formatDate,
  isOverdue,
  isUpcoming,
  relativeDay,
  timesOverlap,
  toISODate,
  todayISO,
  weekdayShort,
} from "../utils/calendar";
import {
  ACTIVITY_TYPES,
  PRIORITIES,
  STATUS_FLOW,
  asStatus,
  buildPreviewEvents,
  normalizeEvent,
  readPreviewEvents,
  typeClass,
  typeIcons,
  writePreviewEvents,
} from "./calendarData";

import "./CalendarPage.css";

interface FormState {
  title: string;
  date: string;
  type: ActivityType;
  person: string;
  description: string;
  location: string;
  priority: ActivityPriority;
  status: ActivityStatus;
  allDay: boolean;
  startTime: string;
  endTime: string;
  notify: boolean;
}

const emptyForm: FormState = {
  title: "",
  date: "",
  type: "Academic",
  person: "",
  description: "",
  location: "",
  priority: "Medium",
  status: "Planned",
  allDay: true,
  startTime: "10:00",
  endTime: "11:30",
  notify: true,
};

type Toast = { id: number; tone: "success" | "error" | "info"; text: string };
type ViewRange = { start: string; end: string; label: string };

export default function CalendarPage() {
  const { user } = useAuth();

  const [events, setEvents] = useState<EventResponse[]>([]);
  const [facultyList, setFacultyList] = useState<EmployeeResponse[]>([]);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [source, setSource] = useState<"live" | "preview">("live");

  const [form, setForm] = useState<FormState>(emptyForm);
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});
  const [editorOpen, setEditorOpen] = useState(false);
  const [editorMode, setEditorMode] = useState<"create" | "edit">("create");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [selectedDay, setSelectedDay] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const [query, setQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState<ActivityType[]>([]);
  const [personFilter, setPersonFilter] = useState("");
  const [upcomingOnly, setUpcomingOnly] = useState(false);

  const [viewRange, setViewRange] = useState<ViewRange>({
    start: todayISO(),
    end: todayISO(),
    label: new Date().toLocaleDateString("en-IN", { month: "long", year: "numeric" }),
  });

  const [aiInsight, setAiInsight] = useState({
    text: "Reading the department calendar…",
    fallback: false,
    loading: true,
  });

  const [toasts, setToasts] = useState<Toast[]>([]);
  const calendarRef = useRef<any>(null);
  const toastSeq = useRef(0);

  // Role comes from the authenticated user - reading an undefined localStorage
  // key used to make every visitor look like an admin.
  const role = (user?.role ?? "").toUpperCase();
  const canManage = ["ADMIN", "HOD", "HEAD"].some((part) => role.includes(part));
  const myName = (user?.name ?? "").trim();

  /* =========================================================
     TOASTS (replaces alert() / confirm() popups)
  ========================================================= */

  const pushToast = useCallback((text: string, tone: Toast["tone"] = "info") => {
    const id = ++toastSeq.current;
    setToasts((current) => [...current, { id, tone, text }]);
    window.setTimeout(() => {
      setToasts((current) => current.filter((toast) => toast.id !== id));
    }, 4200);
  }, []);

  /* =========================================================
     LOAD - live API first, clearly labelled preview fallback
  ========================================================= */

  const loadCalendar = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const [eventData, facultyData] = await Promise.all([
        eventsApi.getAll(),
        employeesApi.getAll().catch(() => [] as EmployeeResponse[]),
      ]);

      setEvents((eventData ?? []).map(normalizeEvent));
      setFacultyList(facultyData ?? []);
      setSource("live");
    } catch (err: any) {
      const cached = readPreviewEvents();
      const preview = cached?.length ? cached : buildPreviewEvents();
      if (!cached?.length) writePreviewEvents(preview);

      setEvents(preview);
      setFacultyList([]);
      setSource("preview");
      setError(err?.message || "The calendar service is unreachable.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadCalendar();
  }, [loadCalendar]);

  // Lock the page behind a modal and allow Escape to dismiss it.
  useEffect(() => {
    if (!editorOpen && !selectedEventId) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      if (editorOpen) {
        setEditorOpen(false);
        setEditingId(null);
        setFormErrors({});
        setForm(emptyForm);
      } else {
        setSelectedEventId(null);
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = previous;
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [editorOpen, selectedEventId]);

  /* =========================================================
     DERIVED DATA
  ========================================================= */

  const facultyOptions = useMemo(() => {
    const names = new Set<string>();
    facultyList.forEach((faculty) => faculty.name && names.add(faculty.name));
    events.forEach((event) => event.person && names.add(event.person));
    return [...names].sort((a, b) => a.localeCompare(b));
  }, [events, facultyList]);

  const matchesFilters = useCallback(
    (event: EventResponse) => {
      if (typeFilter.length && !typeFilter.includes(event.type as ActivityType)) return false;
      if (personFilter && event.person !== personFilter) return false;
      if (upcomingOnly && !isUpcoming(event.date)) return false;
      if (query.trim()) {
        const haystack = [
          event.title,
          event.person,
          event.location,
          event.description,
          event.type,
          event.status,
        ]
          .join(" ")
          .toLowerCase();
        if (!haystack.includes(query.trim().toLowerCase())) return false;
      }
      return true;
    },
    [personFilter, query, typeFilter, upcomingOnly]
  );

  const filteredEvents = useMemo(
    () => events.filter(matchesFilters),
    [events, matchesFilters]
  );

  const withinViewRange = useCallback(
    (event: EventResponse) => {
      const date = toISODate(event.date);
      return date >= viewRange.start && date <= viewRange.end;
    },
    [viewRange.end, viewRange.start]
  );

  const visibleEvents = useMemo(
    () => filteredEvents.filter(withinViewRange),
    [filteredEvents, withinViewRange]
  );

  const conflictIds = useMemo(() => {
    const byDayPerson = new Map<string, EventResponse[]>();
    filteredEvents.forEach((event) => {
      if (event.all_day === false) {
        const key = `${toISODate(event.date)}|${event.person}`;
        byDayPerson.set(key, [...(byDayPerson.get(key) ?? []), event]);
      }
    });

    const conflicts = new Set<string>();
    byDayPerson.forEach((group) => {
      for (let i = 0; i < group.length; i += 1) {
        for (let j = i + 1; j < group.length; j += 1) {
          if (timesOverlap(group[i], group[j])) {
            conflicts.add(String(group[i].id));
            conflicts.add(String(group[j].id));
          }
        }
      }
    });
    return conflicts;
  }, [filteredEvents]);

  const eventsByDay = useMemo(() => {
    const map = new Map<string, EventResponse[]>();
    filteredEvents.forEach((event) => {
      const key = toISODate(event.date);
      map.set(key, [...(map.get(key) ?? []), event]);
    });
    return map;
  }, [filteredEvents]);

  const stats = useMemo(() => {
    const today = todayISO();
    const monthKey = today.slice(0, 7);
    const viewMonthKey = viewRange.start.slice(0, 7);

    const inDays = (event: EventResponse, days: number) => {
      const diff = daysFromToday(event.date);
      return diff !== null && diff >= 0 && diff <= days;
    };

    return {
      total: events.length,
      viewMonth: events.filter((event) => toISODate(event.date).startsWith(viewMonthKey)).length,
      next7: events.filter((event) => inDays(event, 7)).length,
      overdue: events.filter((event) => isOverdue(event.date, event.status)).length,
      review: events.filter((event) => asStatus(event.status) === "Review").length,
      completedMonth: events.filter(
        (event) =>
          asStatus(event.status) === "Completed" && toISODate(event.date).startsWith(monthKey)
      ).length,
      unassigned: events.filter((event) => !event.person).length,
      recordedPast: events.filter((event) => toISODate(event.date) < today).length,
    };
  }, [events, viewRange.start]);

  const upcomingEvents = useMemo(
    () =>
      events
        .filter((event) => isUpcoming(event.date))
        .sort((a, b) => toISODate(a.date).localeCompare(toISODate(b.date)))
        .slice(0, 6),
    [events]
  );

  const dayEvents = useMemo(() => {
    if (!selectedDay) return [];
    return (eventsByDay.get(selectedDay) ?? []).sort((a, b) =>
      (a.start_time || "99:99").localeCompare(b.start_time || "99:99")
    );
  }, [eventsByDay, selectedDay]);

  const workload = useMemo(() => {
    const counts = new Map<string, number>();
    filteredEvents.forEach((event) => {
      const person = event.person || "Unassigned";
      counts.set(person, (counts.get(person) ?? 0) + 1);
    });
    const max = Math.max(1, ...counts.values());
    return [...counts.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([person, count]) => ({ person, count, share: Math.round((count / max) * 100) }));
  }, [filteredEvents]);

  const typeBreakdown = useMemo(
    () =>
      ACTIVITY_TYPES.map((type) => ({
        type,
        count: events.filter((event) => event.type === type).length,
      })),
    [events]
  );

  const selectedEvent = useMemo(
    () => events.find((event) => String(event.id) === String(selectedEventId)) ?? null,
    [events, selectedEventId]
  );

  /* =========================================================
     AI / LOCAL INSIGHT
  ========================================================= */

  const localInsight = useCallback(() => {
    const busiest = [...eventsByDay.entries()].sort((a, b) => b[1].length - a[1].length)[0];
    const load = workload[0];
    const parts: string[] = [];

    if (stats.next7 > 0) parts.push(`${stats.next7} activity(ies) fall in the next 7 days`);
    if (busiest && busiest[1].length > 1)
      parts.push(
        `${formatDate(busiest[0])} (${weekdayShort(busiest[0])}) is the busiest day with ${
          busiest[1].length
        } scheduled`
      );
    if (load && load.count > 1)
      parts.push(`${load.person} carries the heaviest load (${load.count} activities)`);
    if (stats.overdue > 0)
      parts.push(
        `${stats.overdue} activity(ies) are past their date and not marked completed`
      );
    if (!parts.length)
      parts.push("the schedule is light right now — a good window to plan ahead");

    return parts.join(" · ") + ".";
  }, [eventsByDay, stats, workload]);

  useEffect(() => {
    if (loading) return;
    let cancelled = false;

    const run = async () => {
      setAiInsight((current) => ({ ...current, loading: true }));
      try {
        const insight = await aiApi.getCalendarInsights();
        if (cancelled) return;
        if (insight?.message) {
          setAiInsight({ text: insight.message, fallback: false, loading: false });
          return;
        }
        throw new Error("empty insight");
      } catch {
        if (cancelled) return;
        setAiInsight({ text: localInsight(), fallback: true, loading: false });
      }
    };

    run();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading, events.length, stats.next7]);

  /* =========================================================
     EDITOR
  ========================================================= */

  const closeEditor = () => {
    setEditorOpen(false);
    setEditingId(null);
    setFormErrors({});
    setForm(emptyForm);
  };

  const openCreate = (date = "") => {
    if (!canManage) {
      pushToast("Only HOD / Administrator can create department activities.", "error");
      return;
    }

    setEditorMode("create");
    setEditingId(null);
    setFormErrors({});
    setForm({
      ...emptyForm,
      date: toISODate(date) || selectedDay || todayISO(),
      person: myName && facultyOptions.includes(myName) ? myName : "",
    });
    setEditorOpen(true);
  };

  const openEdit = (event: EventResponse) => {
    if (!canManage) {
      pushToast("Only HOD / Administrator can edit department activities.", "error");
      return;
    }

    setEditorMode("edit");
    setEditingId(String(event.id));
    setFormErrors({});
    setForm({
      title: event.title ?? "",
      date: toISODate(event.date),
      type: (event.type as ActivityType) ?? "Academic",
      person: event.person ?? "",
      description: event.description ?? "",
      location: event.location ?? "",
      priority: (event.priority as ActivityPriority) ?? "Medium",
      status: asStatus(event.status),
      allDay: event.all_day !== false,
      startTime: event.start_time || "10:00",
      endTime: event.end_time || "11:30",
      notify: false,
    });
    setSelectedEventId(null);
    setEditorOpen(true);
  };

  const validateForm = (values: FormState) => {
    const errors: Record<string, string> = {};
    if (values.title.trim().length < 4)
      errors.title = "Give the activity a clear title (4+ characters).";
    if (!toISODate(values.date)) errors.date = "Pick a valid activity date.";
    if (!values.person.trim()) errors.person = "Assign a responsible faculty member.";
    if (!values.allDay) {
      if (!values.startTime) errors.startTime = "Add a start time.";
      if (!values.endTime) errors.endTime = "Add an end time.";
      if (values.startTime && values.endTime && values.endTime <= values.startTime)
        errors.endTime = "End time must be after the start time.";
    }
    return errors;
  };

  const payloadFromForm = (values: FormState) => ({
    title: values.title.trim(),
    date: toISODate(values.date),
    type: values.type,
    person: values.person.trim(),
    description: values.description.trim(),
    location: values.location.trim(),
    priority: values.priority,
    status: values.status,
    all_day: values.allDay,
    start_time: values.allDay ? "" : values.startTime,
    end_time: values.allDay ? "" : values.endTime,
  });

  const persistPreview = (next: EventResponse[]) => {
    if (source === "preview") writePreviewEvents(next);
  };

  const handleSubmit = async () => {
    const errors = validateForm(form);
    setFormErrors(errors);
    if (Object.keys(errors).length > 0) return;

    setSaving(true);
    const payload = payloadFromForm(form);

    try {
      if (editorMode === "create") {
        const created =
          source === "preview"
            ? normalizeEvent({
                ...payload,
                id: `preview_${Date.now()}`,
                creator_id: user?.id ?? "preview",
                created_at: new Date().toISOString(),
              })
            : normalizeEvent(
                await eventsApi.create({ ...payload, notify_assignee: form.notify })
              );

        setEvents((previous) => {
          const next = [...previous, created];
          persistPreview(next);
          return next;
        });

        pushToast(`“${created.title}” added on ${formatDate(created.date)}.`, "success");

        if (form.notify && source === "live" && created.person) {
          try {
            await notificationsApi.create({
              title: `New activity: ${created.title}`,
              message: `${formatDate(created.date)} (${weekdayShort(created.date)})${
                created.all_day === false && created.start_time
                  ? ` at ${created.start_time}`
                  : ""
              } · ${created.location || "Venue to be confirmed"}`,
              type: "Event",
              priority: created.priority ?? "Medium",
              icon: typeIcons[created.type as ActivityType] ?? "📅",
              target_route: "/calendar",
            });
            pushToast(`Reminder queued for ${created.person}.`, "success");
          } catch {
            pushToast("Activity created, but the reminder could not be queued.", "info");
          }
        }
      } else if (editingId) {
        const updated =
          source === "preview"
            ? normalizeEvent({ ...payload, id: editingId })
            : normalizeEvent(await eventsApi.update(editingId, payload as EventUpdate));

        setEvents((previous) => {
          const next = previous.map((event) =>
            String(event.id) === editingId ? { ...event, ...updated } : event
          );
          persistPreview(next);
          return next;
        });

        pushToast(`“${updated.title}” updated.`, "success");
      }

      setSelectedDay(toISODate(form.date));
      closeEditor();
    } catch (err: any) {
      pushToast(err?.message || "Could not save this activity. Please try again.", "error");
    } finally {
      setSaving(false);
    }
  };

  const applyStatus = async (event: EventResponse, status: ActivityStatus) => {
    try {
      if (source === "live") await eventsApi.update(String(event.id), { status });
      setEvents((previous) => {
        const next = previous.map((item) =>
          String(item.id) === String(event.id) ? { ...item, status } : item
        );
        persistPreview(next);
        return next;
      });
      pushToast(`“${event.title}” moved to ${status}.`, "success");
    } catch (err: any) {
      pushToast(err?.message || "Status could not be updated.", "error");
    }
  };

  const handleDelete = async () => {
    if (!selectedEvent || !canManage) return;

    setDeleting(true);
    try {
      if (source === "live") await eventsApi.delete(String(selectedEvent.id));
      setEvents((previous) => {
        const next = previous.filter(
          (item) => String(item.id) !== String(selectedEvent.id)
        );
        persistPreview(next);
        return next;
      });
      pushToast(`“${selectedEvent.title}” deleted.`, "success");
      setSelectedEventId(null);
      setConfirmDelete(false);
    } catch (err: any) {
      pushToast(err?.message || "The activity could not be deleted.", "error");
    } finally {
      setDeleting(false);
    }
  };

  /* =========================================================
     CALENDAR INTERACTION
  ========================================================= */

  const calendarEvents = useMemo(
    () =>
      filteredEvents.map((event) => {
        const type = (event.type as ActivityType) ?? "Academic";
        const timed = event.all_day === false && !!event.start_time;
        const offset = daysFromToday(event.date);

        const classNames = [
          "hiera-event",
          typeClass[type] ?? "academic",
          asStatus(event.status) === "Completed" ? "is-done" : "",
          offset !== null && offset < 0 ? "is-past" : "",
          conflictIds.has(String(event.id)) ? "has-conflict" : "",
        ].filter(Boolean);

        return {
          id: String(event.id),
          title: event.title,
          start: timed
            ? `${toISODate(event.date)}T${event.start_time}`
            : toISODate(event.date),
          end:
            timed && event.end_time
              ? `${toISODate(event.date)}T${event.end_time}`
              : undefined,
          allDay: !timed,
          classNames,
          extendedProps: {
            type: event.type,
            person: event.person,
            description: event.description,
            location: event.location,
          },
        };
      }),
    [conflictIds, filteredEvents]
  );

  const handleDatesSet = useCallback((info: any) => {
    const lastDay = new Date(new Date(info.end).getTime() - 86_400_000);
    setViewRange({
      start: dayKey(new Date(info.start)),
      end: dayKey(lastDay),
      label: info.view?.title ?? "",
    });
  }, []);

  const handleDateClick = (info: any) => {
    const key = dayKey(info.date);
    setSelectedDay(key);
    if (canManage) openCreate(key);
  };

  const handleEventClick = (info: any) => {
    info.jsEvent?.preventDefault?.();
    const id = String(info.event?.id ?? "");
    const event = events.find((item) => String(item.id) === id);
    if (event) {
      setSelectedEventId(id);
      setConfirmDelete(false);
      setSelectedDay(toISODate(event.date));
    }
  };

  const handleEventDrop = async (info: any) => {
    const id = String(info.event?.id ?? "");
    const original = events.find((event) => String(event.id) === id);

    if (!canManage || !original) {
      info.revert?.();
      if (!canManage) pushToast("Only the HOD desk can reschedule activities.", "error");
      return;
    }

    const newDate = dayKey(info.event.start);
    if (newDate === toISODate(original.date)) return;

    setEvents((previous) => {
      const next = previous.map((event) =>
        String(event.id) === id ? { ...event, date: newDate } : event
      );
      persistPreview(next);
      return next;
    });

    if (source === "live") {
      try {
        await eventsApi.update(id, { date: newDate });
        pushToast(`“${original.title}” moved to ${formatDate(newDate)}.`, "success");
      } catch (err: any) {
        setEvents((previous) => {
          const next = previous.map((event) =>
            String(event.id) === id ? { ...event, date: toISODate(original.date) } : event
          );
          persistPreview(next);
          return next;
        });
        info.revert?.();
        pushToast(err?.message || "Reschedule failed — the activity moved back.", "error");
      }
    } else {
      pushToast(`Preview only: “${original.title}” moved to ${formatDate(newDate)}.`, "info");
    }
  };

  const dayCellClassNames = useCallback(
    (info: any) => {
      const key = dayKey(info.date);
      const count = eventsByDay.get(key)?.length ?? 0;
      return [
        count > 0 ? "has-events" : "",
        count > 2 ? "is-busy" : "",
        key === selectedDay ? "is-selected" : "",
      ].filter(Boolean);
    },
    [eventsByDay, selectedDay]
  );

  const shift = (direction: "prev" | "next" | "today") => {
    const api = calendarRef.current?.getApi();
    if (!api) return;
    if (direction === "today") api.today();
    else api[direction]();
  };

  /* =========================================================
     EXPORTS
  ========================================================= */

  const exportICS = () => {
    if (visibleEvents.length === 0) {
      pushToast("Nothing to export in the current view.", "info");
      return;
    }
    downloadFile(
      `hiera-sync-calendar-${viewRange.start}.ics`,
      buildICS(visibleEvents),
      "text/calendar"
    );
    pushToast(`Exported ${visibleEvents.length} activities to .ics.`, "success");
  };

  const exportCSV = () => {
    if (visibleEvents.length === 0) {
      pushToast("Nothing to export in the current view.", "info");
      return;
    }
    downloadFile(
      `hiera-sync-calendar-${viewRange.start}.csv`,
      buildCSV(
        visibleEvents.map((event) => ({ ...event, date: toISODate(event.date) })),
        [
          { key: "date", label: "Date" },
          { key: "title", label: "Activity" },
          { key: "type", label: "Type" },
          { key: "person", label: "Responsible Faculty" },
          { key: "location", label: "Location" },
          { key: "start_time", label: "Start" },
          { key: "end_time", label: "End" },
          { key: "priority", label: "Priority" },
          { key: "status", label: "Status" },
        ]
      ),
      "text/csv"
    );
    pushToast(`Exported ${visibleEvents.length} rows to CSV.`, "success");
  };

  const exportSingleICS = (event: EventResponse) => {
    downloadFile(
      `${event.title.toLowerCase().replace(/[^a-z0-9]+/g, "-")}.ics`,
      buildICS([event]),
      "text/calendar"
    );
    pushToast("Calendar invite downloaded.", "success");
  };

  const toggleType = (type: ActivityType) =>
    setTypeFilter((current) =>
      current.includes(type) ? current.filter((item) => item !== type) : [...current, type]
    );

  const resetFilters = () => {
    setQuery("");
    setTypeFilter([]);
    setPersonFilter("");
    setUpcomingOnly(false);
  };

  const filtersActive =
    query.trim() !== "" || typeFilter.length > 0 || personFilter !== "" || upcomingOnly;

  /* =========================================================
     UI
  ========================================================= */

  return (
    <div className="calendar-page hs-page">
      <header className="calendar-header">
        <div className="calendar-heading">
          <div className="calendar-main-icon" aria-hidden="true">
            🗓
          </div>

          <div className="calendar-title-area">
            <div className="department-label">SBJIT Nagpur · CSE (AI &amp; ML) Department</div>
            <h1>Academic Workflow Calendar</h1>
            <p>
              Plan, assign, review and track department activities from one calendar. Drag an
              activity to reschedule it, or click a day to plan ahead.
            </p>
          </div>
        </div>

        <div className="header-actions">
          <div className={`role-badge ${canManage ? "is-admin" : "is-faculty"}`}>
            <span className="online-dot" aria-hidden="true" />
            {canManage ? "Department Admin" : "Faculty Member"}
          </div>

          <div className="month-switch">
            <button type="button" onClick={() => shift("prev")} aria-label="Previous period">
              ‹
            </button>
            <span className="month-switch-label">{viewRange.label}</span>
            <button type="button" onClick={() => shift("next")} aria-label="Next period">
              ›
            </button>
            <button
              type="button"
              className="month-switch-today"
              onClick={() => shift("today")}
              aria-label="Jump to today"
            >
              Today
            </button>
          </div>

          {canManage && (
            <button className="primary-btn" onClick={() => openCreate()}>
              <span aria-hidden="true">＋</span>
              Create Activity
            </button>
          )}
        </div>
      </header>

      {source === "preview" ? (
        <div className="calendar-error" role="status">
          <div>
            <strong>Offline preview</strong>
            <span>
              {error} The calendar service is not reachable, so this screen runs on local preview
              data. Anything you change is kept in this browser until the API responds.
            </span>
          </div>
          <button onClick={loadCalendar}>Retry</button>
        </div>
      ) : (
        error && (
          <div className="calendar-error" role="alert">
            <div>
              <strong>Calendar error</strong>
              <span>{error}</span>
            </div>
            <button onClick={loadCalendar}>Retry</button>
          </div>
        )
      )}

      {/* ---------- STATS BENTO ---------- */}
      <section className="calendar-stats" aria-label="Calendar statistics">
        <article className="stat-card stat-card--hero">
          <div className="stat-hero-top">
            <div>
              <span className="hs-kicker">In view · {viewRange.label}</span>
              <strong className="hs-stat-value">{stats.viewMonth}</strong>
            </div>
            <div className="stat-hero-icon" aria-hidden="true">
              🗓
            </div>
          </div>

          <div className="stat-breakdown">
            {typeBreakdown.map((item) => (
              <button
                key={item.type}
                type="button"
                className={`breakdown-row ${typeClass[item.type]}`}
                onClick={() => toggleType(item.type)}
                aria-pressed={typeFilter.includes(item.type)}
                title={`Filter the calendar by ${item.type}`}
              >
                <span className="breakdown-label">
                  <i className="dot" aria-hidden="true" />
                  {item.type}
                </span>
                <span className="breakdown-bar">
                  <i
                    style={{
                      width: `${
                        item.count
                          ? Math.max(10, (item.count / Math.max(1, stats.total)) * 100)
                          : 0
                      }%`,
                    }}
                  />
                </span>
                <span className="breakdown-count hs-num">{item.count}</span>
              </button>
            ))}
          </div>
        </article>

        <article className="stat-card">
          <div className="stat-icon violet" aria-hidden="true">
            ▦
          </div>
          <div className="stat-info">
            <span>Total activities</span>
            <strong className="hs-num">{stats.total}</strong>
            <small>{stats.recordedPast} recorded before today</small>
          </div>
        </article>

        <article className="stat-card">
          <div className="stat-icon blue" aria-hidden="true">
            ⏱
          </div>
          <div className="stat-info">
            <span>Next 7 days</span>
            <strong className="hs-num">{stats.next7}</strong>
            <small>Immediate department workload</small>
          </div>
        </article>

        <article className="stat-card">
          <div className="stat-icon orange" aria-hidden="true">
            👁
          </div>
          <div className="stat-info">
            <span>Awaiting review</span>
            <strong className="hs-num">{stats.review}</strong>
            <small>Flagged for the HOD desk</small>
          </div>
        </article>

        <article className="stat-card">
          <div className="stat-icon teal" aria-hidden="true">
            ✓
          </div>
          <div className="stat-info">
            <span>Done this month</span>
            <strong className="hs-num">{stats.completedMonth}</strong>
            <small>Closed out by the team</small>
          </div>
        </article>

        <article className={`stat-card ${stats.overdue ? "is-alert" : ""}`}>
          <div className="stat-icon rose" aria-hidden="true">
            !
          </div>
          <div className="stat-info">
            <span>Overdue</span>
            <strong className="hs-num">{stats.overdue}</strong>
            <small>{stats.unassigned} without an owner</small>
          </div>
        </article>
      </section>

      {/* ---------- FILTER BAR ---------- */}
      <section className="calendar-toolbar" aria-label="Calendar filters and exports">
        <div className="toolbar-search">
          <span aria-hidden="true">🔍</span>
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search activities, faculty, venues…"
            aria-label="Search activities"
          />
          {query && (
            <button type="button" onClick={() => setQuery("")} aria-label="Clear search">
              ×
            </button>
          )}
        </div>

        <div className="toolbar-chips" role="group" aria-label="Filter by activity type">
          {ACTIVITY_TYPES.map((type) => (
            <button
              key={type}
              type="button"
              className={`filter-chip ${typeClass[type]} ${
                typeFilter.includes(type) ? "is-on" : ""
              }`}
              onClick={() => toggleType(type)}
              aria-pressed={typeFilter.includes(type)}
            >
              <i className="dot" aria-hidden="true" />
              {type}
            </button>
          ))}
        </div>

        <label className="toolbar-select">
          <span>Faculty</span>
          <select value={personFilter} onChange={(event) => setPersonFilter(event.target.value)}>
            <option value="">Everyone</option>
            {facultyOptions.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </label>

        <button
          type="button"
          className={`toolbar-toggle ${upcomingOnly ? "is-on" : ""}`}
          onClick={() => setUpcomingOnly((value) => !value)}
          aria-pressed={upcomingOnly}
        >
          Upcoming only
        </button>

        {filtersActive && (
          <button type="button" className="toolbar-reset" onClick={resetFilters}>
            Reset
          </button>
        )}

        <div className="toolbar-spacer" />

        <span className="toolbar-count hs-num">
          {visibleEvents.length}
          <small> shown</small>
        </span>

        <button type="button" className="ghost-btn" onClick={exportICS}>
          ⤓ .ics
        </button>
        <button type="button" className="ghost-btn" onClick={exportCSV}>
          ⤓ CSV
        </button>
      </section>

      {/* ---------- MAIN LAYOUT ---------- */}
      <div className="calendar-layout">
        <section className="calendar-card" aria-label="Department calendar">
          <div className="section-header">
            <div className="section-heading">
              <div className="section-kicker">Department schedule</div>
              <h2>{canManage ? "Plan & manage activities" : "Department calendar"}</h2>
              <p>
                {canManage
                  ? "Click a day to schedule · drag an activity to reschedule · click it for details."
                  : "Click an activity for its full details and current review status."}
              </p>
            </div>

            <div className="legend" aria-hidden="true">
              <span>
                <i className="dot dot-academic" />
                Academic
              </span>
              <span>
                <i className="dot dot-meeting" />
                Meeting
              </span>
              <span>
                <i className="dot dot-workshop" />
                Workshop
              </span>
              <span>
                <i className="dot dot-department" />
                Department
              </span>
              <span>
                <i className="dot dot-research" />
                Research
              </span>
            </div>
          </div>

          <div className="calendar-wrapper">
            {loading ? (
              <div className="calendar-loading">
                <div className="loader" />
                <span>Loading department calendar…</span>
              </div>
            ) : (
              <FullCalendar
                ref={calendarRef}
                plugins={[dayGridPlugin, timeGridPlugin, interactionPlugin]}
                initialView="dayGridMonth"
                height="auto"
                events={calendarEvents}
                dateClick={handleDateClick}
                eventClick={handleEventClick}
                eventDrop={handleEventDrop}
                datesSet={handleDatesSet}
                dayCellClassNames={dayCellClassNames}
                dayMaxEventRows={3}
                dayMaxEvents={4}
                eventDisplay="block"
                fixedWeekCount={false}
                expandRows
                nowIndicator
                navLinks
                showNonCurrentDates
                editable={canManage}
                eventStartEditable={canManage}
                eventDurationEditable={false}
                firstDay={1}
                allDayText="Full day"
                moreLinkText={(count: number) => `+${count} more`}
                slotMinTime="07:00:00"
                slotMaxTime="20:00:00"
                slotDuration="00:30:00"
                slotLabelFormat={{ hour: "2-digit", minute: "2-digit", meridiem: "short" }}
                eventTimeFormat={{ hour: "2-digit", minute: "2-digit", meridiem: "short" }}
                dayHeaderFormat={{ weekday: "short" }}
                headerToolbar={{
                  left: "prev,next today",
                  center: "title",
                  right: "dayGridMonth,timeGridWeek,timeGridDay",
                }}
                buttonText={{ today: "Today", month: "Month", week: "Week", day: "Day" }}
                eventContent={(arg: any) => (
                  <span className="hiera-event-inner">
                    <span className="hiera-event-title">{arg.event.title}</span>
                    {arg.timeText ? (
                      <span className="hiera-event-time">{arg.timeText}</span>
                    ) : null}
                    {arg.event.extendedProps?.person ? (
                      <span className="hiera-event-person">
                        {String(arg.event.extendedProps.person).split(" ").slice(-1)[0]}
                      </span>
                    ) : null}
                  </span>
                )}
              />
            )}
          </div>

          <footer className="calendar-footnote">
            <span>
              {canManage
                ? "Admin view — you can create, reschedule, review and close out activities."
                : "Read-only for faculty: reschedule requests go to the HOD desk."}
            </span>
            <span className="hs-kicker">
              {source === "preview" ? "Offline preview data" : "Live · Firestore"}
            </span>
          </footer>
        </section>

        {/* ---------- SIDEBAR BENTO ---------- */}
        <aside className="calendar-sidebar">
          <div className="role-card">
            <div className="role-card-icon" aria-hidden="true">
              🛡
            </div>
            <small>Your calendar role</small>
            <h3>{canManage ? "Department Admin" : "Faculty Member"}</h3>
            <div className="role-permission">
              <span aria-hidden="true">✓</span>
              {canManage
                ? "Create, reschedule, review and close department activities."
                : "View activities, read details and export the schedule."}
            </div>
          </div>

          <div className="day-card">
            <div className="upcoming-heading">
              <div>
                <div className="section-kicker">Selected day</div>
                <h2>{selectedDay ? formatDate(selectedDay) : "Pick a day"}</h2>
              </div>
              <span className="count-badge hs-num">{dayEvents.length}</span>
            </div>

            {selectedDay && (
              <p className="day-card-meta">
                {weekdayShort(selectedDay)} · {relativeDay(selectedDay)}
              </p>
            )}

            {selectedDay && dayEvents.length === 0 && (
              <p className="day-card-empty">Nothing scheduled on this day yet.</p>
            )}

            {dayEvents.length > 0 && (
              <ul className="day-card-list">
                {dayEvents.map((event) => (
                  <li key={event.id}>
                    <button type="button" onClick={() => setSelectedEventId(String(event.id))}>
                      <span
                        className={`upcoming-icon ${
                          typeClass[(event.type as ActivityType) ?? "Academic"]
                        }`}
                        aria-hidden="true"
                      >
                        {typeIcons[(event.type as ActivityType) ?? "Academic"]}
                      </span>
                      <span className="day-card-body">
                        <strong>{event.title}</strong>
                        <small>
                          {event.all_day === false && event.start_time
                            ? `${event.start_time}–${event.end_time || "—"} · `
                            : ""}
                          {event.person || "Unassigned"} · {asStatus(event.status)}
                        </small>
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}

            {canManage && (
              <button className="day-card-add" onClick={() => openCreate(selectedDay)}>
                ＋ Schedule on {selectedDay ? formatDate(selectedDay) : "a day"}
              </button>
            )}
          </div>

          <div className="upcoming-card">
            <div className="upcoming-heading">
              <div>
                <div className="section-kicker">Next activities</div>
                <h2>Upcoming</h2>
              </div>
              <span className="count-badge hs-num">{upcomingEvents.length}</span>
            </div>

            {upcomingEvents.length === 0 ? (
              <div className="empty-upcoming">
                <div aria-hidden="true">📅</div>
                <span>No upcoming activities — the department is clear.</span>
              </div>
            ) : (
              <div className="upcoming-list">
                {upcomingEvents.map((event) => {
                  const type = (event.type as ActivityType) ?? "Academic";
                  return (
                    <button
                      className="upcoming-item"
                      key={event.id}
                      onClick={() => {
                        setSelectedEventId(String(event.id));
                        setSelectedDay(toISODate(event.date));
                      }}
                    >
                      <span className={`upcoming-icon ${typeClass[type]}`} aria-hidden="true">
                        {typeIcons[type]}
                      </span>

                      <span className="upcoming-content">
                        <span className="upcoming-meta">
                          {type} · {relativeDay(event.date)}
                        </span>
                        <strong>{event.title}</strong>
                        <span className="upcoming-line">
                          📅 {formatDate(event.date)}
                          {event.all_day === false && event.start_time
                            ? ` · 🕘 ${event.start_time}`
                            : ""}
                        </span>
                        <span className="upcoming-line">👤 {event.person || "Unassigned"}</span>
                      </span>

                      <span className="upcoming-arrow" aria-hidden="true">
                        →
                      </span>
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          <div className="load-card">
            <div className="upcoming-heading">
              <div>
                <div className="section-kicker">Balance check</div>
                <h2>Faculty workload</h2>
              </div>
            </div>

            {workload.length === 0 ? (
              <p className="day-card-empty">No assignments match the current filter.</p>
            ) : (
              <ul className="load-list">
                {workload.map((row) => (
                  <li key={row.person}>
                    <div className="load-row">
                      <span className="load-name">{row.person}</span>
                      <span className="load-count hs-num">{row.count}</span>
                    </div>
                    <span className="load-bar">
                      <i style={{ width: `${row.share}%` }} />
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="ai-card">
            <div className="ai-card-head">
              <span className="ai-orb" aria-hidden="true" />
              <div>
                <div className="section-kicker">HiéraSync AI</div>
                <h2>Schedule insight</h2>
              </div>
            </div>

            <p className={aiInsight.fallback ? "is-fallback" : ""}>
              {aiInsight.loading ? "Reading the department calendar…" : aiInsight.text}
            </p>

            <small>
              {aiInsight.fallback
                ? "Heuristic summary computed locally in the browser."
                : "Generated by the AI service from live calendar data."}
            </small>
          </div>
        </aside>
      </div>

      {/* ---------- CREATE / EDIT MODAL ---------- */}
      {editorOpen && (
        <div className="modal-overlay" onMouseDown={closeEditor}>
          <div
            className="activity-modal"
            role="dialog"
            aria-modal="true"
            aria-label={editorMode === "create" ? "Create activity" : "Edit activity"}
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div className="modal-header">
              <div>
                <div className="section-kicker">
                  {editorMode === "create" ? "Department schedule" : "Edit schedule entry"}
                </div>
                <h2>{editorMode === "create" ? "Create Activity" : "Edit Activity"}</h2>
                <p>
                  {editorMode === "create"
                    ? "Add an academic workflow activity and notify the owner."
                    : "Update the plan, timing or review status."}
                </p>
              </div>

              <button className="close-btn" onClick={closeEditor} aria-label="Close dialog">
                ×
              </button>
            </div>

            <div className="form-grid">
              <label className={formErrors.title ? "has-error" : ""}>
                Activity title *
                <input
                  value={form.title}
                  onChange={(event) => setForm({ ...form, title: event.target.value })}
                  placeholder="e.g. Final Year Project Review"
                  autoFocus
                />
                <em>{formErrors.title}</em>
              </label>

              <label className={formErrors.date ? "has-error" : ""}>
                Activity date *
                <input
                  type="date"
                  value={form.date}
                  onChange={(event) => setForm({ ...form, date: event.target.value })}
                />
                <em>{formErrors.date}</em>
              </label>

              <label>
                Activity type *
                <select
                  value={form.type}
                  onChange={(event) =>
                    setForm({ ...form, type: event.target.value as ActivityType })
                  }
                >
                  {ACTIVITY_TYPES.map((type) => (
                    <option key={type} value={type}>
                      {type}
                    </option>
                  ))}
                </select>
              </label>

              <label className={formErrors.person ? "has-error" : ""}>
                Responsible faculty *
                <select
                  value={form.person}
                  onChange={(event) => setForm({ ...form, person: event.target.value })}
                >
                  <option value="">Select responsible faculty</option>
                  {facultyOptions.map((name) => (
                    <option key={name} value={name}>
                      {name}
                    </option>
                  ))}
                </select>
                <em>{formErrors.person}</em>
              </label>

              <label>
                Priority
                <select
                  value={form.priority}
                  onChange={(event) =>
                    setForm({ ...form, priority: event.target.value as ActivityPriority })
                  }
                >
                  {PRIORITIES.map((priority) => (
                    <option key={priority} value={priority}>
                      {priority}
                    </option>
                  ))}
                </select>
              </label>

              <label>
                Workflow status
                <select
                  value={form.status}
                  onChange={(event) =>
                    setForm({ ...form, status: event.target.value as ActivityStatus })
                  }
                >
                  {STATUS_FLOW.map((status) => (
                    <option key={status} value={status}>
                      {status}
                    </option>
                  ))}
                </select>
              </label>

              <div className="time-block">
                <div className="time-block-head">
                  <span>Timing</span>
                  <label className="switch">
                    <input
                      type="checkbox"
                      checked={!form.allDay}
                      onChange={(event) => setForm({ ...form, allDay: !event.target.checked })}
                    />
                    <span>Set start / end time</span>
                  </label>
                </div>

                {form.allDay ? (
                  <p className="time-block-hint">
                    Treated as a full-day activity, so it shows in the month grid.
                  </p>
                ) : (
                  <div className="time-inputs">
                    <label className={formErrors.startTime ? "has-error" : ""}>
                      Start
                      <input
                        type="time"
                        value={form.startTime}
                        onChange={(event) =>
                          setForm({ ...form, startTime: event.target.value })
                        }
                      />
                      <em>{formErrors.startTime}</em>
                    </label>
                    <label className={formErrors.endTime ? "has-error" : ""}>
                      End
                      <input
                        type="time"
                        value={form.endTime}
                        onChange={(event) => setForm({ ...form, endTime: event.target.value })}
                      />
                      <em>{formErrors.endTime}</em>
                    </label>
                  </div>
                )}
              </div>

              <label className="full-field">
                Location
                <input
                  value={form.location}
                  onChange={(event) => setForm({ ...form, location: event.target.value })}
                  placeholder="e.g. AI Lab / Seminar Hall"
                />
              </label>

              <label className="full-field">
                Description
                <textarea
                  rows={3}
                  value={form.description}
                  onChange={(event) =>
                    setForm({ ...form, description: event.target.value })
                  }
                  placeholder="Agenda, expectations, evaluation criteria…"
                />
              </label>

              {editorMode === "create" && (
                <label className="switch full-field">
                  <input
                    type="checkbox"
                    checked={form.notify}
                    onChange={(event) => setForm({ ...form, notify: event.target.checked })}
                  />
                  <span>
                    Notify {form.person || "the assigned faculty"} in Notifications
                  </span>
                </label>
              )}
            </div>

            <div className="modal-footer">
              <span className="modal-footer-note">
                {form.date
                  ? `Scheduled for ${formatDate(form.date)}`
                  : "Pick a date to continue"}
              </span>
              <div className="modal-footer-actions">
                <button className="secondary-btn" onClick={closeEditor}>
                  Cancel
                </button>
                <button className="primary-btn" onClick={handleSubmit} disabled={saving}>
                  {saving
                    ? "Saving…"
                    : editorMode === "create"
                    ? "✓ Create Activity"
                    : "✓ Save changes"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ---------- EVENT DETAILS ---------- */}
      {selectedEvent && (
        <div
          className="modal-overlay"
          onMouseDown={() => {
            if (!deleting) setSelectedEventId(null);
          }}
        >
          <div
            className="details-modal"
            role="dialog"
            aria-modal="true"
            aria-label={selectedEvent.title}
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div
              className={`details-banner ${
                typeClass[(selectedEvent.type as ActivityType) ?? "Academic"]
              }`}
            >
              <span className="details-banner-icon" aria-hidden="true">
                {typeIcons[(selectedEvent.type as ActivityType) ?? "Academic"]}
              </span>

              <div className="details-banner-meta">
                <span className="activity-type">{selectedEvent.type || "Academic"}</span>
                <span className="activity-when">
                  {formatDate(selectedEvent.date)} · {weekdayShort(selectedEvent.date)} ·{" "}
                  {relativeDay(selectedEvent.date)}
                </span>
              </div>

              <button
                className="close-btn"
                disabled={deleting}
                onClick={() => setSelectedEventId(null)}
                aria-label="Close details"
              >
                ×
              </button>
            </div>

            <div className="details-body">
              <div className="details-tags">
                <span className={`pill pill--${asStatus(selectedEvent.status).toLowerCase()}`}>
                  {asStatus(selectedEvent.status)}
                </span>
                <span className="pill">{selectedEvent.priority ?? "Medium"} priority</span>
                {selectedEvent.all_day === false && selectedEvent.start_time ? (
                  <span className="pill">
                    🕘 {selectedEvent.start_time}–{selectedEvent.end_time || "—"}
                  </span>
                ) : (
                  <span className="pill">Full day</span>
                )}
                {conflictIds.has(String(selectedEvent.id)) && (
                  <span className="pill pill--conflict">Time clash with another activity</span>
                )}
              </div>

              <h2>{selectedEvent.title}</h2>

              <div className="detail-row">
                <span aria-hidden="true">📅</span>
                <div>
                  <small>Date</small>
                  <strong>
                    {formatDate(selectedEvent.date)} ({relativeDay(selectedEvent.date)})
                  </strong>
                </div>
              </div>

              <div className="detail-row">
                <span aria-hidden="true">👤</span>
                <div>
                  <small>Responsible faculty</small>
                  <strong>{selectedEvent.person || "Unassigned"}</strong>
                </div>
              </div>

              {selectedEvent.location && (
                <div className="detail-row">
                  <span aria-hidden="true">📍</span>
                  <div>
                    <small>Location</small>
                    <strong>{selectedEvent.location}</strong>
                  </div>
                </div>
              )}

              {selectedEvent.description && (
                <div className="description-box">
                  <small>Description</small>
                  <p>{selectedEvent.description}</p>
                </div>
              )}

              <div className="status-flow" role="list" aria-label="Workflow status">
                {STATUS_FLOW.map((status, index) => {
                  const currentIndex = STATUS_FLOW.indexOf(asStatus(selectedEvent.status));
                  const state =
                    index < currentIndex ? "done" : index === currentIndex ? "active" : "todo";
                  return (
                    <div className={`status-step is-${state}`} key={status} role="listitem">
                      <span className="status-dot" aria-hidden="true" />
                      <span>{status}</span>
                    </div>
                  );
                })}
              </div>

              {canManage && (
                <div className="status-actions">
                  {STATUS_FLOW.filter(
                    (status) => status !== asStatus(selectedEvent.status)
                  ).map((status) => (
                    <button
                      key={status}
                      type="button"
                      className="status-btn"
                      onClick={() => applyStatus(selectedEvent, status)}
                    >
                      Mark {status}
                    </button>
                  ))}
                </div>
              )}

              <div className="details-actions">
                {canManage && (
                  <button className="secondary-btn" onClick={() => openEdit(selectedEvent)}>
                    ✎ Edit activity
                  </button>
                )}
                <button className="secondary-btn" onClick={() => exportSingleICS(selectedEvent)}>
                  ⤓ Calendar invite
                </button>
              </div>

              {canManage ? (
                <div className="delete-section">
                  {confirmDelete ? (
                    <div className="delete-confirm">
                      <span>Delete “{selectedEvent.title}”? This cannot be undone.</span>
                      <div>
                        <button
                          className="ghost-btn"
                          onClick={() => setConfirmDelete(false)}
                          disabled={deleting}
                        >
                          Keep it
                        </button>
                        <button
                          className="delete-task-btn"
                          onClick={handleDelete}
                          disabled={deleting}
                        >
                          {deleting ? (
                            <>
                              <span className="delete-spinner" aria-hidden="true" />
                              Deleting…
                            </>
                          ) : (
                            <>🗑 Delete activity</>
                          )}
                        </button>
                      </div>
                    </div>
                  ) : (
                    <button className="delete-link" onClick={() => setConfirmDelete(true)}>
                      🗑 Delete activity
                    </button>
                  )}
                </div>
              ) : (
                <p className="readonly-note">
                  Need a change? Ask the HOD desk to reschedule or close out this activity.
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ---------- TOASTS ---------- */}
      {toasts.length > 0 && (
        <div className="calendar-toasts" role="status" aria-live="polite">
          {toasts.map((toast) => (
            <div key={toast.id} className={`toast toast--${toast.tone}`}>
              <span aria-hidden="true">
                {toast.tone === "success" ? "✓" : toast.tone === "error" ? "!" : "i"}
              </span>
              {toast.text}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
