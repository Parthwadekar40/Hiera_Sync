import { client } from './client';
import { 
  AIChatRequest, 
  AIChatResponse,
  AIDashboardSummaryResponse,
  AIReportResponse
} from '../types';

export const aiApi = {
  chat: (data: AIChatRequest) => client<AIChatResponse>('/ai/chat', { data }),
  getDashboardSummary: () => client<AIDashboardSummaryResponse>('/ai/dashboard-summary'),
  generateReport: () => client<AIReportResponse>('/ai/generate-report', { data: {} }),
  getCalendarInsights: () =>
    client<{ message: string; highlights?: string[]; source?: string }>(
      '/ai/calendar-insights'
    ),
  getApprovalSuggestions: () =>
    client<{
      message: string;
      suggestions?: { id: string; title: string; reason?: string }[];
    }>('/ai/approval-suggestions'),
  getNotificationSummary: () =>
    client<{ summary: string; message: string; total?: number; unread?: number }>(
      '/ai/notification-summary',
      { data: {} }
    ),
};
