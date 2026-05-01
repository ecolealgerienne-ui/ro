import { Controller, Get, Param, ParseUUIDPipe, Query } from '@nestjs/common';
import { SchedulesService } from './schedules.service';

@Controller('workshops/:workshopId/schedule')
export class SchedulesController {
  constructor(private readonly schedules: SchedulesService) {}

  /**
   * Retourne le Schedule de la version active, ou d'une version specifique
   * via `?versionId=...`. Renvoie 200 avec body `null` si pas encore solve.
   */
  @Get()
  findOne(
    @Param('workshopId', ParseUUIDPipe) workshopId: string,
    @Query('versionId', new ParseUUIDPipe({ optional: true })) versionId?: string,
  ) {
    return this.schedules.findOne(workshopId, versionId);
  }
}
