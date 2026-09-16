import { client } from './client';
import type { 
  ApprovalCreate, 
  ApprovalUpdate,
  ApprovalResponse 
} from '../types';

export const approvalsApi = {
  getAll: () => client<ApprovalResponse[]>('/approvals'),
  create: (data: ApprovalCreate) => client<ApprovalResponse>('/approvals', { data }),
  update: (id: string, data: ApprovalUpdate) =>
    client<ApprovalResponse>(`/approvals/${id}`, { method: 'PUT', data }),
  approve: (id: string) => client<ApprovalResponse>(`/approvals/${id}/approve`, { method: 'PUT' }),
  reject: (id: string) => client<ApprovalResponse>(`/approvals/${id}/reject`, { method: 'PUT' }),
  delete: (id: string) => client<void>(`/approvals/${id}`, { method: 'DELETE' }),
};
