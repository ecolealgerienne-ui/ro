/**
 * Types TypeScript miroirs des modèles Prisma backend.
 *
 * Ils ne sont PAS générés automatiquement (le backend ne sert pas l'OpenAPI
 * V1) : on les maintient à la main, alignés avec `backend/prisma/schema.prisma`
 * + les DTO `class-validator`. Si un champ change côté backend, mettre ce
 * fichier à jour.
 */

// ---------- Workshops ----------

export interface Workshop {
  id: string;
  name: string;
  city: string | null;
  certifications: string[];
  shiftStart: number;
  shiftEnd: number;
  workdays: number[];
  nOperators: number;
  transitionMatrix: number[][] | null;
  createdAt: string;
  updatedAt: string;
}

export interface WorkshopWithCount extends Workshop {
  _count: { machines: number; orders: number; versions: number };
}

export interface WorkshopDetail extends Workshop {
  machines: Machine[];
  clients: Client[];
  _count: { orders: number; versions: number };
}

// ---------- Machines / Operators / Resources ----------

export interface Machine {
  id: string;
  workshopId: string;
  machineIdInt: number;
  name: string;
  type: string | null;
  createdAt: string;
  updatedAt: string;
}

// ---------- Clients ----------

export interface Client {
  id: string;
  workshopId: string;
  name: string;
  tier: 1 | 2 | 3;
  certifications: string[];
  createdAt: string;
  updatedAt: string;
}

// ---------- Orders / Jobs / Operations ----------

export type OrderStatus = 'pending' | 'planned' | 'in_progress' | 'done' | 'cancelled';

export interface Operation {
  id: string;
  jobId: string;
  sequenceIdx: number;
  machineId: string;
  durationMin: number;
  familyId: number;
  qualifiedOperatorIds: number[];
}

export interface Job {
  id: string;
  jobIdInt: number;
  criticality: 1 | 2 | 3 | null;
  operations?: Operation[];
}

export interface OrderListItem {
  id: string;
  workshopId: string;
  clientId: string;
  orderRef: string;
  partRef: string;
  partFamilyId: number | null;
  quantity: number;
  deadline: string | null;
  status: OrderStatus;
  createdAt: string;
  updatedAt: string;
  client: Pick<Client, 'id' | 'name' | 'tier'>;
  job: Pick<Job, 'jobIdInt' | 'criticality'> | null;
}

// ---------- Versions ----------

export interface VersionListItem {
  id: string;
  versionNumber: number;
  parentVersionId: string | null;
  message: string;
  author: string;
  isActive: boolean;
  createdAt: string;
}

// ---------- Solve jobs ----------

export type SolveJobStatus = 'pending' | 'running' | 'done' | 'failed' | 'cancelled';

export interface SolveJob {
  id: string;
  workshopId: string;
  versionId: string | null;
  status: SolveJobStatus;
  config: Record<string, unknown>;
  result: Record<string, unknown> | null;
  confidenceScore: number | null;
  simulationVerdict: 'ACCEPT' | 'WARN' | 'REJECT' | null;
  errorMessage: string | null;
  attempts: number;
  startedAt: string | null;
  finishedAt: string | null;
  workerId: string | null;
  heartbeatAt: string | null;
  createdAt: string;
  updatedAt: string;
}

// ---------- Health ----------

export interface HealthStatus {
  status: 'ok' | 'degraded';
  uptime_s: number;
  database: 'up' | 'down';
  version: string;
  timestamp: string;
}
