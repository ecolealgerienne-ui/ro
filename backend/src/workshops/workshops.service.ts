import { Injectable, NotFoundException } from '@nestjs/common';
import { Prisma } from '@prisma/client';
import { PrismaService } from '../prisma/prisma.service';
import { VersionsService } from '../versions/versions.service';
import { CreateWorkshopDto } from './dto/create-workshop.dto';
import { UpdateWorkshopDto } from './dto/update-workshop.dto';

@Injectable()
export class WorkshopsService {
  constructor(
    private readonly prisma: PrismaService,
    private readonly versions: VersionsService,
  ) {}

  async create(dto: CreateWorkshopDto) {
    return this.prisma.$transaction(async (tx) => {
      const workshop = await tx.workshop.create({ data: dto });
      await this.versions.createSnapshotInTransaction(
        tx,
        workshop.id,
        `Création atelier "${workshop.name}"`,
      );
      return workshop;
    });
  }

  findAll() {
    return this.prisma.workshop.findMany({
      orderBy: { createdAt: 'desc' },
      include: { _count: { select: { machines: true, orders: true, versions: true } } },
    });
  }

  async findOne(id: string) {
    const workshop = await this.prisma.workshop.findUnique({
      where: { id },
      include: {
        machines: { orderBy: { machineIdInt: 'asc' } },
        clients: { orderBy: { tier: 'asc' } },
        _count: { select: { orders: true, versions: true } },
      },
    });
    if (!workshop) throw new NotFoundException(`Workshop ${id} introuvable`);
    return workshop;
  }

  async update(id: string, dto: UpdateWorkshopDto) {
    return this.prisma.$transaction(async (tx) => {
      try {
        const workshop = await tx.workshop.update({ where: { id }, data: dto });
        await this.versions.createSnapshotInTransaction(
          tx,
          workshop.id,
          `Modification atelier (${Object.keys(dto).join(', ')})`,
        );
        return workshop;
      } catch (e) {
        if (e instanceof Prisma.PrismaClientKnownRequestError && e.code === 'P2025') {
          throw new NotFoundException(`Workshop ${id} introuvable`);
        }
        throw e;
      }
    });
  }

  async remove(id: string) {
    try {
      // Suppression ordonnée nécessaire : Operation.machine est en `Restrict`
      // (pour bloquer la suppression accidentelle d'une machine référencée par
      // un OF actif). Du coup, le cascade Workshop→Machine échoue tant que des
      // Operation pointent encore dessus. On supprime donc d'abord les Order
      // (cascade vers Job/Operation), puis le Workshop (cascade vers le reste :
      // machines, clients, opérateurs, versions, sessions preflight…).
      await this.prisma.$transaction(async (tx) => {
        await tx.order.deleteMany({ where: { workshopId: id } });
        await tx.workshop.delete({ where: { id } });
      });
      return { id, deleted: true };
    } catch (e) {
      if (e instanceof Prisma.PrismaClientKnownRequestError && e.code === 'P2025') {
        throw new NotFoundException(`Workshop ${id} introuvable`);
      }
      throw e;
    }
  }
}
