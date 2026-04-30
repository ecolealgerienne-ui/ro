import { Module } from '@nestjs/common';
import { PreflightClientService } from './preflight-client.service';
import { PreflightSessionsController } from './preflight-sessions.controller';
import { PreflightSessionsService } from './preflight-sessions.service';

@Module({
  controllers: [PreflightSessionsController],
  providers: [PreflightSessionsService, PreflightClientService],
})
export class PreflightSessionsModule {}
