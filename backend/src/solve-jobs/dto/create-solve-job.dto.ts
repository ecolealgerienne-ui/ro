import { Type } from 'class-transformer';
import {
  ArrayMaxSize,
  ArrayMinSize,
  IsArray,
  IsInt,
  IsNumber,
  IsOptional,
  IsUUID,
  Max,
  Min,
} from 'class-validator';

/** Configuration optionnelle d'un solve. Défauts gérés côté worker Python. */
class SolveConfig {
  /** Budgets temps croissants (en secondes) pour le circuit breaker. */
  @IsOptional()
  @IsArray()
  @IsNumber({}, { each: true })
  @Min(0.1, { each: true })
  @Max(600, { each: true })
  @ArrayMinSize(1)
  @ArrayMaxSize(5)
  time_budgets_s?: number[];

  @IsOptional()
  @IsInt()
  @Min(1)
  @Max(32)
  num_workers?: number;
}

export class CreateSolveJobDto {
  /**
   * Version source à résoudre. Optionnel : si omis, le worker prend la version
   * active du workshop au moment de l'exécution (peut différer de "maintenant"
   * si le poll prend du retard, mais c'est cohérent — dernière version validée).
   */
  @IsOptional()
  @IsUUID()
  versionId?: string;

  @IsOptional()
  @Type(() => SolveConfig)
  config?: SolveConfig;
}
