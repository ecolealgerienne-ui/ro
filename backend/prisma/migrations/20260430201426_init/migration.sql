-- CreateEnum
CREATE TYPE "OrderStatus" AS ENUM ('pending', 'planned', 'in_progress', 'done', 'cancelled');

-- CreateEnum
CREATE TYPE "SolveJobStatus" AS ENUM ('pending', 'running', 'done', 'failed', 'cancelled');

-- CreateEnum
CREATE TYPE "AnomalyLevel" AS ENUM ('certain', 'probable', 'surprising');

-- CreateEnum
CREATE TYPE "AnomalyStatus" AS ENUM ('pending', 'resolved', 'ignored', 'excluded');

-- CreateTable
CREATE TABLE "workshops" (
    "id" UUID NOT NULL,
    "name" TEXT NOT NULL,
    "city" TEXT,
    "certifications" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "shift_start_minutes" INTEGER NOT NULL DEFAULT 360,
    "shift_end_minutes" INTEGER NOT NULL DEFAULT 1320,
    "workdays" INTEGER[] DEFAULT ARRAY[1, 2, 3, 4, 5]::INTEGER[],
    "n_operators" INTEGER NOT NULL DEFAULT 0,
    "transition_matrix" JSONB,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "workshops_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "machines" (
    "id" UUID NOT NULL,
    "workshop_id" UUID NOT NULL,
    "machine_id_int" INTEGER NOT NULL,
    "name" TEXT NOT NULL,
    "type" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "machines_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "operators" (
    "id" UUID NOT NULL,
    "workshop_id" UUID NOT NULL,
    "operator_id_int" INTEGER NOT NULL,
    "name" TEXT NOT NULL,
    "qualified_machines" INTEGER[] DEFAULT ARRAY[]::INTEGER[],
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "operators_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "shared_resources" (
    "id" UUID NOT NULL,
    "workshop_id" UUID NOT NULL,
    "resource_name" TEXT NOT NULL,
    "machine_ids_int" INTEGER[],
    "max_concurrent" INTEGER NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "shared_resources_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "machine_unavailability" (
    "id" UUID NOT NULL,
    "workshop_id" UUID NOT NULL,
    "machine_id" UUID NOT NULL,
    "periods" JSONB NOT NULL,
    "reason" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "machine_unavailability_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "clients" (
    "id" UUID NOT NULL,
    "workshop_id" UUID NOT NULL,
    "name" TEXT NOT NULL,
    "tier" INTEGER NOT NULL DEFAULT 2,
    "certifications" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "clients_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "orders" (
    "id" UUID NOT NULL,
    "workshop_id" UUID NOT NULL,
    "client_id" UUID NOT NULL,
    "order_ref" TEXT NOT NULL,
    "part_ref" TEXT NOT NULL,
    "part_family_id" INTEGER,
    "quantity" INTEGER NOT NULL DEFAULT 1,
    "deadline" TIMESTAMP(3),
    "status" "OrderStatus" NOT NULL DEFAULT 'pending',
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "orders_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "jobs" (
    "id" UUID NOT NULL,
    "order_id" UUID NOT NULL,
    "job_id_int" INTEGER NOT NULL,
    "criticality" INTEGER,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "jobs_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "operations" (
    "id" UUID NOT NULL,
    "job_id" UUID NOT NULL,
    "sequence_idx" INTEGER NOT NULL,
    "machine_id" UUID NOT NULL,
    "duration_min" INTEGER NOT NULL,
    "family_id" INTEGER NOT NULL DEFAULT 0,
    "qualified_operator_ids" INTEGER[] DEFAULT ARRAY[]::INTEGER[],
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "operations_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "soft_constraints" (
    "id" UUID NOT NULL,
    "workshop_id" UUID NOT NULL,
    "category" TEXT NOT NULL,
    "parameters" JSONB NOT NULL DEFAULT '{}',
    "weight_hint" DOUBLE PRECISION NOT NULL DEFAULT 0.5,
    "raw_nl_text" TEXT,
    "enabled" BOOLEAN NOT NULL DEFAULT true,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "soft_constraints_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "versions" (
    "id" UUID NOT NULL,
    "workshop_id" UUID NOT NULL,
    "version_number" INTEGER NOT NULL,
    "parent_version_id" UUID,
    "message" TEXT NOT NULL,
    "author" TEXT NOT NULL,
    "snapshot" JSONB NOT NULL,
    "is_active" BOOLEAN NOT NULL DEFAULT false,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "versions_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "solve_jobs" (
    "id" UUID NOT NULL,
    "workshop_id" UUID NOT NULL,
    "version_id" UUID,
    "status" "SolveJobStatus" NOT NULL DEFAULT 'pending',
    "config" JSONB NOT NULL DEFAULT '{}',
    "result" JSONB,
    "confidence_score" INTEGER,
    "simulation_verdict" TEXT,
    "error_message" TEXT,
    "attempts" INTEGER NOT NULL DEFAULT 0,
    "started_at" TIMESTAMP(3),
    "finished_at" TIMESTAMP(3),
    "worker_id" TEXT,
    "heartbeat_at" TIMESTAMP(3),
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "solve_jobs_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "schedules" (
    "id" UUID NOT NULL,
    "version_id" UUID NOT NULL,
    "makespan_min" INTEGER NOT NULL,
    "assignments" JSONB NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "schedules_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "preflight_sessions" (
    "id" UUID NOT NULL,
    "workshop_id" UUID NOT NULL,
    "file_name" TEXT NOT NULL,
    "file_hash" TEXT,
    "n_rows_total" INTEGER NOT NULL,
    "n_rows_imported" INTEGER NOT NULL DEFAULT 0,
    "imported_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "closed_at" TIMESTAMP(3),

    CONSTRAINT "preflight_sessions_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "anomalies" (
    "id" UUID NOT NULL,
    "session_id" UUID NOT NULL,
    "level" "AnomalyLevel" NOT NULL,
    "code" TEXT NOT NULL,
    "row_index" INTEGER NOT NULL,
    "column" TEXT,
    "raw_value" TEXT,
    "suggestion" TEXT,
    "status" "AnomalyStatus" NOT NULL DEFAULT 'pending',
    "resolution" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "anomalies_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "machines_workshop_id_idx" ON "machines"("workshop_id");

-- CreateIndex
CREATE UNIQUE INDEX "machines_workshop_id_machine_id_int_key" ON "machines"("workshop_id", "machine_id_int");

-- CreateIndex
CREATE INDEX "operators_workshop_id_idx" ON "operators"("workshop_id");

-- CreateIndex
CREATE UNIQUE INDEX "operators_workshop_id_operator_id_int_key" ON "operators"("workshop_id", "operator_id_int");

-- CreateIndex
CREATE UNIQUE INDEX "shared_resources_workshop_id_resource_name_key" ON "shared_resources"("workshop_id", "resource_name");

-- CreateIndex
CREATE INDEX "machine_unavailability_workshop_id_idx" ON "machine_unavailability"("workshop_id");

-- CreateIndex
CREATE INDEX "machine_unavailability_machine_id_idx" ON "machine_unavailability"("machine_id");

-- CreateIndex
CREATE UNIQUE INDEX "clients_workshop_id_name_key" ON "clients"("workshop_id", "name");

-- CreateIndex
CREATE INDEX "orders_workshop_id_status_idx" ON "orders"("workshop_id", "status");

-- CreateIndex
CREATE UNIQUE INDEX "orders_workshop_id_order_ref_key" ON "orders"("workshop_id", "order_ref");

-- CreateIndex
CREATE UNIQUE INDEX "jobs_order_id_key" ON "jobs"("order_id");

-- CreateIndex
CREATE INDEX "operations_machine_id_idx" ON "operations"("machine_id");

-- CreateIndex
CREATE UNIQUE INDEX "operations_job_id_sequence_idx_key" ON "operations"("job_id", "sequence_idx");

-- CreateIndex
CREATE INDEX "soft_constraints_workshop_id_enabled_idx" ON "soft_constraints"("workshop_id", "enabled");

-- CreateIndex
CREATE INDEX "versions_workshop_id_is_active_idx" ON "versions"("workshop_id", "is_active");

-- CreateIndex
CREATE UNIQUE INDEX "versions_workshop_id_version_number_key" ON "versions"("workshop_id", "version_number");

-- CreateIndex
CREATE INDEX "solve_jobs_status_created_at_idx" ON "solve_jobs"("status", "created_at");

-- CreateIndex
CREATE INDEX "solve_jobs_workshop_id_status_idx" ON "solve_jobs"("workshop_id", "status");

-- CreateIndex
CREATE UNIQUE INDEX "schedules_version_id_key" ON "schedules"("version_id");

-- CreateIndex
CREATE INDEX "preflight_sessions_workshop_id_idx" ON "preflight_sessions"("workshop_id");

-- CreateIndex
CREATE INDEX "anomalies_session_id_level_status_idx" ON "anomalies"("session_id", "level", "status");

-- AddForeignKey
ALTER TABLE "machines" ADD CONSTRAINT "machines_workshop_id_fkey" FOREIGN KEY ("workshop_id") REFERENCES "workshops"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "operators" ADD CONSTRAINT "operators_workshop_id_fkey" FOREIGN KEY ("workshop_id") REFERENCES "workshops"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "shared_resources" ADD CONSTRAINT "shared_resources_workshop_id_fkey" FOREIGN KEY ("workshop_id") REFERENCES "workshops"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "machine_unavailability" ADD CONSTRAINT "machine_unavailability_workshop_id_fkey" FOREIGN KEY ("workshop_id") REFERENCES "workshops"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "machine_unavailability" ADD CONSTRAINT "machine_unavailability_machine_id_fkey" FOREIGN KEY ("machine_id") REFERENCES "machines"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "clients" ADD CONSTRAINT "clients_workshop_id_fkey" FOREIGN KEY ("workshop_id") REFERENCES "workshops"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "orders" ADD CONSTRAINT "orders_workshop_id_fkey" FOREIGN KEY ("workshop_id") REFERENCES "workshops"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "orders" ADD CONSTRAINT "orders_client_id_fkey" FOREIGN KEY ("client_id") REFERENCES "clients"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "jobs" ADD CONSTRAINT "jobs_order_id_fkey" FOREIGN KEY ("order_id") REFERENCES "orders"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "operations" ADD CONSTRAINT "operations_job_id_fkey" FOREIGN KEY ("job_id") REFERENCES "jobs"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "operations" ADD CONSTRAINT "operations_machine_id_fkey" FOREIGN KEY ("machine_id") REFERENCES "machines"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "soft_constraints" ADD CONSTRAINT "soft_constraints_workshop_id_fkey" FOREIGN KEY ("workshop_id") REFERENCES "workshops"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "versions" ADD CONSTRAINT "versions_workshop_id_fkey" FOREIGN KEY ("workshop_id") REFERENCES "workshops"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "versions" ADD CONSTRAINT "versions_parent_version_id_fkey" FOREIGN KEY ("parent_version_id") REFERENCES "versions"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "solve_jobs" ADD CONSTRAINT "solve_jobs_workshop_id_fkey" FOREIGN KEY ("workshop_id") REFERENCES "workshops"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "solve_jobs" ADD CONSTRAINT "solve_jobs_version_id_fkey" FOREIGN KEY ("version_id") REFERENCES "versions"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "schedules" ADD CONSTRAINT "schedules_version_id_fkey" FOREIGN KEY ("version_id") REFERENCES "versions"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "preflight_sessions" ADD CONSTRAINT "preflight_sessions_workshop_id_fkey" FOREIGN KEY ("workshop_id") REFERENCES "workshops"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "anomalies" ADD CONSTRAINT "anomalies_session_id_fkey" FOREIGN KEY ("session_id") REFERENCES "preflight_sessions"("id") ON DELETE CASCADE ON UPDATE CASCADE;
