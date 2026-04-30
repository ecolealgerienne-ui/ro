import { BadRequestException, Injectable, NotFoundException } from '@nestjs/common';
import { Prisma } from '@prisma/client';
import { PrismaService } from '../prisma/prisma.service';
import { CreateSolveJobDto } from './dto/create-solve-job.dto';

@Injectable()
export class SolveJobsService {
  constructor(private readonly prisma: PrismaService) {}

  async create(workshopId: string, dto: CreateSolveJobDto) {
    return this.prisma.$transaction(async (tx) => {
      const workshop = await tx.workshop.findUnique({
        where: { id: workshopId },
        select: { id: true },
      });
      if (!workshop) throw new NotFoundException(`Workshop ${workshopId} introuvable`);

      let versionId = dto.versionId ?? null;
      if (versionId) {
        const v = await tx.version.findFirst({
          where: { id: versionId, workshopId },
          select: { id: true },
        });
        if (!v) {
          throw new BadRequestException(
            `Version ${versionId} n'appartient pas à ce workshop`,
          );
        }
      } else {
        // Si pas de version explicite, on snapshot la version active comme repère.
        // Le worker fera de même au moment du claim — utile pour le suivi UX.
        const active = await tx.version.findFirst({
          where: { workshopId, isActive: true },
          select: { id: true },
        });
        versionId = active?.id ?? null;
      }

      return tx.solveJob.create({
        data: {
          workshopId,
          versionId,
          config: (dto.config ?? {}) as Prisma.InputJsonValue,
          status: 'pending',
        },
      });
    });
  }

  findAll(workshopId: string) {
    return this.prisma.solveJob.findMany({
      where: { workshopId },
      orderBy: { createdAt: 'desc' },
      take: 50,
    });
  }

  async findOne(workshopId: string, id: string) {
    const job = await this.prisma.solveJob.findFirst({
      where: { id, workshopId },
    });
    if (!job) throw new NotFoundException(`SolveJob ${id} introuvable`);
    return job;
  }

  async cancel(workshopId: string, id: string) {
    return this.prisma.$transaction(async (tx) => {
      const job = await tx.solveJob.findFirst({ where: { id, workshopId } });
      if (!job) throw new NotFoundException(`SolveJob ${id} introuvable`);
      if (job.status !== 'pending') {
        throw new BadRequestException(
          `SolveJob ${id} n'est pas en attente (status=${job.status})`,
        );
      }
      return tx.solveJob.update({
        where: { id },
        data: { status: 'cancelled', finishedAt: new Date() },
      });
    });
  }
}
