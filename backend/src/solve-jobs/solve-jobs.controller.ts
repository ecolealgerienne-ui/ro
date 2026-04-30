import {
  Body,
  Controller,
  Delete,
  Get,
  HttpCode,
  HttpStatus,
  Param,
  ParseUUIDPipe,
  Post,
} from '@nestjs/common';
import { CreateSolveJobDto } from './dto/create-solve-job.dto';
import { SolveJobsService } from './solve-jobs.service';

@Controller('workshops/:workshopId/solve-jobs')
export class SolveJobsController {
  constructor(private readonly solveJobs: SolveJobsService) {}

  @Post()
  @HttpCode(HttpStatus.CREATED)
  create(@Param('workshopId', ParseUUIDPipe) workshopId: string, @Body() dto: CreateSolveJobDto) {
    return this.solveJobs.create(workshopId, dto);
  }

  @Get()
  findAll(@Param('workshopId', ParseUUIDPipe) workshopId: string) {
    return this.solveJobs.findAll(workshopId);
  }

  @Get(':id')
  findOne(
    @Param('workshopId', ParseUUIDPipe) workshopId: string,
    @Param('id', ParseUUIDPipe) id: string,
  ) {
    return this.solveJobs.findOne(workshopId, id);
  }

  @Delete(':id')
  cancel(
    @Param('workshopId', ParseUUIDPipe) workshopId: string,
    @Param('id', ParseUUIDPipe) id: string,
  ) {
    return this.solveJobs.cancel(workshopId, id);
  }
}
