import {
  BadRequestException,
  ConflictException,
  Injectable,
  NotFoundException,
} from '@nestjs/common';
import { Prisma } from '@prisma/client';
import { PrismaService } from '../prisma/prisma.service';
import { VersionsService, PrismaTx } from '../versions/versions.service';
import { CreateOrderDto } from './dto/create-order.dto';
import { UpdateOrderDto } from './dto/update-order.dto';

@Injectable()
export class OrdersService {
  constructor(
    private readonly prisma: PrismaService,
    private readonly versions: VersionsService,
  ) {}

  async create(workshopId: string, dto: CreateOrderDto) {
    return this.prisma.$transaction(async (tx) => {
      await this.assertWorkshopExists(tx, workshopId);
      await this.assertClientBelongsToWorkshop(tx, workshopId, dto.clientId);
      const machinesById = await this.loadAndAssertMachines(tx, workshopId, dto.operations);
      this.assertSequenceIndicesContiguous(dto.operations);

      const jobIdInt = await this.nextJobIdInt(tx, workshopId);

      try {
        const order = await tx.order.create({
          data: {
            workshopId,
            clientId: dto.clientId,
            orderRef: dto.orderRef,
            partRef: dto.partRef,
            partFamilyId: dto.partFamilyId ?? null,
            quantity: dto.quantity ?? 1,
            deadline: dto.deadline ? new Date(dto.deadline) : null,
            job: {
              create: {
                jobIdInt,
                criticality: dto.criticality ?? null,
                operations: {
                  create: dto.operations.map((op) => ({
                    sequenceIdx: op.sequenceIdx,
                    machineId: machinesById.get(op.machineId)!,
                    durationMin: op.durationMin,
                    familyId: op.familyId ?? 0,
                    qualifiedOperatorIds: op.qualifiedOperatorIds ?? [],
                  })),
                },
              },
            },
          },
          include: { job: { include: { operations: { orderBy: { sequenceIdx: 'asc' } } } } },
        });
        await this.versions.createSnapshotInTransaction(
          tx,
          workshopId,
          `Ajout OF "${order.orderRef}" (${dto.operations.length} ops)`,
        );
        return order;
      } catch (e) {
        if (e instanceof Prisma.PrismaClientKnownRequestError && e.code === 'P2002') {
          throw new ConflictException(`OF "${dto.orderRef}" existe déjà`);
        }
        throw e;
      }
    });
  }

  findAll(workshopId: string) {
    return this.prisma.order.findMany({
      where: { workshopId },
      include: {
        client: { select: { id: true, name: true, tier: true } },
        job: { select: { jobIdInt: true, criticality: true } },
      },
      orderBy: { createdAt: 'desc' },
    });
  }

  async findOne(workshopId: string, id: string) {
    const order = await this.prisma.order.findFirst({
      where: { id, workshopId },
      include: {
        client: true,
        job: { include: { operations: { orderBy: { sequenceIdx: 'asc' } } } },
      },
    });
    if (!order) throw new NotFoundException(`OF ${id} introuvable`);
    return order;
  }

  async update(workshopId: string, id: string, dto: UpdateOrderDto) {
    return this.prisma.$transaction(async (tx) => {
      const existing = await tx.order.findFirst({ where: { id, workshopId } });
      if (!existing) throw new NotFoundException(`OF ${id} introuvable`);

      if (dto.clientId !== undefined) {
        await this.assertClientBelongsToWorkshop(tx, workshopId, dto.clientId);
      }

      const order = await tx.order.update({
        where: { id },
        data: {
          ...(dto.clientId !== undefined && { clientId: dto.clientId }),
          ...(dto.orderRef !== undefined && { orderRef: dto.orderRef }),
          ...(dto.partRef !== undefined && { partRef: dto.partRef }),
          ...(dto.partFamilyId !== undefined && { partFamilyId: dto.partFamilyId }),
          ...(dto.quantity !== undefined && { quantity: dto.quantity }),
          ...(dto.deadline !== undefined && {
            deadline: dto.deadline ? new Date(dto.deadline) : null,
          }),
          ...(dto.status !== undefined && { status: dto.status }),
          ...(dto.criticality !== undefined && {
            job: { update: { criticality: dto.criticality } },
          }),
        },
        include: { job: { include: { operations: true } } },
      });
      await this.versions.createSnapshotInTransaction(
        tx,
        workshopId,
        `Modification OF "${order.orderRef}"`,
      );
      return order;
    });
  }

  async remove(workshopId: string, id: string) {
    return this.prisma.$transaction(async (tx) => {
      const existing = await tx.order.findFirst({ where: { id, workshopId } });
      if (!existing) throw new NotFoundException(`OF ${id} introuvable`);
      await tx.order.delete({ where: { id } });
      await this.versions.createSnapshotInTransaction(
        tx,
        workshopId,
        `Suppression OF "${existing.orderRef}"`,
      );
      return { id, deleted: true };
    });
  }

  // ---------- helpers ----------

  private async assertWorkshopExists(tx: PrismaTx, workshopId: string): Promise<void> {
    const w = await tx.workshop.findUnique({ where: { id: workshopId }, select: { id: true } });
    if (!w) throw new NotFoundException(`Workshop ${workshopId} introuvable`);
  }

  private async assertClientBelongsToWorkshop(
    tx: PrismaTx,
    workshopId: string,
    clientId: string,
  ): Promise<void> {
    const c = await tx.client.findFirst({
      where: { id: clientId, workshopId },
      select: { id: true },
    });
    if (!c) {
      throw new BadRequestException(`Client ${clientId} n'appartient pas à ce workshop`);
    }
  }

  /**
   * Vérifie que toutes les machines référencées appartiennent au workshop, et
   * retourne un Map `machineId -> machineId` (no-op mais qui valide en passant).
   */
  private async loadAndAssertMachines(
    tx: PrismaTx,
    workshopId: string,
    operations: { machineId: string }[],
  ): Promise<Map<string, string>> {
    const ids = Array.from(new Set(operations.map((o) => o.machineId)));
    const machines = await tx.machine.findMany({
      where: { workshopId, id: { in: ids } },
      select: { id: true },
    });
    if (machines.length !== ids.length) {
      const found = new Set(machines.map((m) => m.id));
      const missing = ids.filter((i) => !found.has(i));
      throw new BadRequestException(
        `Machines introuvables ou hors workshop: ${missing.join(', ')}`,
      );
    }
    return new Map(machines.map((m) => [m.id, m.id]));
  }

  /** Vérifie que les sequence_idx vont de 0 à n-1 sans trou ni doublon. */
  private assertSequenceIndicesContiguous(operations: { sequenceIdx: number }[]): void {
    const sorted = operations.map((o) => o.sequenceIdx).sort((a, b) => a - b);
    for (let i = 0; i < sorted.length; i++) {
      if (sorted[i] !== i) {
        throw new BadRequestException(
          `sequence_idx doivent être contigus de 0 à ${operations.length - 1}, reçu: [${sorted.join(', ')}]`,
        );
      }
    }
  }

  private async nextJobIdInt(tx: PrismaTx, workshopId: string): Promise<number> {
    const last = await tx.job.findFirst({
      where: { order: { workshopId } },
      orderBy: { jobIdInt: 'desc' },
      select: { jobIdInt: true },
    });
    return (last?.jobIdInt ?? -1) + 1;
  }
}
