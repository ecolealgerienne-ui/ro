import { AnomalyStatus } from '@prisma/client';
import { IsEnum, IsOptional, IsString, MaxLength } from 'class-validator';

export class UpdateAnomalyDto {
  @IsEnum(AnomalyStatus)
  status!: AnomalyStatus;

  /** Texte libre décrivant ce que l'utilisateur a fait (corrigé, ignoré, exclu...). */
  @IsOptional()
  @IsString()
  @MaxLength(500)
  resolution?: string;
}
