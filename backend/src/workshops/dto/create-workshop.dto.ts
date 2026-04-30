import {
  ArrayMaxSize,
  ArrayMinSize,
  ArrayUnique,
  IsArray,
  IsInt,
  IsOptional,
  IsString,
  Max,
  MaxLength,
  Min,
  MinLength,
} from 'class-validator';

export class CreateWorkshopDto {
  @IsString()
  @MinLength(2)
  @MaxLength(100)
  name!: string;

  @IsOptional()
  @IsString()
  @MaxLength(100)
  city?: string;

  @IsOptional()
  @IsArray()
  @IsString({ each: true })
  @ArrayMaxSize(10)
  certifications?: string[];

  /** Début de quart en minutes depuis minuit (ex: 360 = 6h00). */
  @IsOptional()
  @IsInt()
  @Min(0)
  @Max(1440)
  shiftStart?: number;

  /** Fin de quart en minutes depuis minuit (ex: 1320 = 22h00). */
  @IsOptional()
  @IsInt()
  @Min(0)
  @Max(1440)
  shiftEnd?: number;

  /** Jours travaillés au format ISO (1=lundi, 7=dimanche). */
  @IsOptional()
  @IsArray()
  @IsInt({ each: true })
  @Min(1, { each: true })
  @Max(7, { each: true })
  @ArrayUnique()
  @ArrayMinSize(1)
  @ArrayMaxSize(7)
  workdays?: number[];

  @IsOptional()
  @IsInt()
  @Min(0)
  @Max(500)
  nOperators?: number;
}
