import {
  Body,
  Controller,
  Delete,
  Get,
  HttpCode,
  HttpStatus,
  Param,
  ParseUUIDPipe,
  Patch,
  Post,
} from '@nestjs/common';
import { CreateOrderDto } from './dto/create-order.dto';
import { UpdateOrderDto } from './dto/update-order.dto';
import { OrdersService } from './orders.service';

@Controller('workshops/:workshopId/orders')
export class OrdersController {
  constructor(private readonly orders: OrdersService) {}

  @Post()
  @HttpCode(HttpStatus.CREATED)
  create(@Param('workshopId', ParseUUIDPipe) workshopId: string, @Body() dto: CreateOrderDto) {
    return this.orders.create(workshopId, dto);
  }

  @Get()
  findAll(@Param('workshopId', ParseUUIDPipe) workshopId: string) {
    return this.orders.findAll(workshopId);
  }

  @Get(':id')
  findOne(
    @Param('workshopId', ParseUUIDPipe) workshopId: string,
    @Param('id', ParseUUIDPipe) id: string,
  ) {
    return this.orders.findOne(workshopId, id);
  }

  @Patch(':id')
  update(
    @Param('workshopId', ParseUUIDPipe) workshopId: string,
    @Param('id', ParseUUIDPipe) id: string,
    @Body() dto: UpdateOrderDto,
  ) {
    return this.orders.update(workshopId, id, dto);
  }

  @Delete(':id')
  remove(
    @Param('workshopId', ParseUUIDPipe) workshopId: string,
    @Param('id', ParseUUIDPipe) id: string,
  ) {
    return this.orders.remove(workshopId, id);
  }
}
