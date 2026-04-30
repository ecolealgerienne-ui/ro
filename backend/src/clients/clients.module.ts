import { Module } from '@nestjs/common';
import { VersionsModule } from '../versions/versions.module';
import { ClientsController } from './clients.controller';
import { ClientsService } from './clients.service';

@Module({
  imports: [VersionsModule],
  controllers: [ClientsController],
  providers: [ClientsService],
})
export class ClientsModule {}
