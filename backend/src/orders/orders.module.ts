import { Module } from '@nestjs/common';
import { VersionsModule } from '../versions/versions.module';
import { OrdersController } from './orders.controller';
import { OrdersService } from './orders.service';

@Module({
  imports: [VersionsModule],
  controllers: [OrdersController],
  providers: [OrdersService],
})
export class OrdersModule {}
