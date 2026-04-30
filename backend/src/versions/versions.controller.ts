import { Controller, Get, Param, ParseIntPipe, ParseUUIDPipe, Post } from '@nestjs/common';
import { VersionsService } from './versions.service';

@Controller('workshops/:workshopId/versions')
export class VersionsController {
  constructor(private readonly versions: VersionsService) {}

  @Get()
  list(@Param('workshopId', ParseUUIDPipe) workshopId: string) {
    return this.versions.findAll(workshopId);
  }

  @Get(':versionNumber')
  detail(
    @Param('workshopId', ParseUUIDPipe) workshopId: string,
    @Param('versionNumber', ParseIntPipe) versionNumber: number,
  ) {
    return this.versions.findOne(workshopId, versionNumber);
  }

  @Post(':versionNumber/rollback')
  rollback(
    @Param('workshopId', ParseUUIDPipe) workshopId: string,
    @Param('versionNumber', ParseIntPipe) versionNumber: number,
  ) {
    return this.versions.rollback(workshopId, versionNumber);
  }
}
