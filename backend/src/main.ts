import { NestFactory } from '@nestjs/core';
import { ValidationPipe, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { AppModule } from './app.module';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);

  // CORS — Phase 5 V1 : autorise le frontend Next.js local + un origin
  // configurable via CORS_ORIGIN (separator virgule). Verrouillera en
  // Phase 7 prod avec liste blanche stricte par tenant.
  const config = app.get(ConfigService);
  const corsOrigin = config.get<string>('CORS_ORIGIN', 'http://localhost:3001');
  app.enableCors({
    origin: corsOrigin.split(',').map((o) => o.trim()),
    credentials: true,
  });

  app.useGlobalPipes(
    new ValidationPipe({
      whitelist: true,
      forbidNonWhitelisted: true,
      transform: true,
    }),
  );

  app.setGlobalPrefix('api');

  const port = config.get<number>('PORT', 3000);

  await app.listen(port);
  Logger.log(`Backend ro démarré sur http://localhost:${port}/api`, 'Bootstrap');
  Logger.log(`CORS allow-origin : ${corsOrigin}`, 'Bootstrap');
}

void bootstrap();
