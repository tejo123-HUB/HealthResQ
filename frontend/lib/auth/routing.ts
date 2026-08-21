import type { FacilityType, ScopeLevel } from "@/lib/api/types";

export function homePathForScope(scopeLevel: ScopeLevel, facilityType?: FacilityType | null): string {
  if (scopeLevel === "FACILITY") {
    if (facilityType === "WAREHOUSE") return "/warehouse";
    if (facilityType === "SHC") return "/shc";
    return "/phc";
  }
  if (scopeLevel === "DISTRICT") return "/district";
  if (scopeLevel === "STATE") return "/state";
  return "/national";
}
