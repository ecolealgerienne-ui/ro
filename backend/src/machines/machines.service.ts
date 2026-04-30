import { ConflictException, Injectable, NotFoundException } from '@nestjs/common';
import { Prisma } from '@prisma/client';
import { PrismaService } from '../prisma/prisma.service';
import { VersionsService, PrismaTx } from '../versions/versions.service';
import { CreateMachineDto } from './dto/create-machine.dto';
import { UpdateMachineDto } from './dto/update-machine.dto';

@Injectable()
export class MachinesService {
  constructor(
    private readonly prisma: PrismaService,
    private readonly versions: VersionsService,
  ) {}

  async create(workshopId: string, dto: CreateMachineDto) {
    return this.prisma.$transaction(async (tx) => {
      await this.assertWorkshopExists(tx, workshopId);

      const machineIdInt = dto.machineIdInt ?? (await this.nextMachineIdInt(tx, workshopId));

      try {
        const machine = await tx.machine.create({
          data: {
            workshopId,
            machineIdInt,
            name: dto.name,
            type: dto.type ?? null,
          },
        });
        await this.versions.createSnapshotInTransaction(
          tx,
          workshopId,
          `Ajout machine "${machine.name}" (${machine.machineIdInt})`,
        );
        return machine;
      } catch (e) {
        if (e instanceof Prisma.PrismaClientKnownRequestError && e.code === 'P2002') {
          throw new ConflictException(`machineIdInt=${machineIdInt} déjà utilisé pour ce workshop`);
        }
        throw e;
      }
    });
  }

  findAll(workshopId: string) {
    return this.prisma.machine.findMany({
      where: { workshopId },
      orderBy: { machineIdInt: 'asc' },
    });
  }

  async findOne(workshopId: string, id: string) {
    const machine = await this.prisma.machine.findFirst({ where: { id, workshopId } });
    if (!machine) throw new NotFoundException(`Machine ${id} introuvable dans ce workshop`);
    return machine;
  }

  async update(workshopId: string, id: string, dto: UpdateMachineDto) {
    return this.prisma.$transaction(async (tx) => {
      const existing = await tx.machine.findFirst({ where: { id, workshopId } });
      if (!existing) throw new NotFoundException(`Machine ${id} introuvable`);

      const machine = await tx.machine.update({
        where: { id },
        data: {
          ...(dto.name !== undefined && { name: dto.name }),
          ...(dto.type !== undefined && { type: dto.type }),
          ...(dto.machineIdInt !== undefined && { machineIdInt: dto.machineIdInt }),
        },
      });
      await this.versions.createSnapshotInTransaction(
        tx,
        workshopId,
        `Modification machine "${machine.name}"`,
      );
      return machine;
    });
  }

  async remove(workshopId: string, id: string) {
    return this.prisma.$transaction(async (tx) => {
      const existing = await tx.machine.findFirst({ where: { id, workshopId } });
      if (!existing) throw new NotFoundException(`Machine ${id} introuvable`);
      await tx.machine.delete({ where: { id } });
      await this.versions.createSnapshotInTransaction(
        tx,
        workshopId,
        `Suppression machine "${existing.name}"`,
      );
      return { id, deleted: true };
    });
  }

  // ---------- helpers ----------

  private async assertWorkshopExists(tx: PrismaTx, workshopId: string): Promise<void> {
    const w = await tx.workshop.findUnique({ where: { id: workshopId }, select: { id: true } });
    if (!w) throw new NotFoundException(`Workshop ${workshopId} introuvable`);
  }

  private async nextMachineIdInt(tx: PrismaTx, workshopId: string): Promise<number> {
    const last = await tx.machine.findFirst({
      where: { workshopId },
      orderBy: { machineIdInt: 'desc' },
      select: { machineIdInt: true },
    });
    return (last?.machineIdInt ?? -1) + 1;
  }
}
