import {
  BadRequestException,
  Body,
  Controller,
  Get,
  HttpCode,
  HttpStatus,
  Param,
  ParseUUIDPipe,
  Patch,
  Post,
  UploadedFile,
  UseInterceptors,
} from '@nestjs/common';
import { FileInterceptor } from '@nestjs/platform-express';
import { UpdateAnomalyDto } from './dto/update-anomaly.dto';
import { PreflightSessionsService } from './preflight-sessions.service';
import type { UploadedFile as MulterFile } from './types';

/** 5 Mio max — un CSV ERP de 50 000 lignes pèse ~3-4 Mio. */
const MAX_FILE_SIZE = 5 * 1024 * 1024;

@Controller('workshops/:workshopId/preflight-sessions')
export class PreflightSessionsController {
  constructor(private readonly preflight: PreflightSessionsService) {}

  @Post()
  @HttpCode(HttpStatus.CREATED)
  @UseInterceptors(FileInterceptor('file', { limits: { fileSize: MAX_FILE_SIZE } }))
  upload(
    @Param('workshopId', ParseUUIDPipe) workshopId: string,
    @UploadedFile() file: MulterFile,
  ) {
    if (!file) throw new BadRequestException('Fichier manquant (champ multipart "file")');
    return this.preflight.upload(workshopId, file);
  }

  @Get()
  findAll(@Param('workshopId', ParseUUIDPipe) workshopId: string) {
    return this.preflight.findAll(workshopId);
  }

  @Get(':id')
  findOne(
    @Param('workshopId', ParseUUIDPipe) workshopId: string,
    @Param('id', ParseUUIDPipe) id: string,
  ) {
    return this.preflight.findOne(workshopId, id);
  }

  @Patch(':id/anomalies/:anomalyId')
  updateAnomaly(
    @Param('workshopId', ParseUUIDPipe) workshopId: string,
    @Param('id', ParseUUIDPipe) sessionId: string,
    @Param('anomalyId', ParseUUIDPipe) anomalyId: string,
    @Body() dto: UpdateAnomalyDto,
  ) {
    return this.preflight.updateAnomaly(workshopId, sessionId, anomalyId, dto);
  }
}
