import { FIXTURE_FEDERATION_ROWS, type FederationCountryRow } from "@/lib/fixtures/federation";

export const federation = {
  getProfile: async (): Promise<FederationCountryRow[]> => FIXTURE_FEDERATION_ROWS,
};
