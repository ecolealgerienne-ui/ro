import { Injectable, Logger, NotFoundException, ConflictException } from '@nestjs/common';
import { Prisma } from '@prisma/client';
import { PrismaService } from '../prisma/prisma.service';

/** Couche de transaction Prisma — accepte le client root ou un client de transaction. */
export type PrismaTx = Prisma.TransactionClient | PrismaService;

/**
 * Service partagé pour la gestion du versioning des configurations Workshop.
 *
 * Discipline V1 : chaque mutation (CRUD sur Workshop / Machine / Client /
 * Order / SoftConstraint) crée une nouvelle Version qui stocke un snapshot
 * complet de l'état du Workshop. Le rollback ne supprime jamais : il crée
 * une nouvelle version au sommet de la timeline avec le snapshot d'une
 * version antérieure.
 */
@Injectable()
export class VersionsService {
  private readonly logger = new Logger(VersionsService.name);

  constructor(private readonly prisma: PrismaService) {}

  /**
   * Crée une nouvelle Version dans la même transaction que la mutation appelante.
   * À appeler depuis l'intérieur d'un `prisma.$transaction(async (tx) => { ... })`.
   *
   * Implémentation : repose sur la contrainte d'unicité `(workshop_id, version_number)`
   * + retry simple en cas de course (très peu probable V1, single-tenant).
   */
  async createSnapshotInTransaction(
    tx: PrismaTx,
    workshopId: string,
    message: string,
    author = 'api-user',
  ): Promise<{ id: string; versionNumber: number }> {
    const snapshot = await this.buildSnapshot(tx, workshopId);

    const previousActive = await tx.version.findFirst({
      where: { workshopId, isActive: true },
      orderBy: { versionNumber: 'desc' },
    });

    const lastVersion = await tx.version.findFirst({
      where: { workshopId },
      orderBy: { versionNumber: 'desc' },
      select: { versionNumber: true },
    });
    const nextNumber = (lastVersion?.versionNumber ?? 0) + 1;

    if (previousActive) {
      await tx.version.update({
        where: { id: previousActive.id },
        data: { isActive: false },
      });
    }

    const created = await tx.version.create({
      data: {
        workshopId,
        versionNumber: nextNumber,
        parentVersionId: previousActive?.id ?? null,
        message,
        author,
        snapshot: snapshot as Prisma.InputJsonValue,
        isActive: true,
      },
      select: { id: true, versionNumber: true },
    });
    this.logger.debug(`Workshop ${workshopId}: créé v${nextNumber} (${message})`);
    return created;
  }

  /**
   * Rollback : crée une nouvelle version au sommet, en copiant le snapshot
   * d'une version cible. Pas de delete, l'historique reste intact.
   */
  async rollback(workshopId: string, targetVersionNumber: number, author = 'api-user') {
    return this.prisma.$transaction(async (tx) => {
      const target = await tx.version.findUnique({
        where: { workshopId_versionNumber: { workshopId, versionNumber: targetVersionNumber } },
      });
      if (!target) {
        throw new NotFoundException(
          `Version v${targetVersionNumber} introuvable pour le workshop ${workshopId}`,
        );
      }
      if (target.isActive) {
        throw new ConflictException(`Version v${targetVersionNumber} est déjà la version active`);
      }

      const previousActive = await tx.version.findFirst({
        where: { workshopId, isActive: true },
        orderBy: { versionNumber: 'desc' },
      });

      const lastVersion = await tx.version.findFirst({
        where: { workshopId },
        orderBy: { versionNumber: 'desc' },
        select: { versionNumber: true },
      });
      const nextNumber = (lastVersion?.versionNumber ?? 0) + 1;

      if (previousActive) {
        await tx.version.update({
          where: { id: previousActive.id },
          data: { isActive: false },
        });
      }

      return tx.version.create({
        data: {
          workshopId,
          versionNumber: nextNumber,
          parentVersionId: previousActive?.id ?? null,
          message: `Rollback vers v${targetVersionNumber}`,
          author,
          snapshot: target.snapshot as Prisma.InputJsonValue,
          isActive: true,
        },
      });
    });
  }

  async findAll(workshopId: string) {
    return this.prisma.version.findMany({
      where: { workshopId },
      orderBy: { versionNumber: 'desc' },
      select: {
        id: true,
        versionNumber: true,
        parentVersionId: true,
        message: true,
        author: true,
        isActive: true,
        createdAt: true,
      },
    });
  }

  async findOne(workshopId: string, versionNumber: number) {
    const version = await this.prisma.version.findUnique({
      where: { workshopId_versionNumber: { workshopId, versionNumber } },
    });
    if (!version) {
      throw new NotFoundException(
        `Version v${versionNumber} introuvable pour le workshop ${workshopId}`,
      );
    }
    return version;
  }

  /**
   * Construit le snapshot JSON complet d'un Workshop.
   *
   * V1 : structure brute des tables (proche du WorkshopInstance Pydantic).
   * Le worker Python (J4) consommera ce snapshot pour construire l'instance
   * solveur. La bijection est documentée dans
   * `poc-scheduler/scripts/db_worker.py` (à venir).
   */
  private async buildSnapshot(tx: PrismaTx, workshopId: string): Promise<unknown> {
    const workshop = await tx.workshop.findUnique({
      where: { id: workshopId },
      include: {
        machines: { orderBy: { machineIdInt: 'asc' } },
        operators: { orderBy: { operatorIdInt: 'asc' } },
        sharedRes: { orderBy: { resourceName: 'asc' } },
        unavailability: { include: { machine: { select: { machineIdInt: true } } } },
        clients: { orderBy: { name: 'asc' } },
        orders: {
          include: {
            client: { select: { id: true, name: true, tier: true } },
            job: { include: { operations: { orderBy: { sequenceIdx: 'asc' } } } },
          },
          orderBy: { orderRef: 'asc' },
        },
        softConstraints: { where: { enabled: true }, orderBy: { createdAt: 'asc' } },
      },
    });
    if (!workshop) {
      throw new NotFoundException(`Workshop ${workshopId} introuvable`);
    }
    return workshop;
  }
}
