import { Module } from '@nestjs/common';
import { VersionsModule } from '../versions/versions.module';
import { MachinesController } from './machines.controller';
import { MachinesService } from './machines.service';

@Module({
  imports: [VersionsModule],
  controllers: [MachinesController],
  providers: [MachinesService],
})
export class MachinesModule {}
