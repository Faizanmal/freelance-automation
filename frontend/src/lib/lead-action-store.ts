/**
 * Cross-route source of truth for recent lead Save/Skip/Pitch actions.
 * Desk, /leads and /pipeline overlay this so a lagging findings GET cannot
 * disagree with an in-session write.
 */

export type LeadActionStatus = "save" | "skip" | "pitched" | "won" | null;

export type LeadActionOverride = {
  status: LeadActionStatus;
  gen: number;
  updatedAt: number;
};

type Listener = () => void;

const STORAGE_KEY = "signaldesk:lead-overrides:v1";

let overrides = new Map<number, LeadActionOverride>();
let writeEpoch = 0;
const listeners = new Set<Listener>();

function readStorage(): Map<number, LeadActionOverride> {
  if (typeof window === "undefined") return new Map();
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return new Map();
    const parsed = JSON.parse(raw) as Record<string, LeadActionOverride>;
    return new Map(
      Object.entries(parsed).map(([k, v]) => [
        Number(k),
        {
          status: v.status,
          gen: Number(v.gen) || 0,
          updatedAt: Number(v.updatedAt) || Date.now(),
        },
      ]),
    );
  } catch {
    return new Map();
  }
}

function persist() {
  if (typeof window === "undefined") return;
  try {
    const obj: Record<string, LeadActionOverride> = {};
    for (const [k, v] of overrides.entries()) obj[String(k)] = v;
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(obj));
  } catch {
    /* quota */
  }
}

if (typeof window !== "undefined") {
  overrides = readStorage();
}

function emit() {
  for (const listener of listeners) listener();
}

export function subscribeLeadActions(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function getLeadWriteEpoch(): number {
  return writeEpoch;
}

export function bumpLeadWriteEpoch(): number {
  writeEpoch += 1;
  return writeEpoch;
}

export function getLeadOverrides(): Map<number, LeadActionOverride> {
  return overrides;
}

export function setLeadOverride(jobId: number, status: LeadActionStatus, gen: number) {
  overrides.set(jobId, { status, gen, updatedAt: Date.now() });
  persist();
  bumpLeadWriteEpoch();
  emit();
}

export function clearLeadOverride(jobId: number) {
  if (!overrides.delete(jobId)) return;
  persist();
  emit();
}

export function applyLeadOverridesToItems<
  T extends { job_id: number; user_status?: LeadActionStatus | string | null },
>(items: T[]): T[] {
  if (overrides.size === 0) return items;
  return items.map((item) => {
    const over = overrides.get(item.job_id);
    if (!over) return item;
    if (item.user_status === over.status) {
      overrides.delete(item.job_id);
      persist();
      return item;
    }
    return { ...item, user_status: over.status };
  });
}
