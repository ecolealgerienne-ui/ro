import {
  ArrayMaxSize,
  IsArray,
  IsInt,
  IsOptional,
  IsString,
  Max,
  MaxLength,
  Min,
  MinLength,
} from 'class-validator';

export class CreateClientDto {
  @IsString()
  @MinLength(1)
  @MaxLength(80)
  name!: string;

  /** Tier de criticité : 1=critique, 2=standard, 3=opportuniste. */
  @IsOptional()
  @IsInt()
  @Min(1)
  @Max(3)
  tier?: number;

  @IsOptional()
  @IsArray()
  @IsString({ each: true })
  @ArrayMaxSize(10)
  certifications?: string[];
}
