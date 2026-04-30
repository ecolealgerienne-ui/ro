import { Module } from '@nestjs/common';
import { VersionsModule } from '../versions/versions.module';
import { WorkshopsController } from './workshops.controller';
import { WorkshopsService } from './workshops.service';

@Module({
  imports: [VersionsModule],
  controllers: [WorkshopsController],
  providers: [WorkshopsService],
})
export class WorkshopsModule {}
