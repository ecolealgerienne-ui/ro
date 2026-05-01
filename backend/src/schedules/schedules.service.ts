import { Injectable, NotFoundException } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';

/**
 * Service de lecture du Schedule (résultat planifié) d'une Version.
 *
 * Le Schedule est écrit par le worker Python (Phase 4 J4) après chaque solve
 * réussi. Il est rattaché à la `Version` source. Une `Version` n'a au plus
 * qu'un Schedule (contrainte unique sur `version_id`).
 */
@Injectable()
export class SchedulesService {
  constructor(private readonly prisma: PrismaService) {}

  /**
   * Récupère le Schedule de la version active (si versionId omis) ou d'une
   * version explicite. Retourne null si pas encore solvé.
   */
  async findOne(workshopId: string, versionId?: string) {
    const workshop = await this.prisma.workshop.findUnique({
      where: { id: workshopId },
      select: { id: true },
    });
    if (!workshop) throw new NotFoundException(`Workshop ${workshopId} introuvable`);

    let resolvedVersionId = versionId;
    if (!resolvedVersionId) {
      const active = await this.prisma.version.findFirst({
        where: { workshopId, isActive: true },
        select: { id: true },
      });
      resolvedVersionId = active?.id;
    }
    if (!resolvedVersionId) return null;

    // Vérifie que la version appartient bien au workshop (sécurité)
    const version = await this.prisma.version.findFirst({
      where: { id: resolvedVersionId, workshopId },
      select: { id: true, versionNumber: true, isActive: true },
    });
    if (!version) {
      throw new NotFoundException(
        `Version ${resolvedVersionId} introuvable dans ce workshop`,
      );
    }

    const schedule = await this.prisma.schedule.findUnique({
      where: { versionId: resolvedVersionId },
    });
    if (!schedule) return null;

    return {
      ...schedule,
      versionNumber: version.versionNumber,
      versionIsActive: version.isActive,
    };
  }
}
