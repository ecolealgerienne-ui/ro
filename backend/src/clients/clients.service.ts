import { ConflictException, Injectable, NotFoundException } from '@nestjs/common';
import { Prisma } from '@prisma/client';
import { PrismaService } from '../prisma/prisma.service';
import { VersionsService, PrismaTx } from '../versions/versions.service';
import { CreateClientDto } from './dto/create-client.dto';
import { UpdateClientDto } from './dto/update-client.dto';

@Injectable()
export class ClientsService {
  constructor(
    private readonly prisma: PrismaService,
    private readonly versions: VersionsService,
  ) {}

  async create(workshopId: string, dto: CreateClientDto) {
    return this.prisma.$transaction(async (tx) => {
      await this.assertWorkshopExists(tx, workshopId);
      try {
        const client = await tx.client.create({
          data: { workshopId, ...dto },
        });
        await this.versions.createSnapshotInTransaction(
          tx,
          workshopId,
          `Ajout client "${client.name}" (T${client.tier})`,
        );
        return client;
      } catch (e) {
        if (e instanceof Prisma.PrismaClientKnownRequestError && e.code === 'P2002') {
          throw new ConflictException(`Client "${dto.name}" existe déjà pour ce workshop`);
        }
        throw e;
      }
    });
  }

  findAll(workshopId: string) {
    return this.prisma.client.findMany({
      where: { workshopId },
      orderBy: [{ tier: 'asc' }, { name: 'asc' }],
    });
  }

  async findOne(workshopId: string, id: string) {
    const client = await this.prisma.client.findFirst({ where: { id, workshopId } });
    if (!client) throw new NotFoundException(`Client ${id} introuvable`);
    return client;
  }

  async update(workshopId: string, id: string, dto: UpdateClientDto) {
    return this.prisma.$transaction(async (tx) => {
      const existing = await tx.client.findFirst({ where: { id, workshopId } });
      if (!existing) throw new NotFoundException(`Client ${id} introuvable`);
      const client = await tx.client.update({ where: { id }, data: dto });
      await this.versions.createSnapshotInTransaction(
        tx,
        workshopId,
        `Modification client "${client.name}"`,
      );
      return client;
    });
  }

  async remove(workshopId: string, id: string) {
    return this.prisma.$transaction(async (tx) => {
      const existing = await tx.client.findFirst({ where: { id, workshopId } });
      if (!existing) throw new NotFoundException(`Client ${id} introuvable`);
      try {
        await tx.client.delete({ where: { id } });
      } catch (e) {
        if (e instanceof Prisma.PrismaClientKnownRequestError && e.code === 'P2003') {
          throw new ConflictException(
            `Impossible de supprimer "${existing.name}" : des OF y sont rattachés`,
          );
        }
        throw e;
      }
      await this.versions.createSnapshotInTransaction(
        tx,
        workshopId,
        `Suppression client "${existing.name}"`,
      );
      return { id, deleted: true };
    });
  }

  private async assertWorkshopExists(tx: PrismaTx, workshopId: string): Promise<void> {
    const w = await tx.workshop.findUnique({ where: { id: workshopId }, select: { id: true } });
    if (!w) throw new NotFoundException(`Workshop ${workshopId} introuvable`);
  }
}
