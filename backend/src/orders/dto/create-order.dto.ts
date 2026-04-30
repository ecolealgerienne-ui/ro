import { Type } from 'class-transformer';
import {
  ArrayMinSize,
  IsArray,
  IsDateString,
  IsInt,
  IsOptional,
  IsString,
  IsUUID,
  Max,
  MaxLength,
  Min,
  MinLength,
  ValidateNested,
} from 'class-validator';

/** Une opération de la gamme : machine + durée + family + opérateurs qualifiés. */
export class CreateOperationDto {
  /** Index de séquence dans la gamme (0-indexé). */
  @IsInt()
  @Min(0)
  sequenceIdx!: number;

  /** UUID de la machine (Machine.id, pas machineIdInt). */
  @IsUUID()
  machineId!: string;

  /** Durée en minutes (cohérente avec horizon engine). */
  @IsInt()
  @Min(1)
  durationMin!: number;

  /** Index famille de pièce dans la transition_matrix du workshop. */
  @IsOptional()
  @IsInt()
  @Min(0)
  familyId?: number;

  /** Liste des operatorIdInt qualifiés. Vide = pas de contrainte opérateur. */
  @IsOptional()
  @IsArray()
  @IsInt({ each: true })
  qualifiedOperatorIds?: number[];
}

export class CreateOrderDto {
  @IsUUID()
  clientId!: string;

  /** Identifiant métier visible (ex: OF-2026-0847), unique par workshop. */
  @IsString()
  @MinLength(1)
  @MaxLength(80)
  orderRef!: string;

  @IsString()
  @MinLength(1)
  @MaxLength(120)
  partRef!: string;

  @IsOptional()
  @IsInt()
  @Min(0)
  partFamilyId?: number;

  @IsOptional()
  @IsInt()
  @Min(1)
  @Max(10000)
  quantity?: number;

  @IsOptional()
  @IsDateString()
  deadline?: string;

  /** Surcharge le tier hérité du client (1=critique, 3=standard). */
  @IsOptional()
  @IsInt()
  @Min(1)
  @Max(3)
  criticality?: number;

  /** Gamme opératoire. Au moins une opération requise. */
  @IsArray()
  @ArrayMinSize(1)
  @ValidateNested({ each: true })
  @Type(() => CreateOperationDto)
  operations!: CreateOperationDto[];
}
