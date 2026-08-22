import { api } from './client';
import type { FederationCountryRow } from '@/lib/api/types';

export const federation = {
  getProfile: async (): Promise<FederationCountryRow[]> => api.get<FederationCountryRow[]>('/intelligence/federation'),
};
