import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { ClientsModule } from './clients/clients.module';
import { HealthModule } from './health/health.module';
import { MachinesModule } from './machines/machines.module';
import { OrdersModule } from './orders/orders.module';
import { PrismaModule } from './prisma/prisma.module';
import { SolveJobsModule } from './solve-jobs/solve-jobs.module';
import { VersionsModule } from './versions/versions.module';
import { WorkshopsModule } from './workshops/workshops.module';

@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal: true,
      envFilePath: ['.env.local', '.env'],
    }),
    PrismaModule,
    HealthModule,
    VersionsModule,
    WorkshopsModule,
    MachinesModule,
    ClientsModule,
    OrdersModule,
    SolveJobsModule,
  ],
})
export class AppModule {}
