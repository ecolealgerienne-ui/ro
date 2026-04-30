import { Module } from '@nestjs/common';
import { SolveJobsController } from './solve-jobs.controller';
import { SolveJobsService } from './solve-jobs.service';

@Module({
  controllers: [SolveJobsController],
  providers: [SolveJobsService],
})
export class SolveJobsModule {}
