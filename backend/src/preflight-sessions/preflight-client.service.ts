import { HttpException, Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';

/**
 * Erreur preflight (un PreflightError côté Python).
 */
export interface PreflightError {
  type: string;
  severity: 'blocking' | 'warning' | 'info';
  row_index: number | null;
  column: string | null;
  raw_value: string | null;
  description: string;
}

export interface CleanedRow {
  raw_index: number;
  cells: Record<string, string>;
}

/**
 * Réponse JSON renvoyée par le service Python `scripts/preflight_service.py`.
 * Aligné avec `src.preflight.models.PreflightReport`.
 */
export interface PreflightReport {
  csv_parseable: boolean;
  detected_separator: string | null;
  detected_encoding: string | null;
  column_mapping_suggested: Record<string, string>;
  rows_parsed: number;
  errors: PreflightError[];
  cleaned_rows: CleanedRow[];
  filename: string;
}

/**
 * Bridge HTTP synchrone vers le service Python qui expose `src/preflight/`.
 *
 * Le pre-flight est rapide (parsing CSV + fuzzy match, < 1s pour 500 lignes
 * typiquement), donc pas besoin de DB-as-queue : appel bloquant suffisant.
 */
@Injectable()
export class PreflightClientService {
  private readonly logger = new Logger(PreflightClientService.name);
  private readonly baseUrl: string;

  constructor(config: ConfigService) {
    this.baseUrl = config.get<string>('PREFLIGHT_SERVICE_URL', 'http://localhost:8001');
  }

  async runPreflight(
    fileBuffer: Buffer,
    filename: string,
    mimeType: string,
  ): Promise<PreflightReport> {
    const form = new FormData();
    const blob = new Blob([new Uint8Array(fileBuffer)], { type: mimeType || 'text/csv' });
    form.append('file', blob, filename);

    const url = `${this.baseUrl}/preflight`;
    this.logger.debug(`POST ${url} (${fileBuffer.length} bytes)`);

    let res: Response;
    try {
      res = await fetch(url, { method: 'POST', body: form });
    } catch (e) {
      const err = e as Error;
      throw new HttpException(
        `Service preflight injoignable (${this.baseUrl}) : ${err.message}`,
        503,
      );
    }
    if (!res.ok) {
      const text = await res.text().catch(() => '');
      throw new HttpException(
        `Service preflight a renvoyé ${res.status} : ${text.slice(0, 300)}`,
        502,
      );
    }
    return (await res.json()) as PreflightReport;
  }
}
