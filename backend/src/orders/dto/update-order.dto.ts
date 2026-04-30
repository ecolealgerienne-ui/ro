import { OmitType, PartialType } from '@nestjs/mapped-types';
import { IsEnum, IsOptional } from 'class-validator';
import { OrderStatus } from '@prisma/client';
import { CreateOrderDto } from './create-order.dto';

/**
 * Mise à jour partielle. La gamme `operations` n'est PAS modifiable via PATCH
 * en V1 — il faut supprimer l'OF et le recréer pour changer la gamme. Cette
 * restriction garde le versioning lisible (un changement de gamme = un OF
 * neuf, pas un patch en place qui mélange l'historique).
 */
export class UpdateOrderDto extends PartialType(OmitType(CreateOrderDto, ['operations'] as const)) {
  @IsOptional()
  @IsEnum(OrderStatus)
  status?: OrderStatus;
}
