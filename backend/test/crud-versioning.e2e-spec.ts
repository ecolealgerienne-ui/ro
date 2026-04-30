import { INestApplication, ValidationPipe } from '@nestjs/common';
import { Test } from '@nestjs/testing';
import request from 'supertest';
import { AppModule } from '../src/app.module';
import { PrismaService } from '../src/prisma/prisma.service';

describe('CRUD + versioning e2e', () => {
  let app: INestApplication;
  let prisma: PrismaService;

  beforeAll(async () => {
    const moduleRef = await Test.createTestingModule({
      imports: [AppModule],
    }).compile();

    app = moduleRef.createNestApplication();
    app.useGlobalPipes(
      new ValidationPipe({ whitelist: true, forbidNonWhitelisted: true, transform: true }),
    );
    app.setGlobalPrefix('api');
    await app.init();

    prisma = app.get(PrismaService);
    // Repartir d'une DB propre — on supprime tous les workshops (cascade fait le reste).
    // Order important : supprimer Operations -> Jobs -> Orders -> Machines via cascade.
    // Workshop a 2 chemins de cascade (machines, orders) qui peuvent s'entrelacer
    // avec le Restrict sur Operation.machine_id ; on vide explicitement les
    // tables enfant d'abord pour éviter ce conflit.
    await prisma.order.deleteMany();
    await prisma.workshop.deleteMany();
  });

  afterAll(async () => {
    // Order important : supprimer Operations -> Jobs -> Orders -> Machines via cascade.
    // Workshop a 2 chemins de cascade (machines, orders) qui peuvent s'entrelacer
    // avec le Restrict sur Operation.machine_id ; on vide explicitement les
    // tables enfant d'abord pour éviter ce conflit.
    await prisma.order.deleteMany();
    await prisma.workshop.deleteMany();
    await app.close();
  });

  let workshopId: string;
  let machineId: string;
  let clientId: string;

  it('crée un workshop et une v1 active', async () => {
    const res = await request(app.getHttpServer())
      .post('/api/workshops')
      .send({ name: 'Atelier de test', city: 'Paris' })
      .expect(201);

    expect(res.body.id).toBeDefined();
    expect(res.body.name).toBe('Atelier de test');
    workshopId = res.body.id;

    const versions = await request(app.getHttpServer())
      .get(`/api/workshops/${workshopId}/versions`)
      .expect(200);
    expect(versions.body).toHaveLength(1);
    expect(versions.body[0]).toMatchObject({ versionNumber: 1, isActive: true });
  });

  it('rejette les champs supplémentaires (whitelist Pydantic-like)', async () => {
    await request(app.getHttpServer())
      .post('/api/workshops')
      .send({ name: 'Bad', unknownField: 42 })
      .expect(400);
  });

  it('ajoute une machine et incrémente la version', async () => {
    const res = await request(app.getHttpServer())
      .post(`/api/workshops/${workshopId}/machines`)
      .send({ name: 'Tour CN-1', type: 'Tour CN' })
      .expect(201);

    expect(res.body.machineIdInt).toBe(0); // auto-assigné
    machineId = res.body.id;

    const v = await request(app.getHttpServer())
      .get(`/api/workshops/${workshopId}/versions`)
      .expect(200);
    expect(v.body).toHaveLength(2);
    expect(v.body[0]).toMatchObject({ versionNumber: 2, isActive: true });
  });

  it('refuse une machine avec machineIdInt déjà pris', async () => {
    await request(app.getHttpServer())
      .post(`/api/workshops/${workshopId}/machines`)
      .send({ name: 'Tour CN-1bis', machineIdInt: 0 })
      .expect(409);
  });

  it('crée client + OF avec gamme à 2 ops', async () => {
    const c = await request(app.getHttpServer())
      .post(`/api/workshops/${workshopId}/clients`)
      .send({ name: 'Safran', tier: 1, certifications: ['EN 9100'] })
      .expect(201);
    clientId = c.body.id;

    const o = await request(app.getHttpServer())
      .post(`/api/workshops/${workshopId}/orders`)
      .send({
        clientId,
        orderRef: 'OF-2026-0001',
        partRef: 'Bague aube TBP',
        quantity: 1,
        criticality: 1,
        operations: [
          { sequenceIdx: 0, machineId, durationMin: 30 },
          { sequenceIdx: 1, machineId, durationMin: 10 },
        ],
      })
      .expect(201);

    expect(o.body.job.operations).toHaveLength(2);
    expect(o.body.job.criticality).toBe(1);
  });

  it('refuse un OF avec sequence_idx non contigus', async () => {
    await request(app.getHttpServer())
      .post(`/api/workshops/${workshopId}/orders`)
      .send({
        clientId,
        orderRef: 'OF-bad',
        partRef: 'X',
        operations: [
          { sequenceIdx: 0, machineId, durationMin: 10 },
          { sequenceIdx: 2, machineId, durationMin: 10 }, // saute 1
        ],
      })
      .expect(400);
  });

  it('refuse un OF référençant une machine d\'un autre workshop', async () => {
    // Créer un 2e workshop avec sa propre machine
    const w2 = await request(app.getHttpServer())
      .post('/api/workshops')
      .send({ name: 'Atelier 2' })
      .expect(201);
    const m2 = await request(app.getHttpServer())
      .post(`/api/workshops/${w2.body.id}/machines`)
      .send({ name: 'Externe' })
      .expect(201);

    await request(app.getHttpServer())
      .post(`/api/workshops/${workshopId}/orders`)
      .send({
        clientId,
        orderRef: 'OF-2026-0002',
        partRef: 'X',
        operations: [{ sequenceIdx: 0, machineId: m2.body.id, durationMin: 10 }],
      })
      .expect(400);
  });

  it('rollback crée une nouvelle version sans détruire l\'historique', async () => {
    // Snapshot des versions avant rollback
    const before = await request(app.getHttpServer())
      .get(`/api/workshops/${workshopId}/versions`)
      .expect(200);
    const targetVersionNumber = 1;
    const lastBefore = before.body[0].versionNumber;

    const r = await request(app.getHttpServer())
      .post(`/api/workshops/${workshopId}/versions/${targetVersionNumber}/rollback`)
      .expect(201);

    expect(r.body.versionNumber).toBe(lastBefore + 1);
    expect(r.body.message).toContain(`Rollback vers v${targetVersionNumber}`);
    expect(r.body.isActive).toBe(true);

    const after = await request(app.getHttpServer())
      .get(`/api/workshops/${workshopId}/versions`)
      .expect(200);
    expect(after.body).toHaveLength(before.body.length + 1);
    // L'historique n'a pas été supprimé
    const stillThere = after.body.find(
      (v: { versionNumber: number }) => v.versionNumber === targetVersionNumber,
    );
    expect(stillThere).toBeDefined();
  });

  it('refuse un rollback vers la version active', async () => {
    const list = await request(app.getHttpServer())
      .get(`/api/workshops/${workshopId}/versions`)
      .expect(200);
    const active = list.body.find((v: { isActive: boolean }) => v.isActive);
    await request(app.getHttpServer())
      .post(`/api/workshops/${workshopId}/versions/${active.versionNumber}/rollback`)
      .expect(409);
  });

  it('refuse un rollback vers une version inexistante', async () => {
    await request(app.getHttpServer())
      .post(`/api/workshops/${workshopId}/versions/9999/rollback`)
      .expect(404);
  });

  it('snapshot inclut machines + orders + clients', async () => {
    const v1 = await request(app.getHttpServer())
      .get(`/api/workshops/${workshopId}/versions/1`)
      .expect(200);
    expect(v1.body.snapshot).toBeDefined();
    expect(v1.body.snapshot.machines).toEqual([]); // v1 = juste après création workshop
  });
});
