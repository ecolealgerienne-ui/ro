import { Controller, Get, Logger } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';

interface HealthCheckResult {
  status: 'ok' | 'degraded';
  uptime_s: number;
  database: 'up' | 'down';
  version: string;
  timestamp: string;
}

@Controller('health')
export class HealthController {
  private readonly logger = new Logger(HealthController.name);
  private readonly startedAt = Date.now();

  constructor(private readonly prisma: PrismaService) {}

  @Get()
  async check(): Promise<HealthCheckResult> {
    let database: 'up' | 'down' = 'up';
    try {
      await this.prisma.$queryRaw`SELECT 1`;
    } catch (err) {
      this.logger.error('Healthcheck DB failed', err);
      database = 'down';
    }

    return {
      status: database === 'up' ? 'ok' : 'degraded',
      uptime_s: Math.floor((Date.now() - this.startedAt) / 1000),
      database,
      version: process.env.npm_package_version ?? '0.1.0',
      timestamp: new Date().toISOString(),
    };
  }
}
