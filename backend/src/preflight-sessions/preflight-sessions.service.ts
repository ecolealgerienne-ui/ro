import { createHash } from 'node:crypto';
import { BadRequestException, Injectable, Logger, NotFoundException } from '@nestjs/common';
import { AnomalyLevel, Prisma } from '@prisma/client';
import { PrismaService } from '../prisma/prisma.service';
import { UpdateAnomalyDto } from './dto/update-anomaly.dto';
import { PreflightClientService, PreflightError } from './preflight-client.service';
import type { UploadedFile as MulterFile } from './types';

const SEVERITY_TO_LEVEL: Record<PreflightError['severity'], AnomalyLevel> = {
  blocking: AnomalyLevel.certain,
  warning: AnomalyLevel.probable,
  info: AnomalyLevel.surprising,
};

/**
 * Coordonne l'upload CSV cote backend :
 * 1. Recoit le buffer multipart (controller).
 * 2. Forwarde vers le service Python (PreflightClientService).
 * 3. Persiste PreflightSession + Anomaly[] dans une transaction.
 */
@Injectable()
export class PreflightSessionsService {
  private readonly logger = new Logger(PreflightSessionsService.name);

  constructor(
    private readonly prisma: PrismaService,
    private readonly preflightClient: PreflightClientService,
  ) {}

  async upload(workshopId: string, file: MulterFile) {
    if (!file?.buffer || file.size === 0) {
      throw new BadRequestException('Fichier vide ou absent');
    }
    const workshop = await this.prisma.workshop.findUnique({
      where: { id: workshopId },
      select: { id: true },
    });
    if (!workshop) throw new NotFoundException(`Workshop ${workshopId} introuvable`);

    const report = await this.preflightClient.runPreflight(
      file.buffer,
      file.originalname,
      file.mimetype,
    );

    const fileHash = createHash('sha256').update(file.buffer).digest('hex');

    const session = await this.prisma.$transaction(async (tx) => {
      const created = await tx.preflightSession.create({
        data: {
          workshopId,
          fileName: file.originalname,
          fileHash,
          nRowsTotal: report.rows_parsed,
          nRowsImported: report.cleaned_rows.length,
        },
      });

      if (report.errors.length > 0) {
        await tx.anomaly.createMany({
          data: report.errors.map((e) => ({
            sessionId: created.id,
            level: SEVERITY_TO_LEVEL[e.severity],
            code: e.type,
            rowIndex: e.row_index ?? -1,
            column: e.column ?? null,
            rawValue: e.raw_value ?? null,
            suggestion: e.description,
          })),
        });
      }
      return created;
    });

    this.logger.log(
      `Preflight ${session.id}: ${report.errors.length} anomalies / ${report.rows_parsed} lignes (workshop ${workshopId})`,
    );
    return this.findOne(workshopId, session.id);
  }

  findAll(workshopId: string) {
    return this.prisma.preflightSession.findMany({
      where: { workshopId },
      orderBy: { importedAt: 'desc' },
      include: { _count: { select: { anomalies: true } } },
      take: 50,
    });
  }

  async findOne(workshopId: string, id: string) {
    const session = await this.prisma.preflightSession.findFirst({
      where: { id, workshopId },
      include: {
        anomalies: { orderBy: [{ level: 'asc' }, { rowIndex: 'asc' }] },
      },
    });
    if (!session) throw new NotFoundException(`PreflightSession ${id} introuvable`);
    return session;
  }

  async updateAnomaly(
    workshopId: string,
    sessionId: string,
    anomalyId: string,
    dto: UpdateAnomalyDto,
  ) {
    return this.prisma.$transaction(async (tx) => {
      const anomaly = await tx.anomaly.findFirst({
        where: { id: anomalyId, sessionId, session: { workshopId } },
      });
      if (!anomaly) throw new NotFoundException(`Anomaly ${anomalyId} introuvable`);
      try {
        return await tx.anomaly.update({
          where: { id: anomalyId },
          data: { status: dto.status, resolution: dto.resolution ?? null },
        });
      } catch (e) {
        if (e instanceof Prisma.PrismaClientKnownRequestError && e.code === 'P2025') {
          throw new NotFoundException(`Anomaly ${anomalyId} introuvable`);
        }
        throw e;
      }
    });
  }
}
