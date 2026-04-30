import { IsInt, IsOptional, IsString, MaxLength, Min, MinLength } from 'class-validator';

export class CreateMachineDto {
  @IsString()
  @MinLength(1)
  @MaxLength(80)
  name!: string;

  @IsOptional()
  @IsString()
  @MaxLength(60)
  type?: string;

  /**
   * Index entier 0-N stable pour le solveur. Optionnel à la création :
   * si omis, le service auto-assigne `max(machineIdInt) + 1` du workshop.
   */
  @IsOptional()
  @IsInt()
  @Min(0)
  machineIdInt?: number;
}
